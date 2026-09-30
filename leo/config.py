"""Configuration and LLM factory for Leo: Multi-Agent AI Tutor."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
load_dotenv(Path(__file__).parent.parent / ".env")

# Execution Parameters
TIMEOUT_S = int(os.environ.get("LEO_TIMEOUT", "90"))
RETRIES = int(os.environ.get("LEO_RETRIES", "2"))
MAX_RELEARN = int(os.environ.get("LEO_MAX_RELEARN", "2"))
PASS_PCT = int(os.environ.get("LEO_PASS_PCT", "70"))
N_QUESTIONS = int(os.environ.get("LEO_N_QUESTIONS", "4"))

DEFAULT_MODEL = os.environ.get("LEO_MODEL", "gemini/gemini-3.5-flash")


def get_llm():
    """Build and return configured CrewAI LLM instance."""
    from crewai import LLM

    gemini_key = os.environ.get("GEMINI_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    groq_key = os.environ.get("GROQ_API_KEY")

    if gemini_key and gemini_key != "your-key-here":
        return LLM(
            model=DEFAULT_MODEL if "gemini" in DEFAULT_MODEL else f"gemini/{DEFAULT_MODEL}",
            api_key=gemini_key,
            temperature=0.3,
        )
    elif openai_key:
        return LLM(
            model=os.environ.get("LEO_MODEL", "gpt-4o-mini"),
            api_key=openai_key,
            temperature=0.3,
        )
    elif groq_key:
        return LLM(
            model=os.environ.get("LEO_MODEL", "groq/llama-3.3-70b-versatile"),
            api_key=groq_key,
            temperature=0.3,
        )
    else:
        # Return fallback configuration or raise descriptive message
        return LLM(
            model=DEFAULT_MODEL,
            api_key=gemini_key or "missing-key",
            temperature=0.3,
        )


def check_api_key() -> bool:
    """Check if a valid API key is present."""
    k = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY") or os.environ.get("GROQ_API_KEY")
    return bool(k and k != "your-key-here" and len(k) > 10)
