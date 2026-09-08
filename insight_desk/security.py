from __future__ import annotations

import os
import re
from collections.abc import Iterable, Mapping
from typing import Any


_SECRET_KEY_PATTERN = re.compile(r"(?i)(client[_-]?(?:id|secret)|api[_-]?key|authorization|token|password)")

# Keep the production credential classes in one immutable registry.  Callers
# may add explicit values (for example credentials supplied by a test double),
# but no initialization path may replace the environment-derived union with a
# narrower tuple.
SECRET_ENV_NAMES = (
    "NCP_CLIENT_ID",
    "NCP_CLIENT_SECRET",
    "OPENDART_API_KEY",
    "KOSIS_API_KEY",
    "ECOS_API_KEY",
    "VAPID_PRIVATE_KEY",
    "PUSH_PAIR_TOKEN",
    "PUSH_SEND_TOKEN",
)


def configured_secret_values(
    *explicit_values: str,
    environment: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    """Return the deduplicated union of all configured secret values.

    The optional environment mapping exists for deterministic tests.  The
    production path always uses ``os.environ`` and preserves every configured
    secret even when a client object is constructed later in the run.
    """

    source = os.environ if environment is None else environment
    values = [source.get(name, "") for name in SECRET_ENV_NAMES]
    values.extend(explicit_values)
    result: list[str] = []
    for value in values:
        normalized = str(value or "")
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


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


def scan_secret_values(root: "os.PathLike[str] | str", secrets: Iterable[str]) -> tuple[str, ...]:
    """Scan every generated file below *root* without exposing secret values.

    Byte scanning is intentional: it covers JSON, HTML, JavaScript, logs,
    archives, and otherwise-unexpected generated files while remaining safe
    for binary assets.  Returned errors contain paths only.
    """

    root_path = os.fspath(root)
    needles = tuple(
        value.encode("utf-8")
        for value in secrets
        if value
    )
    if not needles or not os.path.isdir(root_path):
        return ()
    errors: list[str] = []
    for directory, _, filenames in os.walk(root_path):
        for filename in filenames:
            path = os.path.join(directory, filename)
            try:
                with open(path, "rb") as handle:
                    content = handle.read()
            except OSError:
                continue
            if any(needle in content for needle in needles):
                errors.append(f"secret detected in generated tree: {os.path.relpath(path, root_path)}")
    return tuple(sorted(errors))
