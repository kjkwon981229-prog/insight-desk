from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any


_SECRET_KEY_PATTERN = re.compile(r"(?i)(client[_-]?(?:id|secret)|api[_-]?key|authorization|token|password)")


def redact_text(text: str, secrets: Iterable[str] = ()) -> str:
    redacted = text
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def redact_error(error: BaseException, secrets: Iterable[str] = ()) -> str:
    return redact_text(f"{type(error).__name__}: {error}", secrets)[:500]


def redact_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, item in value.items():
        if _SECRET_KEY_PATTERN.search(str(key)):
            output[str(key)] = "[REDACTED]"
        elif isinstance(item, Mapping):
            output[str(key)] = redact_mapping(item)
        elif isinstance(item, list):
            output[str(key)] = [redact_mapping(x) if isinstance(x, Mapping) else x for x in item]
        else:
            output[str(key)] = item
    return output


def assert_no_secret_values(value: Any, secrets: Iterable[str]) -> None:
    """Raise if a serialized value contains a configured secret."""

    text = str(value)
    for secret in secrets:
        if secret and secret in text:
            raise ValueError("secret value detected in generated output")
