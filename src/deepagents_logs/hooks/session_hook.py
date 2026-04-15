from __future__ import annotations

import os
from datetime import UTC, datetime
from getpass import getuser
from socket import gethostname
from typing import Any

from deepagents_logs.core.config import load_logging_config
from deepagents_logs.core.io import write_json
from deepagents_logs.core.layout import session_paths
from deepagents_logs.core.readme import build_readme
from deepagents_logs.core.session_logger import SessionArtifactLogger
from deepagents_logs.core.state import SessionStateStore


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class HookHandler:
    def __init__(self) -> None:
        self.config = load_logging_config()
        self.logger = SessionArtifactLogger(self.config)
        self.state_store = SessionStateStore(self.config)

    def handle(self, payload: dict[str, Any]) -> None:
        event = str(payload.get("event") or "").strip()
        if not event:
            return
        session_id = str(payload.get("thread_id") or payload.get("session_id") or "").strip()
        cwd = os.getcwd()
        if event == "session.start" and session_id:
            self._handle_session_start(session_id, payload, cwd)
        elif event == "session.end" and session_id:
            self._handle_session_end(session_id, payload, cwd)
        elif session_id:
            self._handle_session_event(session_id, payload, cwd)

    def _handle_session_start(self, session_id: str, payload: dict[str, Any], cwd: str) -> None:
        state = self.state_store.load(session_id)
        if state is None:
            state = self.state_store.ensure(session_id, cwd)
            state.started_at = now_iso()
            state.cwd = cwd
            state.user = getuser()
            state.hostname = gethostname()
            self.state_store.save(state)
        if self.config.local_enabled:
            paths = session_paths(self.config, session_id, state.started_at)
            write_json(paths.meta_path, state.to_dict())
        self.logger.append_hook_event(session_id, {"timestamp": now_iso(), **payload}, cwd)

    def _handle_session_event(self, session_id: str, payload: dict[str, Any], cwd: str) -> None:
        self.logger.append_hook_event(session_id, {"timestamp": now_iso(), **payload}, cwd)

    def _handle_session_end(self, session_id: str, payload: dict[str, Any], cwd: str) -> None:
        self.logger.append_hook_event(session_id, {"timestamp": now_iso(), **payload}, cwd)
        state = self.state_store.ensure(session_id, cwd)
        state.stopped_at = now_iso()
        self.state_store.save(state)
        if not self.config.local_enabled:
            return
        paths = session_paths(self.config, session_id, state.started_at)
        write_json(paths.meta_path, state.to_dict())
        if self.config.include_readme:
            paths.readme_path.write_text(build_readme(state))
            self.logger._upload_text(paths.readme_path, "text/markdown")
        self.logger._upload_text(paths.meta_path, "application/json")
