from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


def to_serializable(value: Any):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return to_serializable(asdict(value))
    if hasattr(value, "model_dump"):
        try:
            return to_serializable(value.model_dump(exclude_none=True, by_alias=True))
        except TypeError:
            return to_serializable(value.model_dump())
    if isinstance(value, dict):
        return {str(k): to_serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_serializable(item) for item in value]
    if hasattr(value, "dict"):
        try:
            return to_serializable(value.dict())
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        return to_serializable(vars(value))
    return str(value)
