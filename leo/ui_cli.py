import sys
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from .logger import logger

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console()

AGENT_STYLES = {
    "Coordinator": {"color": "yellow", "icon": "👑", "badge": "bold yellow"},
    "Explainer": {"color": "green", "icon": "💡", "badge": "bold green"},
    "Quiz Master": {"color": "magenta", "icon": "📝", "badge": "bold magenta"},
    "Evaluator": {"color": "cyan", "icon": "🎯", "badge": "bold cyan"},
    "System": {"color": "red", "icon": "⚠️", "badge": "bold red"},
}


def working(agent: str, task_desc: str):
    """Notify console and logger that an agent has started working."""
    logger.log_working(agent, task_desc)
    style = AGENT_STYLES.get(agent, {"color": "white", "icon": "⚙", "badge": "bold white"})
    console.print(f"[{style['badge']}]{style['icon']} {agent}[/] is {task_desc}...")


def turn(agent: str, content: str):
    """Display an agent's speech/output turn inside an aesthetic Rich panel."""
    logger.log_turn(agent, content)
    style = AGENT_STYLES.get(agent, {"color": "white", "icon": "🤖", "badge": "bold white"})
    title = f"{style['icon']}  {agent}"
    panel = Panel(
        Markdown(content),
        title=title,
        title_align="left",
        border_style=style["color"],
        padding=(1, 2),
    )
    console.print(panel)


def handoff(src_agent: str, dst_agent: str, payload_desc: str):
    """Display a clear, highlighted handoff between two collaborating agents."""
    logger.log_handoff(src_agent, dst_agent, payload_desc)
    src_style = AGENT_STYLES.get(src_agent, {"badge": "bold white"})["badge"]
    dst_style = AGENT_STYLES.get(dst_agent, {"badge": "bold white"})["badge"]
    console.print(
        f"\n[bold white on blue] ➜ HANDOFF [/] [{src_style}]{src_agent}[/] "
        f"──▶ [{dst_style}]{dst_agent}[/] [dim italic]({payload_desc})[/]\n"
    )


def warn(message: str):
    logger.log_warn(message)
    console.print(f"[bold yellow]⚠️  {message}[/]")


def error(message: str):
    logger.log_error(message)
    console.print(f"[bold red]❌  {message}[/]")


def ask(prompt: str) -> str:
    """Prompt the user for input with custom styling."""
    try:
        return console.input(f"[bold blue]❯ {prompt}[/] ").strip()
    except (EOFError, KeyboardInterrupt):
        return "/quit"


def print_score_table(grades: list, total_pct: int):
    """Render a clean summary table of quiz evaluation results."""
    table = Table(title=f"Assessment Results (Final Score: {total_pct}%)", border_style="cyan")
    table.add_column("Q#", justify="center", style="bold")
    table.add_column("Concept", style="dim")
    table.add_column("Score", justify="center")
    table.add_column("Feedback", style="white")

    for g in grades:
        score_badge = "[green]2/2 Correct[/]" if g.score == 2 else ("[yellow]1/2 Partial[/]" if g.score == 1 else "[red]0/2 Needs Work[/]")
        table.add_row(f"Q{g.question_id}", g.concept, score_badge, g.feedback)

    console.print(table)
