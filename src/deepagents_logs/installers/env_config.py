from __future__ import annotations

import os
from pathlib import Path

from deepagents_logs.core.env import merge_env_file, parse_env_file, write_env_file
from deepagents_logs.core.paths import DEFAULT_LOCAL_ROOT, DEFAULT_S3_BUCKET, DEEPAGENTS_ENV_PATH, LOGGING_ENV_PATH


LOGGING_ENV_ORDER = [
    "DEEPAGENTS_LOGS_ENABLED",
    "DEEPAGENTS_LOGS_LOCAL_ENABLED",
    "DEEPAGENTS_LOGS_S3_ENABLED",
    "DEEPAGENTS_LOGS_LOCAL_ROOT",
    "DEEPAGENTS_LOGS_INCLUDE_README",
    "DEEPAGENTS_LOGS_S3_BUCKET",
    "DEEPAGENTS_LOGS_S3_PREFIX",
    "DEEPAGENTS_LOGS_S3_REGION",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_ENDPOINT_URL",
]

LOGGING_ENV_COMMENTS = [
    "# Deep Agents logging config",
    "# Local and S3 export settings for deepagents-logs.",
]

GIGACHAT_TEMPLATE_COMMENTS = [
    "# Optional GigaChat env for Deep Agents CLI",
    "# Fill values as needed. Existing values are preserved.",
]


def install_logging_env(path: Path = LOGGING_ENV_PATH) -> None:
    merged = parse_env_file(path)
    for key, value in {
        "DEEPAGENTS_LOGS_ENABLED": "1",
        "DEEPAGENTS_LOGS_LOCAL_ENABLED": "1",
        "DEEPAGENTS_LOGS_S3_ENABLED": "0",
        "DEEPAGENTS_LOGS_LOCAL_ROOT": str(DEFAULT_LOCAL_ROOT),
        "DEEPAGENTS_LOGS_INCLUDE_README": "1",
        "DEEPAGENTS_LOGS_S3_BUCKET": DEFAULT_S3_BUCKET,
        "DEEPAGENTS_LOGS_S3_PREFIX": "",
        "DEEPAGENTS_LOGS_S3_REGION": "us-east-1",
        "AWS_ACCESS_KEY_ID": "",
        "AWS_SECRET_ACCESS_KEY": "",
        "AWS_ENDPOINT_URL": "",
    }.items():
        merged.setdefault(key, value)
    write_env_file(path, merged, comments=LOGGING_ENV_COMMENTS, ordering=LOGGING_ENV_ORDER)


def set_logging_toggle(key: str, enabled: bool, path: Path = LOGGING_ENV_PATH) -> None:
    merged = merge_env_file(path, {key: "1" if enabled else "0"})
    write_env_file(path, merged, comments=LOGGING_ENV_COMMENTS, ordering=LOGGING_ENV_ORDER)


def install_gigachat_env_template(path: Path = DEEPAGENTS_ENV_PATH) -> None:
    current = parse_env_file(path)
    for key in [
        "GIGACHAT_CREDENTIALS",
        "GIGACHAT_SCOPE",
        "GIGACHAT_USER",
        "GIGACHAT_PASSWORD",
        "GIGACHAT_VERIFY_SSL_CERTS",
        "GIGACHAT_CA_BUNDLE_FILE",
    ]:
        current.setdefault(key, "")
    write_env_file(path, current, comments=GIGACHAT_TEMPLATE_COMMENTS)


def install_pythonpath_bridge(repo_src: Path, path: Path = DEEPAGENTS_ENV_PATH) -> None:
    current = parse_env_file(path)
    entries = [entry for entry in current.get("PYTHONPATH", "").split(os.pathsep) if entry]
    repo_src_str = str(repo_src)
    if repo_src_str not in entries:
        entries.insert(0, repo_src_str)
    current["PYTHONPATH"] = os.pathsep.join(entries)
    write_env_file(path, current, comments=GIGACHAT_TEMPLATE_COMMENTS)
