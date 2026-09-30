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

DEFAULT_MODEL = os.environ.get("LEO_MODEL", "gemini/gemini-3.5-flash").strip()


def get_llm():
    """Build and return configured CrewAI LLM instance."""
    from crewai import LLM

    gemini_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    openai_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    groq_key = (os.environ.get("GROQ_API_KEY") or "").strip()
    active_model = os.environ.get("LEO_MODEL", DEFAULT_MODEL).strip()

    if gemini_key and gemini_key not in ("your-key-here", "your-gemini-api-key-here"):
        return LLM(
            model=active_model if "gemini" in active_model else f"gemini/{active_model}",
            api_key=gemini_key,
            temperature=0.3,
        )
    elif openai_key:
        return LLM(
            model=active_model if active_model.startswith("gpt") else "gpt-4o-mini",
            api_key=openai_key,
            temperature=0.3,
        )
    elif groq_key:
        return LLM(
            model=active_model if "groq" in active_model else f"groq/{active_model}",
            api_key=groq_key,
            temperature=0.3,
        )
    else:
        return LLM(
            model=active_model,
            api_key=gemini_key or "missing-key",
            temperature=0.3,
        )


def check_api_key() -> bool:
    """Check if a valid API key is present."""
    k = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY") or os.environ.get("GROQ_API_KEY")
    return bool(k and k != "your-key-here" and len(k) > 10)
