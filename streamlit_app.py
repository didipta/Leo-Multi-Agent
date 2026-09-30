"""Leo: Multi-Agent AI Tutor — Professional Streamlit Web Application.

A multi-agent pedagogical application featuring:
- 👑 Coordinator: Analyzes student requests and formulates plans
- 💡 Explainer: Teaches concepts with analogies, examples, and tools
- 📝 Quiz Master: Generates diagnostic quizzes with structured output
- 🎯 Evaluator: Grades answers, provides feedback, and diagnoses gaps
- 🔄 Feedback Loop: Automatically re-teaches weak concepts when score < 70%
- 🤝 Human-in-the-Loop: Allows student interventions and follow-up Q&A
"""
import os
import time
import streamlit as st

# Page configuration
st.set_page_config(
    page_title="Leo — Multi-Agent AI Tutor",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom High-End Styling
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }

    /* Gradient Brand Header */
    .brand-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 50%, #f472b6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .brand-sub {
        font-size: 1.05rem;
        color: #94a3b8;
        margin-bottom: 1.5rem;
    }

    /* Agent Role Badges */
    .badge {
        display: inline-flex;
        align-items: center;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-right: 8px;
        letter-spacing: 0.02em;
    }
    .badge-coordinator {
        background: rgba(245, 158, 11, 0.15);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }
    .badge-explainer {
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .badge-quizmaster {
        background: rgba(139, 92, 246, 0.15);
        color: #c084fc;
        border: 1px solid rgba(139, 92, 246, 0.3);
    }
    .badge-evaluator {
        background: rgba(6, 182, 212, 0.15);
        color: #38bdf8;
        border: 1px solid rgba(6, 182, 212, 0.3);
    }

    /* Glass Cards */
    .glass-card {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 20px;
        margin-bottom: 18px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
    }
    .glass-card-highlight {
        background: linear-gradient(135deg, rgba(59, 130, 246, 0.05) 0%, rgba(139, 92, 246, 0.05) 100%);
        border: 1px solid rgba(139, 92, 246, 0.25);
        border-radius: 14px;
        padding: 22px;
        margin-bottom: 20px;
    }

    /* Handoff Banner */
    .handoff-banner {
        background: rgba(30, 41, 59, 0.7);
        border-left: 4px solid #38bdf8;
        border-radius: 8px;
        padding: 10px 16px;
        margin: 14px 0;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.88rem;
        color: #e2e8f0;
    }

    /* Progress Pipeline Steps */
    .step-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px;
        padding: 12px 18px;
        margin-bottom: 24px;
    }
    .step-pill {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 0.82rem;
        font-weight: 600;
        color: #64748b;
    }
    .step-pill.active {
        color: #38bdf8;
    }
    .step-pill.completed {
        color: #10b981;
    }

    /* Score Meter */
    .score-circle {
        font-size: 2.8rem;
        font-weight: 800;
        text-align: center;
        padding: 16px;
        border-radius: 16px;
        margin-bottom: 12px;
    }
    .score-pass {
        background: rgba(16, 185, 129, 0.1);
        color: #34d399;
        border: 2px solid rgba(16, 185, 129, 0.3);
    }
    .score-retry {
        background: rgba(245, 158, 11, 0.1);
        color: #fbbf24;
        border: 2px solid rgba(245, 158, 11, 0.3);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Import Leo Core Modules
from leo.config import check_api_key, DEFAULT_MODEL, PASS_PCT, MAX_RELEARN, N_QUESTIONS
from leo.logger import logger
from leo.memory import StudentMemory
from leo.models import Plan, Quiz, Question, Evaluation
from leo.orchestrator import LeoOrchestrator

# Session State Initialization
if "memory" not in st.session_state:
    st.session_state.memory = StudentMemory()

if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = LeoOrchestrator(memory=st.session_state.memory)

if "stage" not in st.session_state:
    st.session_state.stage = "input"  # input -> clarify -> lesson -> quiz -> evaluated -> reteach

if "plan" not in st.session_state:
    st.session_state.plan = None

if "lesson" not in st.session_state:
    st.session_state.lesson = ""

if "quiz" not in st.session_state:
    st.session_state.quiz = None

if "evaluation" not in st.session_state:
    st.session_state.evaluation = None

if "followups" not in st.session_state:
    st.session_state.followups = []

if "student_answers" not in st.session_state:
    st.session_state.student_answers = {}

if "clarification_needed" not in st.session_state:
    st.session_state.clarification_needed = False

if "clarifying_question" not in st.session_state:
    st.session_state.clarifying_question = ""

if "clarifications" not in st.session_state:
    st.session_state.clarifications = []

if "relearn_round" not in st.session_state:
    st.session_state.relearn_round = 0


# ==============================================================================
# Sidebar: Student Profile, Configuration & Live Agent Logs
# ==============================================================================
with st.sidebar:
    st.markdown("### 🎓 Leo Tutor Control")
    student_name = st.text_input(
        "Student Name",
        value=st.session_state.memory.name or "Alex",
        help="Leo remembers your name and learning profile between sessions.",
    )
    if student_name != st.session_state.memory.name:
        st.session_state.memory.set_name(student_name)

    st.markdown("---")
    st.markdown("#### ⚙️ Agent Engine Settings")
    api_key_status = check_api_key()
    if api_key_status:
        st.success("✅ API Key configured (.env)")
    else:
        st.error("⚠️ Missing API Key! Configure GEMINI_API_KEY in .env or enter below:")
        custom_key = st.text_input("Gemini API Key", type="password")
        if custom_key:
            os.environ["GEMINI_API_KEY"] = custom_key
            st.session_state.orchestrator = LeoOrchestrator(memory=st.session_state.memory)
            st.rerun()

    model_name = st.selectbox(
        "LLM Model",
        ["gemini/gemini-3.5-flash", "gemini/gemini-3.7-flash", "gemini/gemini-3.8-flash", "gpt-4o-mini", "groq/llama-3.3-70b-versatile"],
        index=0,
    )
    os.environ["LEO_MODEL"] = model_name

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        pass_threshold = st.number_input("Pass Score %", min_value=50, max_value=90, value=PASS_PCT, step=5)
    with col_s2:
        question_count = st.number_input("Quiz Questions", min_value=2, max_value=6, value=N_QUESTIONS, step=1)

    st.markdown("---")
    # Learning History (Memory)
    history = st.session_state.memory.get_history()
    with st.expander(f"📚 Learning Memory ({len(history)} sessions)", expanded=False):
        if history:
            for item in reversed(history[-5:]):
                score_color = "🟢" if item.get("score", 0) >= pass_threshold else "🟡"
                st.markdown(
                    f"{score_color} **{item.get('topic')}** ({item.get('level')})\n"
                    f"- Score: **{item.get('score')}%** | {item.get('date')}\n"
                    + (f"- Weak areas: `{', '.join(item.get('weak', []))}`\n" if item.get("weak") else "- Mastered completely!\n")
                )
            if st.button("Clear Memory History", use_container_width=True):
                st.session_state.memory.clear()
                st.rerun()
        else:
            st.caption("No past sessions recorded yet. Complete a quiz to build memory!")

    # Live Agent Event Log
    st.markdown("---")
    with st.expander("⚡ Live Agent Event Bus", expanded=True):
        events = logger.get_events()
        if events:
            for ev in reversed(events[-10:]):
                if ev.event_type == "handoff":
                    st.markdown(f"**[{ev.timestamp}]** 🔀 `{ev.agent}` ➔ `{ev.target_agent}`: {ev.message}")
                elif ev.event_type == "working":
                    st.caption(f"[{ev.timestamp}] ⚙️ **{ev.agent}**: {ev.message}")
                elif ev.event_type == "warning":
                    st.warning(f"[{ev.timestamp}] ⚠️ {ev.message}")
                elif ev.event_type == "tool":
                    st.info(f"[{ev.timestamp}] 🛠️ **{ev.agent}**: {ev.message}")
        else:
            st.caption("Agent activity stream is ready.")

    if st.button("🔄 Start New Topic / Reset", use_container_width=True):
        st.session_state.stage = "input"
        st.session_state.plan = None
        st.session_state.lesson = ""
        st.session_state.quiz = None
        st.session_state.evaluation = None
        st.session_state.followups = []
        st.session_state.student_answers = {}
        st.session_state.clarifications = []
        st.session_state.relearn_round = 0
        st.rerun()


# ==============================================================================
# Header & Multi-Agent Architecture Badges
# ==============================================================================
col_head1, col_head2 = st.columns([3, 1])
with col_head1:
    st.markdown('<div class="brand-title">Leo: Multi-Agent AI Tutor</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="brand-sub">Collaborative pedagogical system powered by CrewAI: '
        'Plan ➔ Teach ➔ Handoff ➔ Quiz ➔ Grade ➔ Feedback Loop</div>',
        unsafe_allow_html=True,
    )
with col_head2:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='text-align:right;'><span style='color:#94a3b8; font-size:0.9rem;'>Active Student:</span><br>"
        f"<b>{st.session_state.memory.name or 'Student'}</b></div>",
        unsafe_allow_html=True,
    )

# Agent Roster Badges
st.markdown(
    """
    <div style="margin-bottom: 20px;">
        <span class="badge badge-coordinator">👑 Coordinator (Planner)</span>
        <span class="badge badge-explainer">💡 Explainer (Pedagogy)</span>
        <span class="badge badge-quizmaster">📝 Quiz Master (Assessment)</span>
        <span class="badge badge-evaluator">🎯 Evaluator (Diagnosis)</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# Pipeline Step Visualizer
stages = ["1. Plan", "2. Lesson", "3. Clarify (HITL)", "4. Quiz", "5. Evaluation"]
current_idx = 0
if st.session_state.stage in ("input", "clarify"):
    current_idx = 0
elif st.session_state.stage == "lesson":
    current_idx = 1
elif st.session_state.stage == "quiz":
    current_idx = 3
elif st.session_state.stage in ("evaluated", "reteach"):
    current_idx = 4

step_html = '<div class="step-container">'
for idx, s in enumerate(stages):
    cls = "step-pill completed" if idx < current_idx else ("step-pill active" if idx == current_idx else "step-pill")
    icon = "✓" if idx < current_idx else ("▶" if idx == current_idx else "○")
    step_html += f'<div class="{cls}"><span>{icon}</span> {s}</div>'
step_html += "</div>"
st.markdown(step_html, unsafe_allow_html=True)


# ==============================================================================
# Stage 1: Topic Selection & Coordinator Planning
# ==============================================================================
if st.session_state.stage in ("input", "clarify"):
    st.markdown("### 🎯 What would you like to master today?")

    # Topic chips for instant inspiration
    st.caption("Suggested study topics:")
    chip_cols = st.columns(5)
    suggestions = [
        "Gradient Descent & Optimizers",
        "Python Generators & Yield",
        "Docker Containerization",
        "Attention Mechanism in Transformers",
        "REST vs GraphQL APIs",
    ]
    selected_suggestion = None
    for i, chip in enumerate(suggestions):
        with chip_cols[i]:
            if st.button(chip, key=f"chip_{i}", use_container_width=True):
                selected_suggestion = chip

    topic_input = st.text_input(
        "Enter any concept, topic, or question:",
        value=selected_suggestion or "",
        placeholder="e.g., How does backpropagation work in neural networks?",
    )

    # Clarification UI if Coordinator previously flagged vague prompt
    if st.session_state.stage == "clarify":
        st.markdown(
            f"""
            <div class="glass-card" style="border-left: 4px solid #f59e0b;">
                <span class="badge badge-coordinator">👑 Coordinator Clarification</span><br><br>
                <b>Leo needs a tiny bit more information:</b><br>
                {st.session_state.clarifying_question}
            </div>
            """,
            unsafe_allow_html=True,
        )
        clarification_input = st.text_input("Your clarification response:", placeholder="e.g. Focus on intuition and code implementation")
        if st.button("Submit Clarification to Coordinator", type="primary"):
            st.session_state.clarifications.append(clarification_input)
            with st.spinner("👑 Coordinator is finalizing the lesson trajectory..."):
                plan = st.session_state.orchestrator.plan_session(
                    topic_input or "AI fundamentals",
                    clarification_callback=lambda q: clarification_input,
                )
                st.session_state.plan = plan
                st.session_state.stage = "lesson"
                st.rerun()

    else:
        if st.button("🚀 Start Tutoring Session", type="primary"):
            if not topic_input.strip():
                st.warning("Please enter a topic to start.")
            else:
                with st.spinner("👑 Coordinator is analyzing your request and designing the learning trajectory..."):
                    # Coordinator analyzes topic
                    plan = st.session_state.orchestrator.plan_session(
                        topic_input,
                        clarification_callback=lambda q: "",  # will handle in UI if needs_clarification
                    )
                    st.session_state.plan = plan

                    if plan.needs_clarification and plan.clarifying_question:
                        st.session_state.clarifying_question = plan.clarifying_question
                        st.session_state.stage = "clarify"
                        st.rerun()
                    else:
                        # Coordinator initiates Explainer + Quiz Master sequential crew
                        with st.spinner("💡 Explainer is crafting the lesson with analogies & code examples..."):
                            lesson, quiz = st.session_state.orchestrator.teach_and_generate_quiz(plan)
                            st.session_state.lesson = lesson or "Lesson unavailable."
                            st.session_state.quiz = quiz
                            st.session_state.stage = "lesson"
                            st.rerun()


# ==============================================================================
# Stage 2: Lesson Presentation & Human-in-the-Loop Clarification
# ==============================================================================
if st.session_state.stage == "lesson":
    plan = st.session_state.plan
    st.markdown(
        f"""
        <div class="glass-card-highlight">
            <span class="badge badge-coordinator">👑 Coordinator Approved Plan</span>
            <span style="float:right; color:#94a3b8; font-size:0.85rem;">Target Level: <b>{plan.level.title()}</b></span>
            <h3 style="margin-top:10px; margin-bottom:6px;">Topic: {plan.topic}</h3>
            <span style="color:#cbd5e1; font-size:0.92rem;">Key Focus Points: {', '.join(plan.focus_points)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="handoff-banner">➜ HANDOFF: [Coordinator] ──▶ [Explainer] : delegated lesson production</div>',
        unsafe_allow_html=True,
    )

    # Explainer's Lesson
    st.markdown(
        f"""
        <div class="glass-card">
            <span class="badge badge-explainer">💡 Explainer Lesson</span>
            <div style="margin-top: 14px; line-height: 1.7;">
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(st.session_state.lesson)

    st.markdown(
        '<div class="handoff-banner">➜ HANDOFF: [Explainer] ──▶ [Quiz Master] : lesson text passed as Task context for question formulation</div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # Bonus: Human-in-the-Loop Interactivity
    st.markdown("### 🤝 Human-in-the-Loop: Have questions before the quiz?")
    st.caption("Ask Leo's Explainer anything to clarify concepts before taking your practice quiz.")

    # Show past followups
    for item in st.session_state.followups:
        with st.chat_message("user"):
            st.markdown(item["question"])
        with st.chat_message("assistant", avatar="💡"):
            st.markdown(f"**Explainer:** {item['answer']}")

    student_followup = st.text_input("Ask a follow-up question:", placeholder="e.g. Could you explain the analogy again?")
    col_hitl1, col_hitl2 = st.columns([1, 2])
    with col_hitl1:
        if st.button("💬 Ask Explainer"):
            if student_followup.strip():
                with st.spinner("💡 Explainer is reviewing your question..."):
                    answer = st.session_state.orchestrator.answer_student_followup(plan, student_followup)
                    st.session_state.followups.append({"question": student_followup, "answer": answer})
                    st.rerun()

    with col_hitl2:
        if st.button("📝 Ready! Begin Practice Quiz ➔", type="primary", use_container_width=True):
            st.session_state.stage = "quiz"
            st.rerun()


# ==============================================================================
# Stage 3: Interactive Practice Quiz (Quiz Master)
# ==============================================================================
if st.session_state.stage == "quiz":
    quiz = st.session_state.quiz
    plan = st.session_state.plan

    st.markdown(
        f"""
        <div class="glass-card">
            <span class="badge badge-quizmaster">📝 Quiz Master</span>
            <h3 style="margin-top:8px;">{quiz.title if quiz else 'Diagnostic Practice Quiz'}</h3>
            <p style="color:#94a3b8; font-size:0.92rem;">
                Answer the questions below to test your understanding of <b>{plan.topic}</b>.
                You can view hints if you get stuck.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    submitted_answers = {}

    if quiz and quiz.questions:
        for q in quiz.questions:
            st.markdown(
                f"""
                <div style="background: rgba(255,255,255,0.02); border-radius: 10px; padding: 14px 18px; margin-bottom: 12px; border: 1px solid rgba(255,255,255,0.06);">
                    <span style="font-weight: 700; color: #c084fc;">Question {q.id}</span>
                    <span style="float:right; font-size: 0.8rem; color: #94a3b8; background: rgba(255,255,255,0.05); padding: 2px 8px; border-radius: 6px;">Concept: {q.concept}</span>
                    <div style="margin-top: 6px; font-size: 1.02rem; font-weight: 500;">{q.question}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Option selection
            if q.options and len(q.options) >= 2:
                selected_opt = st.radio(
                    f"Select your answer for Q{q.id}:",
                    options=q.options,
                    index=None,
                    key=f"ans_radio_{q.id}",
                    label_visibility="collapsed",
                )
                submitted_answers[q.id] = selected_opt or "(skipped)"
            else:
                text_ans = st.text_input(
                    f"Your answer for Q{q.id}:",
                    key=f"ans_text_{q.id}",
                    placeholder="Type your explanation...",
                    label_visibility="collapsed",
                )
                submitted_answers[q.id] = text_ans or "(skipped)"

            # Hint Expander
            with st.expander(f"💡 Hint for Q{q.id}"):
                st.caption(f"Concept key: Focus on **{q.concept}** as explained in the lesson.")

            st.markdown("<br>", unsafe_allow_html=True)

        col_sub1, col_sub2 = st.columns([2, 1])
        with col_sub1:
            if st.button("🎯 Submit Answers to Evaluator", type="primary", use_container_width=True):
                st.session_state.student_answers = submitted_answers
                with st.spinner("🎯 Evaluator is reviewing your answers against the answer key..."):
                    evaluation = st.session_state.orchestrator.evaluate_submission(quiz, submitted_answers)
                    st.session_state.evaluation = evaluation
                    st.session_state.stage = "evaluated"
                    st.rerun()

        with col_sub2:
            if st.button("⬅️ Review Lesson", use_container_width=True):
                st.session_state.stage = "lesson"
                st.rerun()
    else:
        st.error("Quiz questions could not be loaded. Please click Reset in the sidebar.")


# ==============================================================================
# Stage 4: Evaluator Scorecard, Feedback & Bonus Feedback Loop
# ==============================================================================
if st.session_state.stage in ("evaluated", "reteach"):
    evaluation = st.session_state.evaluation
    plan = st.session_state.plan
    quiz = st.session_state.quiz

    st.markdown(
        '<div class="handoff-banner">➜ HANDOFF: [Quiz Master & Student] ──▶ [Evaluator] : quiz rubrics and student answers submitted</div>',
        unsafe_allow_html=True,
    )

    if evaluation:
        total_score = sum(g.score for g in evaluation.grades)
        max_score = 2 * max(len(evaluation.grades), 1)
        score_pct = round(100 * total_score / max_score)
        passed = score_pct >= pass_threshold
        weak_concepts = evaluation.weak_concepts

        # Save to memory
        st.session_state.memory.record(plan.topic, plan.level, score_pct, weak_concepts)

        # Score Banner
        score_class = "score-pass" if passed else "score-retry"
        status_label = "🎉 Mastery Achieved!" if passed else "📚 Revision Recommended"

        st.markdown(
            f"""
            <div class="score-circle {score_class}">
                <div>{score_pct}%</div>
                <div style="font-size: 1.1rem; font-weight: 600; margin-top: 4px;">{status_label}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Evaluator Overall Feedback
        st.markdown(
            f"""
            <div class="glass-card">
                <span class="badge badge-evaluator">🎯 Evaluator Comprehensive Diagnosis</span>
                <div style="margin-top: 12px; font-size: 1.05rem; line-height: 1.6;">
                    {evaluation.overall_feedback}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Question-by-Question Diagnostic Breakdown
        st.markdown("### 📋 Question Performance Breakdown")
        for g in evaluation.grades:
            badge_color = "#34d399" if g.score == 2 else ("#fbbf24" if g.score == 1 else "#f87171")
            score_text = "2/2 (Correct)" if g.score == 2 else ("1/2 (Partial)" if g.score == 1 else "0/2 (Incorrect)")
            user_ans = st.session_state.student_answers.get(g.question_id, "(skipped)")

            st.markdown(
                f"""
                <div style="background: rgba(255,255,255,0.02); border-left: 4px solid {badge_color}; border-radius: 8px; padding: 14px 18px; margin-bottom: 12px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-weight:700;">Question {g.question_id} ({g.concept})</span>
                        <span style="font-weight:700; color:{badge_color};">{score_text}</span>
                    </div>
                    <div style="margin-top: 6px; font-size:0.92rem; color:#94a3b8;"><b>Your Answer:</b> {user_ans}</div>
                    <div style="margin-top: 6px; font-size:0.95rem; color:#e2e8f0;"><b>Evaluator Feedback:</b> {g.feedback}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("---")

        # ==============================================================================
        # Bonus (+10): Evaluator Feedback Loop (Re-teaching Weak Concepts)
        # ==============================================================================
        if not passed and weak_concepts and st.session_state.relearn_round < MAX_RELEARN:
            st.markdown(
                f"""
                <div class="glass-card-highlight" style="border-left: 4px solid #fbbf24;">
                    <span class="badge badge-coordinator">👑 Coordinator: Bonus Feedback Loop Activated</span>
                    <h4 style="margin-top: 8px;">Remedial Learning Opportunity</h4>
                    <p style="color: #cbd5e1;">
                        The Evaluator diagnosed learning gaps in: <b>{', '.join(weak_concepts)}</b>.<br>
                        Leo's multi-agent feedback loop can route these concepts back to the <b>Explainer</b> to teach them
                        using a completely new analogy and generate a fresh diagnostic quiz.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            col_fb1, col_fb2 = st.columns(2)
            with col_fb1:
                if st.button("🔄 Activate Feedback Loop: Re-teach & Retake Quiz", type="primary", use_container_width=True):
                    st.session_state.relearn_round += 1
                    with st.spinner("💡 Explainer is crafting a fresh remedial explanation for the weak concepts..."):
                        new_lesson, new_quiz = st.session_state.orchestrator.teach_and_generate_quiz(
                            plan,
                            is_reteach=True,
                            weak_concepts=weak_concepts,
                            feedback=evaluation.overall_feedback,
                        )
                        st.session_state.lesson = new_lesson
                        st.session_state.quiz = new_quiz
                        st.session_state.stage = "lesson"
                        st.rerun()

            with col_fb2:
                if st.button("🏁 Conclude Session Here", use_container_width=True):
                    st.session_state.stage = "input"
                    st.balloons()
                    st.success("Session saved to your persistent memory profile!")

        else:
            if passed:
                st.balloons()
                st.success(f"🎉 Excellent mastery, {st.session_state.memory.name}! This session has been saved to your profile.")
            else:
                st.info(f"Session finished, {st.session_state.memory.name}! Review the feedback notes above.")

            if st.button("🚀 Learn Another Topic", type="primary"):
                st.session_state.stage = "input"
                st.session_state.plan = None
                st.session_state.lesson = ""
                st.session_state.quiz = None
                st.session_state.evaluation = None
                st.rerun()
