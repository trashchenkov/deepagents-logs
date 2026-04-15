from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .config import sensitive_key


REDACTED = "[REDACTED]"


def sanitize(value):
    if isinstance(value, dict):
        return {
            key: REDACTED if sensitive_key(str(key)) else sanitize(val)
            for key, val in value.items()
        }
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize(item) for item in value]
    return value


def redact_url(url: str) -> str:
    if not url:
        return url
    split = urlsplit(url)
    if not split.query:
        return url
    query = []
    for key, value in parse_qsl(split.query, keep_blank_values=True):
        query.append((key, REDACTED if sensitive_key(key) else value))
    return urlunsplit((split.scheme, split.netloc, split.path, urlencode(query), split.fragment))
