from __future__ import annotations

from pathlib import Path
from typing import Iterable


def clean_env_value(value: str) -> str:
    value = value.strip()
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        result[key] = clean_env_value(value)
    return result


def write_env_file(
    path: Path,
    values: dict[str, str],
    *,
    comments: Iterable[str] | None = None,
    ordering: Iterable[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if comments:
        for comment in comments:
            lines.append(comment)
    seen: set[str] = set()
    if ordering:
        for key in ordering:
            if key in values:
                lines.append(f"{key}={values[key]}")
                seen.add(key)
    for key in sorted(values):
        if key in seen:
            continue
        lines.append(f"{key}={values[key]}")
    path.write_text("\n".join(lines).rstrip() + "\n")


def merge_env_file(path: Path, updates: dict[str, str]) -> dict[str, str]:
    current = parse_env_file(path)
    current.update(updates)
    return current
