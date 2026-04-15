from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from .config import LoggingConfig, load_logging_config
from .io import append_jsonl, write_json
from .layout import iso_timestamp, pair_id, session_paths
from .readme import build_readme
from .redact import redact_url, sanitize
from .s3 import S3Mirror
from .serialize import to_serializable
from .state import SessionStateStore


@dataclass(frozen=True)
class ApiRequestRecord:
    timestamp: str
    sessionId: str
    source: str
    url: str
    method: str
    headers: dict[str, Any] | None
    body: Any


@dataclass(frozen=True)
class ApiResponseRecord:
    timestamp: str
    sessionId: str
    status: int | str | None
    headers: dict[str, Any] | None
    body: Any


class SessionArtifactLogger:
    def __init__(self, config: LoggingConfig | None = None):
        self.config = config or load_logging_config()
        self.state_store = SessionStateStore(self.config)
        self.s3 = S3Mirror(self.config)

    def ensure_state(self, session_id: str, cwd: str, agent_name: str | None = None):
        return self.state_store.ensure(session_id, cwd=cwd, agent_name=agent_name)

    def append_hook_event(self, session_id: str, event: dict[str, Any], cwd: str) -> None:
        if not self.config.enabled:
            return
        state = self.ensure_state(session_id, cwd)
        state.hook_events += 1
        self.state_store.save(state)
        if not self.config.local_enabled:
            return
        paths = session_paths(self.config, session_id, state.started_at)
        append_jsonl(paths.hook_events_path, sanitize(event))
        write_json(paths.meta_path, state.to_dict())
        self._upload_text(paths.hook_events_path, "application/json")
        self._upload_text(paths.meta_path, "application/json")

    def append_prompt(self, session_id: str, prompt_texts: list[str], *, timestamp: str, cwd: str) -> None:
        state = self.ensure_state(session_id, cwd)
        existing = {entry.get('text') for entry in state.prompts}
        changed = False
        for text in prompt_texts:
            if not text or text in existing:
                continue
            state.prompts.append({"text": text, "timestamp": timestamp})
            changed = True
        if changed:
            self.state_store.save(state)

    def register_model(self, session_id: str, model_name: str | None, *, cwd: str) -> None:
        if not model_name:
            return
        state = self.ensure_state(session_id, cwd)
        if model_name not in state.models:
            state.models.append(model_name)
            self.state_store.save(state)

    def finalize_session(self, session_id: str, *, cwd: str) -> None:
        state = self.ensure_state(session_id, cwd)
        state.stopped_at = iso_timestamp()
        self.state_store.save(state)
        if not self.config.local_enabled:
            return
        paths = session_paths(self.config, session_id, state.started_at)
        write_json(paths.meta_path, state.to_dict())
        if self.config.include_readme:
            paths.readme_path.write_text(build_readme(state))
            self._upload_text(paths.readme_path, "text/markdown")
        self._upload_text(paths.meta_path, "application/json")

    def log_api_pair(
        self,
        *,
        session_id: str,
        source: str,
        method: str,
        url: str,
        request_headers: dict[str, Any] | None,
        request_body: Any,
        response_status: int | str | None,
        response_headers: dict[str, Any] | None,
        response_body: Any,
        cwd: str,
        model_name: str | None = None,
    ) -> None:
        if not self.config.enabled:
            return
        state = self.ensure_state(session_id, cwd)
        if model_name:
            self.register_model(session_id, model_name, cwd=cwd)
        timestamp = iso_timestamp()
        log_id = pair_id()
        request_record = ApiRequestRecord(
            timestamp=timestamp,
            sessionId=session_id,
            source=source,
            url=redact_url(url),
            method=method,
            headers=sanitize(to_serializable(request_headers or {})),
            body=sanitize(to_serializable(request_body)),
        )
        response_record = ApiResponseRecord(
            timestamp=timestamp,
            sessionId=session_id,
            status=response_status,
            headers=sanitize(to_serializable(response_headers or {})),
            body=sanitize(to_serializable(response_body)),
        )
        state.request_count += 1
        state.response_count += 1
        self.state_store.save(state)
        if not self.config.local_enabled:
            return
        paths = session_paths(self.config, session_id, state.started_at)
        req_path = paths.session_dir / f"{timestamp}_{log_id}_request.json"
        res_path = paths.session_dir / f"{timestamp}_{log_id}_response.json"
        write_json(req_path, to_serializable(request_record))
        write_json(res_path, to_serializable(response_record))
        self._upload_text(req_path, "application/json")
        self._upload_text(res_path, "application/json")

    def _upload_text(self, path: Path, content_type: str) -> None:
        if not path.exists():
            return
        body = path.read_text()
        key = "/".join(path.relative_to(self.config.local_root).parts)
        self.s3.upload_text_async(key, body, content_type=content_type)


def absolute_url(base_url: str, maybe_relative: str) -> str:
    if maybe_relative.startswith("http://") or maybe_relative.startswith("https://"):
        return maybe_relative
    base = base_url if base_url.endswith("/") else f"{base_url}/"
    return urljoin(base, maybe_relative.lstrip("/"))


def build_request_body(kwargs: dict[str, Any]) -> Any:
    if "json" in kwargs:
        return kwargs["json"]
    if "data" in kwargs:
        return kwargs["data"]
    if "content" in kwargs:
        content = kwargs["content"]
        if isinstance(content, (bytes, bytearray)):
            try:
                return json.loads(content.decode("utf-8"))
            except Exception:
                return content.decode("utf-8", errors="replace")
        if isinstance(content, str):
            try:
                return json.loads(content)
            except Exception:
                return content
        return content
    if "auth" in kwargs:
        user, password = kwargs["auth"]
        return {"user": user, "password": password}
    return None
