from __future__ import annotations

import re
from pathlib import Path

from deepagents_logs.core.paths import (
    DEEPAGENTS_CONFIG_PATH,
    DEFAULT_GIGACHAT_MODEL,
    DEFAULT_LOGGED_MODEL,
    GIGACHAT_MODELS,
    LOGGED_GIGACHAT_PROVIDER,
    LOGGED_LANGCHAIN_PROVIDER,
    MANAGED_BLOCK_END,
    MANAGED_BLOCK_START,
)


def normalize_logged_model(model: str, *, provider_hint: str | None = None) -> str:
    normalized = str(model).strip()
    if not normalized:
        return DEFAULT_LOGGED_MODEL
    if ":" in normalized or not provider_hint:
        return normalized
    return f"{provider_hint}:{normalized}"


def _managed_provider_block(default_model: str = DEFAULT_LOGGED_MODEL) -> str:
    return (
        f"{MANAGED_BLOCK_START}\n"
        f"[models.providers.{LOGGED_LANGCHAIN_PROVIDER}]\n"
        'class_path = "deepagents_logs.providers.langchain:LoggedLangChainModel"\n'
        f'models = ["{default_model}"]\n'
        "enabled = true\n\n"
        f"[models.providers.{LOGGED_LANGCHAIN_PROVIDER}.params]\n"
        "timeout = 120.0\n"
        "max_retries = 0\n\n"
        f"[models.providers.{LOGGED_LANGCHAIN_PROVIDER}.profile]\n"
        "tool_calling = true\n"
        f'default_model_hint = "{default_model}"\n'
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


def install_logged_langchain_provider(
    path: Path = DEEPAGENTS_CONFIG_PATH,
    *,
    default_model: str = DEFAULT_LOGGED_MODEL,
    set_default: bool = True,
) -> None:
    normalized_model = normalize_logged_model(default_model)
    logged_default = f"{LOGGED_LANGCHAIN_PROVIDER}:{normalized_model}"
    text = path.read_text() if path.exists() else ""
    text = _strip_managed_block(text)
    if set_default:
        text = _set_models_default(text, logged_default)
    text = text.rstrip() + "\n\n" + _managed_provider_block(normalized_model)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n")


def install_logged_gigachat_provider(
    path: Path = DEEPAGENTS_CONFIG_PATH,
    *,
    default_model: str = DEFAULT_GIGACHAT_MODEL,
    set_default: bool = True,
) -> None:
    install_logged_langchain_provider(
        path,
        default_model=normalize_logged_model(default_model, provider_hint="gigachat"),
        set_default=set_default,
    )


def remove_logged_provider(path: Path = DEEPAGENTS_CONFIG_PATH) -> None:
    if not path.exists():
        return
    path.write_text(_strip_managed_block(path.read_text()).rstrip() + "\n")


def langchain_logged_provider_installed(path: Path = DEEPAGENTS_CONFIG_PATH) -> bool:
    if not path.exists():
        return False
    text = path.read_text()
    return (
        f"[models.providers.{LOGGED_LANGCHAIN_PROVIDER}]" in text
        and "deepagents_logs.providers.langchain:LoggedLangChainModel" in text
    )


def legacy_logged_gigachat_provider_installed(path: Path = DEEPAGENTS_CONFIG_PATH) -> bool:
    if not path.exists():
        return False
    text = path.read_text()
    return (
        f"[models.providers.{LOGGED_GIGACHAT_PROVIDER}]" in text
        and "deepagents_logs.providers.gigachat:LoggedGigaChat" in text
    )


def logged_provider_installed(path: Path = DEEPAGENTS_CONFIG_PATH) -> bool:
    return (
        langchain_logged_provider_installed(path)
        or legacy_logged_gigachat_provider_installed(path)
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


__all__ = [
    "configured_default_model",
    "install_logged_gigachat_provider",
    "install_logged_langchain_provider",
    "langchain_logged_provider_installed",
    "legacy_logged_gigachat_provider_installed",
    "logged_provider_installed",
    "normalize_logged_model",
    "remove_logged_provider",
    "GIGACHAT_MODELS",
]
