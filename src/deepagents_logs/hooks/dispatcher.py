from __future__ import annotations

import json
import sys

from deepagents_logs.hooks.session_hook import HookHandler


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        return 0
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return 0
    if not isinstance(payload, dict):
        return 0
    HookHandler().handle(payload)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
