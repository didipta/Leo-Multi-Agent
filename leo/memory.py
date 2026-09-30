"""Persistent student memory: tracks learning profile, past topics, scores, and mastery."""
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_MEMORY_DIR = Path(".leo_memory")
DEFAULT_MEMORY_PATH = DEFAULT_MEMORY_DIR / "student.json"


class StudentMemory:
    """Manages persistent session history and student context."""

    def __init__(self, path: Path = DEFAULT_MEMORY_PATH):
        self.path = path
        self.data: Dict[str, Any] = {"name": "", "history": []}
        self.load()

    def load(self):
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self.data = {"name": "", "history": []}

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        except OSError:
            pass

    @property
    def name(self) -> str:
        return self.data.get("name", "")

    def set_name(self, name: str):
        if name:
            self.data["name"] = name.strip()
            self.save()

    def record(self, topic: str, level: str, score_pct: int, weak: List[str]):
        entry = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "topic": topic,
            "level": level,
            "score": score_pct,
            "weak": weak,
        }
        self.data.setdefault("history", []).append(entry)
        # Keep last 25 sessions
        self.data["history"] = self.data["history"][-25:]
        self.save()

    def get_history(self) -> List[Dict[str, Any]]:
        return self.data.get("history", [])

    def context(self) -> str:
        """Formatted contextual string dynamically injected into agent backstories."""
        name = self.name or "Student"
        history = self.get_history()
        if not history:
            return f"Student name: {name}. This is their first learning session with Leo."

        recent = history[-3:]
        past_items = []
        for h in recent:
            weak_str = f"remedial areas: {', '.join(h['weak'])}" if h.get("weak") else "mastered cleanly"
            past_items.append(f"{h.get('topic')} ({h.get('level')}, score {h.get('score')}%, {weak_str})")

        return f"Student name: {name}. Past learning sessions: {'; '.join(past_items)}."

    def clear(self):
        self.data = {"name": "", "history": []}
        self.save()
