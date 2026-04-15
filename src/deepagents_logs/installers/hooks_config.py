from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deepagents_logs.core.paths import DEEPAGENTS_HOOKS_PATH


HOOK_EVENTS = [
    "session.start",
    "session.end",
    "task.complete",
    "user.prompt",
    "input.required",
    "permission.request",
    "tool.error",
    "context.offload",
    "context.compact",
]

def managed_hook_command() -> list[str]:
    return [
        str(Path.home() / ".local" / "share" / "uv" / "tools" / "deepagents-cli" / "bin" / "python"),
        "-m",
        "deepagents_logs.hooks.dispatcher",
    ]


def _legacy_hook_commands() -> list[list[str]]:
    return [["deepagents-logs-hook"], managed_hook_command()]


def load_hooks(path: Path = DEEPAGENTS_HOOKS_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"hooks": []}
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {"hooks": []}
    if not isinstance(payload, dict):
        return {"hooks": []}
    hooks = payload.get("hooks")
    if not isinstance(hooks, list):
        payload["hooks"] = []
    return payload


def install_hook(path: Path = DEEPAGENTS_HOOKS_PATH) -> None:
    payload = load_hooks(path)
    commands = _legacy_hook_commands()
    hooks = [hook for hook in payload["hooks"] if hook.get("command") not in commands]
    hooks.append({"command": managed_hook_command(), "events": HOOK_EVENTS})
    payload["hooks"] = hooks
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def remove_hook(path: Path = DEEPAGENTS_HOOKS_PATH) -> None:
    payload = load_hooks(path)
    commands = _legacy_hook_commands()
    payload["hooks"] = [hook for hook in payload["hooks"] if hook.get("command") not in commands]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
