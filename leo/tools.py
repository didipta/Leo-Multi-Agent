"""Optional pedagogical tools (Module 22): Web Search and Calculator."""
import math
from typing import Optional
from crewai.tools import tool
from .logger import logger


@tool("web_search")
def web_search(query: str) -> str:
    """Search the web for up-to-date definitions, facts, or technical examples.
    Useful when clarifying recent technologies or domain-specific topics."""
    logger.log_working("SearchTool", f"Searching web for: {query}")
    try:
        from duckduckgo_search import DDGS
        results = DDGS().text(query, max_results=3)
        if not results:
            return f"No direct search results found for '{query}'."
        snippets = []
        for r in results:
            snippets.append(f"- **{r.get('title', '')}**: {r.get('body', '')}")
        res = "\n".join(snippets)
        logger.log_tool("SearchTool", "web_search", query, f"Found {len(results)} results")
        return res
    except Exception as e:
        logger.log_warn(f"Web search tool failed: {e}")
        return f"Web search unavailable: {e}"


@tool("calculator")
def calculator(expression: str) -> str:
    """Safely evaluate mathematical expressions for science, coding, or math lessons.
    Examples: '2 ** 8', '1024 / 8', 'math.sqrt(144)'."""
    logger.log_working("CalculatorTool", f"Evaluating: {expression}")
    safe_dict = {
        "math": math,
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "pow": pow,
        "sum": sum,
    }
    try:
        # evaluate in restricted scope
        cleaned = expression.strip().replace("^", "**")
        result = eval(cleaned, {"__builtins__": {}}, safe_dict)
        res_str = str(result)
        logger.log_tool("CalculatorTool", "calculator", expression, f"Result = {res_str}")
        return f"Calculation result: {res_str}"
    except Exception as e:
        logger.log_warn(f"Calculator failed for expression '{expression}': {e}")
        return f"Invalid expression: {e}"


AVAILABLE_TOOLS = [web_search, calculator]
