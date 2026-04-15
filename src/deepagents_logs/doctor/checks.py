from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deepagents_logs.core.config import load_logging_config
from deepagents_logs.core.paths import DEEPAGENTS_CONFIG_PATH, DEEPAGENTS_HOOKS_PATH, LOGGING_ENV_PATH
from deepagents_logs.installers.deepagents_config import logged_provider_installed
from deepagents_logs.installers.hooks_config import managed_hook_command


@dataclass(frozen=True)
class DoctorResult:
    ok: bool
    checks: list[dict[str, Any]]


def run_doctor() -> DoctorResult:
    checks: list[dict[str, Any]] = []
    checks.append({"name": "deepagents config", "ok": DEEPAGENTS_CONFIG_PATH.exists()})
    checks.append({"name": "logging env", "ok": LOGGING_ENV_PATH.exists()})
    hooks_ok = False
    command = managed_hook_command()
    if DEEPAGENTS_HOOKS_PATH.exists():
        try:
            payload = json.loads(DEEPAGENTS_HOOKS_PATH.read_text())
            hooks_ok = any(hook.get("command") == command for hook in payload.get("hooks", []))
        except Exception:
            hooks_ok = False
    checks.append({"name": "hook installed", "ok": hooks_ok})
    checks.append({"name": "hook python exists", "ok": Path(command[0]).exists()})
    config = load_logging_config()
    checks.append({"name": "local root configured", "ok": bool(config.local_root)})
    checks.append({
        "name": "s3 fully configured when s3 enabled",
        "ok": (
            not config.s3_enabled
            or bool(config.bucket and config.endpoint and config.access_key_id and config.secret_access_key)
        ),
    })
    checks.append({
        "name": "optional logged model adapter status",
        "ok": True,
        "installed": logged_provider_installed(),
    })

    deepagents_python = Path.home() / ".local" / "share" / "uv" / "tools" / "deepagents-cli" / "bin" / "python"
    import_ok = False
    if deepagents_python.exists():
        proc = subprocess.run(
            [str(deepagents_python), "-c", "import deepagents_logs; print('ok')"],
            capture_output=True,
            text=True,
            check=False,
        )
        import_ok = proc.returncode == 0
    checks.append({"name": "deepagents tool env imports deepagents_logs", "ok": import_ok})
    return DoctorResult(ok=all(bool(item["ok"]) for item in checks), checks=checks)
