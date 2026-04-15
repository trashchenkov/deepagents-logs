from __future__ import annotations

import re
from pathlib import Path

from deepagents_logs.core.paths import (
    DEEPAGENTS_CONFIG_PATH,
    DEFAULT_GIGACHAT_MODEL,
    GIGACHAT_MODELS,
    LOGGED_GIGACHAT_PROVIDER,
    MANAGED_BLOCK_END,
    MANAGED_BLOCK_START,
)


def _managed_provider_block(default_model: str = DEFAULT_GIGACHAT_MODEL) -> str:
    models_literal = ", ".join(f'"{name}"' for name in GIGACHAT_MODELS)
    return (
        f"{MANAGED_BLOCK_START}\n"
        f"[models.providers.{LOGGED_GIGACHAT_PROVIDER}]\n"
        "class_path = \"deepagents_logs.providers.gigachat:LoggedGigaChat\"\n"
        f"models = [{models_literal}]\n"
        "enabled = true\n\n"
        f"[models.providers.{LOGGED_GIGACHAT_PROVIDER}.params]\n"
        "timeout = 120.0\n"
        "max_retries = 0\n\n"
        f"[models.providers.{LOGGED_GIGACHAT_PROVIDER}.profile]\n"
        "tool_calling = true\n"
        f"default_model_hint = \"{default_model}\"\n"
        f"{MANAGED_BLOCK_END}\n"
    )


def _strip_managed_block(text: str) -> str:
    pattern = re.compile(
        rf"\n?{re.escape(MANAGED_BLOCK_START)}.*?{re.escape(MANAGED_BLOCK_END)}\n?",
        re.DOTALL,
    )
    return pattern.sub("\n", text).rstrip() + ("\n" if text else "")


def _set_models_default(text: str, default_spec: str) -> str:
    section_pattern = re.compile(r"(?ms)^\[models\]\n(?P<body>.*?)(?=^\[|\Z)")
    match = section_pattern.search(text)
    if not match:
        prefix = f"[models]\ndefault = \"{default_spec}\"\n\n"
        return prefix + text.lstrip()
    body = match.group("body")
    if re.search(r"(?m)^default\s*=", body):
        body = re.sub(r'(?m)^default\s*=.*$', f'default = "{default_spec}"', body)
    else:
        body = f'default = "{default_spec}"\n' + body
    return text[: match.start("body")] + body + text[match.end("body") :]


def install_logged_gigachat_provider(
    path: Path = DEEPAGENTS_CONFIG_PATH,
    *,
    default_model: str = DEFAULT_GIGACHAT_MODEL,
    set_default: bool = True,
) -> None:
    text = path.read_text() if path.exists() else ""
    text = _strip_managed_block(text)
    if set_default:
        text = _set_models_default(text, f"{LOGGED_GIGACHAT_PROVIDER}:{default_model}")
    text = text.rstrip() + "\n\n" + _managed_provider_block(default_model)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n")


def remove_logged_provider(path: Path = DEEPAGENTS_CONFIG_PATH) -> None:
    if not path.exists():
        return
    path.write_text(_strip_managed_block(path.read_text()).rstrip() + "\n")


def logged_provider_installed(path: Path = DEEPAGENTS_CONFIG_PATH) -> bool:
    if not path.exists():
        return False
    text = path.read_text()
    return (
        MANAGED_BLOCK_START in text
        and MANAGED_BLOCK_END in text
        and "deepagents_logs.providers.gigachat:LoggedGigaChat" in text
    )


def configured_default_model(path: Path = DEEPAGENTS_CONFIG_PATH) -> str | None:
    if not path.exists():
        return None
    section_pattern = re.compile(r"(?ms)^\[models\]\n(?P<body>.*?)(?=^\[|\Z)")
    match = section_pattern.search(path.read_text())
    if not match:
        return None
    default_match = re.search(r'(?m)^default\s*=\s*"(?P<value>[^"]+)"', match.group("body"))
    if not default_match:
        return None
    return default_match.group("value")
