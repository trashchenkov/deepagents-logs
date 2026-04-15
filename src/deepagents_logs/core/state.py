from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from getpass import getuser
from pathlib import Path
from typing import Any

from .config import LoggingConfig
from .layout import hostname, state_root
from .serialize import to_serializable


@dataclass
class SessionState:
    session_id: str
    started_at: str
    cwd: str
    user: str
    hostname: str
    agent_name: str | None = None
    stopped_at: str | None = None
    prompts: list[dict[str, str | None]] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    provider_events: list[dict[str, Any]] = field(default_factory=list)
    hook_events: int = 0
    request_count: int = 0
    response_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return to_serializable(self)


class SessionStateStore:
    def __init__(self, config: LoggingConfig):
        self.config = config

    def _path(self, session_id: str) -> Path:
        return state_root(self.config) / f"{session_id}.json"

    def load(self, session_id: str) -> SessionState | None:
        path = self._path(session_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text())
        return SessionState(**payload)

    def save(self, state: SessionState) -> None:
        path = self._path(state.session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2) + "\n")

    def ensure(self, session_id: str, cwd: str, agent_name: str | None = None) -> SessionState:
        existing = self.load(session_id)
        if existing is not None:
            if agent_name and not existing.agent_name:
                existing.agent_name = agent_name
                self.save(existing)
            return existing
        state = SessionState(
            session_id=session_id,
            started_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            cwd=cwd,
            user=getuser() or "unknown",
            hostname=hostname(),
            agent_name=agent_name,
        )
        self.save(state)
        return state
