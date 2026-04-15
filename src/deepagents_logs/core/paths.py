from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


HOME = Path.home()
DEEPAGENTS_DIR = HOME / ".deepagents"
DEEPAGENTS_CONFIG_PATH = DEEPAGENTS_DIR / "config.toml"
DEEPAGENTS_ENV_PATH = DEEPAGENTS_DIR / ".env"
DEEPAGENTS_HOOKS_PATH = DEEPAGENTS_DIR / "hooks.json"
LOGGING_ENV_PATH = HOME / ".config" / "deepagents-logs.env"
DEFAULT_LOCAL_ROOT = DEEPAGENTS_DIR / "log-export"
DEFAULT_S3_BUCKET = "bucket-deepagents-logs"
STATE_DIR_NAME = "state"
UPLOAD_JOBS_DIR_NAME = "upload-jobs"
DEBUG_LOG_NAME = "debug.log"
MANAGED_BLOCK_START = "# BEGIN deepagents-logs managed block"
MANAGED_BLOCK_END = "# END deepagents-logs managed block"
LOGGED_LANGCHAIN_PROVIDER = "langchain_logged"
LOGGED_GIGACHAT_PROVIDER = "gigachat_logged"
DEFAULT_GIGACHAT_MODEL = "GigaChat-2-Max"
DEFAULT_LOGGED_MODEL = f"gigachat:{DEFAULT_GIGACHAT_MODEL}"
GIGACHAT_MODELS = [
    "GigaChat-2-Lite",
    "GigaChat-2-Pro",
    "GigaChat-2-Max",
    "GigaChat-3-Ultra",
]


@dataclass(frozen=True)
class SessionPaths:
    session_dir: Path
    meta_path: Path
    hook_events_path: Path
    readme_path: Path


__all__ = [
    "DEBUG_LOG_NAME",
    "DEFAULT_GIGACHAT_MODEL",
    "DEFAULT_LOCAL_ROOT",
    "DEFAULT_LOGGED_MODEL",
    "DEFAULT_S3_BUCKET",
    "DEEPAGENTS_CONFIG_PATH",
    "DEEPAGENTS_DIR",
    "DEEPAGENTS_ENV_PATH",
    "DEEPAGENTS_HOOKS_PATH",
    "GIGACHAT_MODELS",
    "HOME",
    "LOGGED_GIGACHAT_PROVIDER",
    "LOGGED_LANGCHAIN_PROVIDER",
    "LOGGING_ENV_PATH",
    "MANAGED_BLOCK_END",
    "MANAGED_BLOCK_START",
    "SessionPaths",
    "STATE_DIR_NAME",
    "UPLOAD_JOBS_DIR_NAME",
]
