"""Core Multi-Agent Orchestrator for Leo: AI Tutor.

Implements:
- 4 distinct CrewAI agents (Coordinator, Explainer, Quiz Master, Evaluator)
- Real handoffs between agents with structured Pydantic models
- Human-in-the-loop interventions (follow-up questions, hints, skips)
- Remedial feedback loop when performance < 70%
- Timeout, retries, and stall recovery handled by Coordinator
- Modular programmatic interface used by both CLI and Streamlit Web UI
"""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import json
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from crewai import Agent, Crew, Process, Task

from .config import (
    DEFAULT_MODEL,
    MAX_RELEARN,
    N_QUESTIONS,
    PASS_PCT,
    RETRIES,
    TIMEOUT_S,
    get_llm,
)
from .logger import logger
from .memory import StudentMemory
from .models import Evaluation, Grade, Plan, Question, Quiz
from . import prompts as P
from .tools import AVAILABLE_TOOLS, calculator, web_search
from . import ui_cli as ui


class QuitSession(Exception):
    """Raised when user requests exit."""
    pass


class LeoOrchestrator:
    """Multi-Agent Orchestrator managing pedagogical lifecycle and agent handoffs."""

    def __init__(self, memory: Optional[StudentMemory] = None):
        self.llm = get_llm()
        self.memory = memory or StudentMemory()
        self.current_plan: Optional[Plan] = None
        self.current_lesson: str = ""
        self.current_quiz: Optional[Quiz] = None
        self.current_evaluation: Optional[Evaluation] = None
        self.relearn_rounds: int = 0

    # --------------------------------------------------------------------------
    # Agent Factory
    # --------------------------------------------------------------------------
    def create_agent(self, role_key: str, enable_tools: bool = False) -> Agent:
        """Instantiate a specialized CrewAI Agent with persona and memory context."""
        persona = P.PERSONAS[role_key]
        backstory = persona["backstory"].substitute(student_context=self.memory.context())

        agent_tools = []
        if enable_tools and role_key == "explainer":
            agent_tools = [web_search, calculator]
        elif enable_tools and role_key == "quiz_master":
            agent_tools = [calculator]

        return Agent(
            role=persona["role"],
            goal=persona["goal"],
            backstory=backstory,
            llm=self.llm,
            tools=agent_tools,
            allow_delegation=False,
            verbose=False,
        )

    # --------------------------------------------------------------------------
    # Resilient Crew Execution
    # --------------------------------------------------------------------------
    def run_crew(self, crew_factory: Callable[[], Crew], label: str):
        """Execute a Crew with timeout protection and retry loop for stall recovery."""
        for attempt in range(1, RETRIES + 2):
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(lambda: crew_factory().kickoff())
            try:
                result = future.result(timeout=TIMEOUT_S)
                return result
            except FutureTimeout:
                msg = f"{label} stalled (exceeded {TIMEOUT_S}s). Coordinator initiating retry {attempt}/{RETRIES + 1}..."
                ui.warn(msg)
                logger.log_warn(msg)
            except Exception as e:
                msg = f"{label} encountered an issue: {str(e)[:120]}. Coordinator initiating retry {attempt}/{RETRIES + 1}..."
                ui.warn(msg)
                logger.log_warn(msg)
            finally:
                executor.shutdown(wait=False)

        error_msg = f"Coordinator: {label} could not complete after {RETRIES + 1} attempts."
        ui.error(error_msg)
        return None

    @staticmethod
    def parse_pydantic_output(task_output: Any, model_cls: Any) -> Any:
        """Extract structured Pydantic model from CrewAI TaskOutput with fallback parsing."""
        if getattr(task_output, "pydantic", None) and isinstance(task_output.pydantic, model_cls):
            return task_output.pydantic

        raw_text = getattr(task_output, "raw", str(task_output))

        # Try to find JSON in markdown code blocks
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
        if json_match:
            try:
                return model_cls.model_validate_json(json_match.group(1))
            except Exception:
                pass

        # Try to find outermost curly braces
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start != -1 and end != -1:
            try:
                cleaned = raw_text[start: end + 1]
                return model_cls.model_validate_json(cleaned)
            except Exception:
                pass

        return model_cls.model_validate_json(raw_text)

    # --------------------------------------------------------------------------
    # Stage 1: Planning (Coordinator)
    # --------------------------------------------------------------------------
    def plan_session(self, student_request: str, clarification_callback: Optional[Callable[[str], str]] = None) -> Plan:
        """Coordinator analyzes student request and formulates a study plan."""
        clarifications: List[str] = []
        max_clarification_turns = 3

        for turn_idx in range(max_clarification_turns):
            ui.working("Coordinator", "analyzing your learning request")
            coordinator = self.create_agent("coordinator")

            task_desc = P.PLAN_TASK.substitute(
                request=student_request,
                clarifications=" | ".join(clarifications) if clarifications else "None yet",
            )
            plan_task = Task(
                description=task_desc,
                expected_output="A structured Plan object with topic, level, and focus points",
                agent=coordinator,
                output_pydantic=Plan,
            )

            output = self.run_crew(
                lambda: Crew(agents=[coordinator], tasks=[plan_task], process=Process.sequential),
                "Coordinator",
            )

            if output is None:
                break

            plan = self.parse_pydantic_output(output.tasks_output[0], Plan)

            if not plan.needs_clarification and plan.topic:
                ui.turn(
                    "Coordinator",
                    f"### Study Plan Approved\n"
                    f"- **Topic:** {plan.topic}\n"
                    f"- **Level:** {plan.level.title()}\n"
                    f"- **Core Focus Points:** {', '.join(plan.focus_points)}",
                )
                self.current_plan = plan
                return plan

            # Student needs to clarify
            question = plan.clarifying_question or "Could you clarify which specific aspect you would like to master?"
            ui.turn("Coordinator", question)

            if clarification_callback:
                reply = clarification_callback(question)
            else:
                reply = ui.ask("Your clarification:")

            if reply.lower() in ("/quit", "/exit"):
                raise QuitSession()

            clarifications.append(reply)

        fallback_plan = Plan(topic=student_request, level="beginner", focus_points=["Fundamentals", "Practical Usage"])
        self.current_plan = fallback_plan
        return fallback_plan

    # --------------------------------------------------------------------------
    # Stage 2: Explainer -> Quiz Master (Sequential Crew with Context Handoff)
    # --------------------------------------------------------------------------
    def teach_and_generate_quiz(
        self,
        plan: Plan,
        is_reteach: bool = False,
        weak_concepts: Optional[List[str]] = None,
        feedback: str = "",
        on_lesson_ready: Optional[Callable[[str], None]] = None,
    ) -> Tuple[Optional[str], Optional[Quiz]]:
        """Sequential handoff: Explainer creates lesson -> Quiz Master reads lesson context & creates Quiz."""
        explainer = self.create_agent("explainer", enable_tools=True)
        quiz_master = self.create_agent("quiz_master", enable_tools=False)

        if is_reteach:
            lesson_desc = P.RETEACH_TASK.substitute(
                weak=", ".join(weak_concepts or []),
                feedback=feedback,
                topic=plan.topic,
            )
            working_label = "re-teaching weak concepts with a fresh approach"
        else:
            lesson_desc = P.EXPLAIN_TASK.substitute(
                topic=plan.topic,
                level=plan.level,
                focus=", ".join(plan.focus_points),
            )
            working_label = f"preparing the lesson on '{plan.topic}'"

        def lesson_callback(output):
            raw_lesson = getattr(output, "raw", str(output))
            ui.turn("Explainer", raw_lesson)
            ui.handoff(
                "Explainer",
                "Quiz Master",
                f"passed lesson text ({len(raw_lesson.split())} words) as Task context",
            )
            ui.working("Quiz Master", "generating targeted practice questions from the lesson")
            if on_lesson_ready:
                on_lesson_ready(raw_lesson)

        task_explain = Task(
            description=lesson_desc,
            expected_output="A structured markdown lesson with analogy and code or example",
            agent=explainer,
            callback=lesson_callback,
        )

        task_quiz = Task(
            description=P.QUIZ_TASK.substitute(n=N_QUESTIONS),
            expected_output="A Quiz object with multiple choice and short answer questions",
            agent=quiz_master,
            context=[task_explain],  # REAL HANDOFF via CrewAI context
            output_pydantic=Quiz,
        )

        ui.working("Explainer", working_label)

        crew_output = self.run_crew(
            lambda: Crew(agents=[explainer, quiz_master], tasks=[task_explain, task_quiz], process=Process.sequential),
            "Explainer & Quiz Master Crew",
        )

        if crew_output is None or len(crew_output.tasks_output) < 2:
            return None, None

        lesson_text = getattr(crew_output.tasks_output[0], "raw", str(crew_output.tasks_output[0]))
        quiz_obj = self.parse_pydantic_output(crew_output.tasks_output[1], Quiz)

        self.current_lesson = lesson_text
        self.current_quiz = quiz_obj
        return lesson_text, quiz_obj

    # --------------------------------------------------------------------------
    # Human-in-the-Loop: Post-Lesson Follow-Up
    # --------------------------------------------------------------------------
    def answer_student_followup(self, plan: Plan, student_question: str) -> str:
        """Explainer addresses mid-run student questions before the quiz begins."""
        ui.handoff("Coordinator", "Explainer", f"student question: '{student_question}'")
        ui.working("Explainer", "answering your follow-up question")

        explainer = self.create_agent("explainer", enable_tools=True)
        task = Task(
            description=P.FOLLOWUP_TASK.substitute(topic=plan.topic, question=student_question),
            expected_output="A clear, concise answer in under 120 words",
            agent=explainer,
        )

        output = self.run_crew(
            lambda: Crew(agents=[explainer], tasks=[task], process=Process.sequential),
            "Explainer Followup",
        )
        answer = getattr(output, "raw", "I am having trouble answering that right now, but let's continue to the quiz!")
        ui.turn("Explainer", answer)
        return answer

    # --------------------------------------------------------------------------
    # Stage 3: Evaluator Checks Answers
    # --------------------------------------------------------------------------
    def evaluate_submission(self, quiz: Quiz, answers: Dict[int, str]) -> Optional[Evaluation]:
        """Evaluator checks student answers against the Quiz Master's answer key."""
        evaluator = self.create_agent("evaluator", enable_tools=False)

        ui.handoff("Quiz Master", "Evaluator", "passed quiz specification, rubrics, and answer keys")
        ui.handoff("Student", "Evaluator", f"submitted answers for {len(answers)} questions")
        ui.working("Evaluator", "grading submission and preparing actionable feedback")

        eval_task = Task(
            description=P.EVAL_TASK.substitute(
                quiz=quiz.model_dump_json(indent=2),
                answers=json.dumps(answers, indent=2),
            ),
            expected_output="An Evaluation object containing individual grades, feedback, and weak concepts",
            agent=evaluator,
            output_pydantic=Evaluation,
        )

        output = self.run_crew(
            lambda: Crew(agents=[evaluator], tasks=[eval_task], process=Process.sequential),
            "Evaluator",
        )

        if output is None:
            return None

        evaluation = self.parse_pydantic_output(output.tasks_output[0], Evaluation)
        self.current_evaluation = evaluation
        return evaluation

    # --------------------------------------------------------------------------
    # CLI Full Interactive Session
    # --------------------------------------------------------------------------
    def run_cli_session(self):
        """Execute a full end-to-end interactive tutoring session in the terminal."""
        ui.console.rule("[bold cyan]🎓 Leo: Multi-Agent AI Tutor[/]")

        if not self.memory.name:
            student_name = ui.ask("What is your name?")
            self.memory.set_name(student_name or "Student")

        ui.console.print(f"\nWelcome, [bold green]{self.memory.name}[/]! (Type [bold red]/quit[/] at any prompt to exit)\n")

        # 1. Ask for topic
        request = ui.ask("What topic would you like to study today?")
        if request.lower() in ("/quit", "/exit"):
            return

        # 2. Coordinator Plans
        plan = self.plan_session(request)

        # 3. Explainer & Quiz Master
        ui.handoff("Coordinator", "Explainer", f"commission lesson on '{plan.topic}'")
        lesson, quiz = self.teach_and_generate_quiz(plan)

        if not quiz:
            ui.error("Agents were unable to complete the lesson. Please check your API key in .env.")
            return

        # 4. Human-in-the-Loop Clarification
        while True:
            q = ui.ask("Do you have any questions before starting the quiz? (Press [Enter] to start quiz):")
            if not q:
                break
            if q.lower() in ("/quit", "/exit"):
                return
            self.answer_student_followup(plan, q)

        # 5. Quiz & Evaluation with Bonus Feedback Loop
        rounds = 0
        final_pct = 0
        weak_spots = []

        while True:
            # Collect answers
            answers = {}
            ui.console.print(f"\n[bold magenta]📝 {quiz.title or 'Practice Quiz'}[/]\n")

            for q in quiz.questions:
                opts = ""
                if q.options:
                    opts = "\n" + "\n".join(f"     {opt}" for opt in q.options)
                ui.console.print(f"\n[bold yellow]Q{q.id}.[/] {q.question}{opts}")

                while True:
                    ans = ui.ask("Your answer (type answer, /hint, or /skip):")
                    if ans.lower() in ("/quit", "/exit"):
                        return
                    if ans == "/hint":
                        ui.console.print(f"[dim cyan]💡 Hint: Focus on the concept '{q.concept}'.[/]")
                        continue
                    if ans == "/skip" or not ans:
                        answers[q.id] = "(skipped)"
                    else:
                        answers[q.id] = ans
                    break

            # Evaluate
            evaluation = self.evaluate_submission(quiz, answers)
            if not evaluation:
                ui.warn("Evaluator was temporarily unavailable; concluding session.")
                break

            total_score = sum(g.score for g in evaluation.grades)
            max_score = 2 * max(len(evaluation.grades), 1)
            final_pct = round(100 * total_score / max_score)
            weak_spots = evaluation.weak_concepts

            # Print score table and feedback
            ui.print_score_table(evaluation.grades, final_pct)
            ui.turn(
                "Evaluator",
                f"### Overall Assessment\n\n{evaluation.overall_feedback}\n\n"
                f"**Score:** {final_pct}% {'(Passing)' if final_pct >= PASS_PCT else '(Needs Revision)'}"
            )

            # Check if pass or max relearn attempts reached
            if final_pct >= PASS_PCT or not weak_spots or rounds >= MAX_RELEARN:
                break

            # Bonus Feedback Loop Trigger
            rounds += 1
            ui.handoff(
                "Evaluator",
                "Explainer",
                f"identified weak concepts: {', '.join(weak_spots)} ➔ initiating remedial feedback loop ({rounds}/{MAX_RELEARN})",
            )

            retry_choice = ui.ask("Would you like Leo to re-teach the weak spots and give you a new quiz? (y/n):").lower()
            if retry_choice != "y":
                break

            new_lesson, new_quiz = self.teach_and_generate_quiz(
                plan,
                is_reteach=True,
                weak_concepts=weak_spots,
                feedback=evaluation.overall_feedback,
            )

            if not new_quiz:
                ui.warn("Unable to generate remedial quiz. Concluding session.")
                break

            quiz = new_quiz

        # 6. Save to Persistent Memory
        self.memory.record(plan.topic, plan.level, final_pct, weak_spots)

        closing_msg = (
            f"🎉 Outstanding work, **{self.memory.name}**! You achieved a score of **{final_pct}%** on *{plan.topic}*."
            if final_pct >= PASS_PCT else
            f"Good effort, **{self.memory.name}**! Session recorded. Key areas to review: {', '.join(weak_spots)}."
        )
        ui.turn("Coordinator", closing_msg)

    # Alias for app.py
    session = run_cli_session



Leo = LeoOrchestrator
Quit = QuitSession
