from __future__ import annotations

from datetime import UTC, datetime
from getpass import getuser
from pathlib import Path
from socket import gethostname
from uuid import uuid4

from .config import LoggingConfig
from .paths import DEBUG_LOG_NAME, SessionPaths, STATE_DIR_NAME, UPLOAD_JOBS_DIR_NAME


def iso_timestamp(dt: datetime | None = None) -> str:
    value = (dt or datetime.now(UTC)).astimezone(UTC)
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z").replace(":", "-")


def session_prefix(started_at: str | None = None) -> str:
    dt = datetime.now(UTC)
    if started_at:
        try:
            dt = datetime.fromisoformat(started_at.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            dt = datetime.now(UTC)
    return f"{dt.year:04d}-{dt.month:02d}-{getuser()}"


def pair_id() -> str:
    return uuid4().hex[:8]


def session_paths(config: LoggingConfig, session_id: str, started_at: str | None = None) -> SessionPaths:
    session_dir = config.local_root / session_prefix(started_at) / session_id
    return SessionPaths(
        session_dir=session_dir,
        meta_path=session_dir / "session-meta.json",
        hook_events_path=session_dir / "hook-events.jsonl",
        readme_path=session_dir / "README.md",
    )


def state_root(config: LoggingConfig) -> Path:
    return config.local_root / STATE_DIR_NAME


def upload_jobs_root(config: LoggingConfig) -> Path:
    return state_root(config) / UPLOAD_JOBS_DIR_NAME


def debug_log_path(config: LoggingConfig) -> Path:
    return config.local_root / DEBUG_LOG_NAME


def hostname() -> str:
    return gethostname()
