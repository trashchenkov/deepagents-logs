from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .env import parse_env_file
from .paths import DEFAULT_LOCAL_ROOT, LOGGING_ENV_PATH


TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
SENSITIVE_EXACT_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credentials",
    "id_token",
    "password",
    "refresh_token",
    "secret",
    "token",
}
SENSITIVE_KEY_PARTS = (
    "authorization",
    "api_key",
    "credentials",
    "password",
    "secret",
    "access_token",
    "refresh_token",
    "id_token",
    "cookie",
)


@dataclass(frozen=True)
class LoggingConfig:
    enabled: bool
    local_enabled: bool
    s3_enabled: bool
    local_root: Path
    include_readme: bool
    endpoint: str
    region: str
    bucket: str
    prefix: str
    access_key_id: str
    secret_access_key: str
    upload_debug: bool


def parse_bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return default


def _merged_env() -> dict[str, str]:
    env = parse_env_file(LOGGING_ENV_PATH)
    env.update({k: v for k, v in os.environ.items() if k.startswith("DEEPAGENTS_LOGS_") or k.startswith("AWS_")})
    return env


def load_logging_config() -> LoggingConfig:
    env = _merged_env()
    enabled = parse_bool(env.get("DEEPAGENTS_LOGS_ENABLED"), True)
    local_enabled = enabled and parse_bool(env.get("DEEPAGENTS_LOGS_LOCAL_ENABLED"), True)
    s3_enabled = enabled and parse_bool(env.get("DEEPAGENTS_LOGS_S3_ENABLED"), False)
    local_root = Path(env.get("DEEPAGENTS_LOGS_LOCAL_ROOT", str(DEFAULT_LOCAL_ROOT))).expanduser()
    include_readme = parse_bool(env.get("DEEPAGENTS_LOGS_INCLUDE_README"), True)
    return LoggingConfig(
        enabled=enabled,
        local_enabled=local_enabled,
        s3_enabled=s3_enabled,
        local_root=local_root,
        include_readme=include_readme,
        endpoint=env.get("AWS_ENDPOINT_URL", "").strip(),
        region=env.get("DEEPAGENTS_LOGS_S3_REGION", env.get("AWS_DEFAULT_REGION", "us-east-1")).strip(),
        bucket=env.get("DEEPAGENTS_LOGS_S3_BUCKET", "").strip(),
        prefix=env.get("DEEPAGENTS_LOGS_S3_PREFIX", "").strip().strip("/"),
        access_key_id=env.get("AWS_ACCESS_KEY_ID", "").strip(),
        secret_access_key=env.get("AWS_SECRET_ACCESS_KEY", "").strip(),
        upload_debug=parse_bool(env.get("DEEPAGENTS_LOGS_UPLOAD_DEBUG"), False),
    )


def sensitive_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    return lowered in SENSITIVE_EXACT_KEYS or any(part in lowered for part in SENSITIVE_KEY_PARTS)
