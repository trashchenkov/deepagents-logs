from __future__ import annotations

import os
from typing import Any

from deepagents_logs.core.session_logger import SessionArtifactLogger


class ProviderLoggingMixin:
    source_name = "provider"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._session_logger = SessionArtifactLogger()
        super().__init__(*args, **kwargs)

    def _current_cwd(self) -> str:
        return os.getcwd()

    def _ensure_session_id(self) -> str | None:
        try:
            from langgraph.config import get_config

            config = get_config()
            return str(config.get("configurable", {}).get("thread_id") or "").strip() or None
        except Exception:
            return None
