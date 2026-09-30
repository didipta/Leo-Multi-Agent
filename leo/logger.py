"""Professional logging infrastructure for Leo: Multi-Agent AI Tutor.

Provides:
1. Rotating file logger in `logs/leo.log`.
2. Colorized terminal output with agent badges.
3. In-memory event bus/history accessible by both CLI and Streamlit UI.
"""
from dataclasses import dataclass, field
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
from typing import List, Optional

LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)
LOG_FILE = LOGS_DIR / "leo.log"


@dataclass
class AgentEvent:
    timestamp: str
    event_type: str  # "turn", "handoff", "tool", "working", "warning", "info"
    agent: str
    target_agent: Optional[str] = None
    message: str = ""
    extra: dict = field(default_factory=dict)


class LeoLogger:
    """Singleton logger with file rotation and in-memory event buffer."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LeoLogger, cls).__new__(cls)
            cls._instance._init_logger()
        return cls._instance

    def _init_logger(self):
        self.events: List[AgentEvent] = []
        self.logger = logging.getLogger("leo_multi_agent")
        self.logger.setLevel(logging.DEBUG)

        # Avoid duplicate handlers on reload
        if self.logger.handlers:
            return

        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # 1. Rotating File Handler (up to 5MB, keep 3 backups)
        file_handler = RotatingFileHandler(
            LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def _record(self, event_type: str, agent: str, message: str, target: Optional[str] = None, **kwargs):
        ts = datetime.now().strftime("%H:%M:%S")
        event = AgentEvent(
            timestamp=ts,
            event_type=event_type,
            agent=agent,
            target_agent=target,
            message=message,
            extra=kwargs
        )
        self.events.append(event)
        # Keep last 250 in-memory events
        if len(self.events) > 250:
            self.events.pop(0)

    def log_working(self, agent: str, activity: str):
        msg = f"[{agent}] Working: {activity}"
        self.logger.info(msg)
        self._record("working", agent, activity)

    def log_turn(self, agent: str, text: str):
        preview = text[:150] + "..." if len(text) > 150 else text
        self.logger.info(f"[{agent}] Response: {preview}")
        self._record("turn", agent, text)

    def log_handoff(self, src: str, dst: str, description: str):
        msg = f"[HANDOFF] {src} ➔ {dst} | Data: {description}"
        self.logger.info(msg)
        self._record("handoff", src, description, target=dst)

    def log_tool(self, agent: str, tool_name: str, input_query: str, result_summary: str):
        msg = f"[{agent}] Tool '{tool_name}' invoked: '{input_query}' -> {result_summary}"
        self.logger.info(msg)
        self._record("tool", agent, f"Tool: {tool_name} | Query: {input_query}", tool_name=tool_name, summary=result_summary)

    def log_warn(self, message: str):
        self.logger.warning(message)
        self._record("warning", "System", message)

    def log_error(self, message: str, exc_info: bool = False):
        self.logger.error(message, exc_info=exc_info)
        self._record("error", "System", message)

    def get_events(self) -> List[AgentEvent]:
        return list(self.events)

    def clear_events(self):
        self.events.clear()


# Global logger instance
logger = LeoLogger()
