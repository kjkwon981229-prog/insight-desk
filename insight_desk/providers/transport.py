from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from insight_desk.core import FailureKind


class ProviderConfigError(ValueError):
    """Raised when required zero-cost provider configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class ProviderTransportError(RuntimeError):
    failure_kind: FailureKind
    status_code: int | None = None
    detail: str = ""
    retry_after_seconds: float | None = None

    def __str__(self) -> str:
        status = f" status={self.status_code}" if self.status_code is not None else ""
        detail = f" detail={self.detail}" if self.detail else ""
        retry = (
            f" retry_after={self.retry_after_seconds}"
            if self.retry_after_seconds is not None
            else ""
        )
        return f"provider transport failure={self.failure_kind.value}{status}{retry}{detail}"


def require_secret(env: dict[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ProviderConfigError(f"missing provider credential: {name}")
    return value


def _retry_after_seconds(headers: Any) -> float | None:
    value = headers.get("Retry-After") if headers is not None else None
    if value is None:
        return None
    try:
        seconds = float(str(value).strip())
    except ValueError:
        return None
    return max(0.0, seconds)


class JsonHttpTransport:
    """Small stdlib-only JSON transport shared by production provider adapters.

    The transport does not guess provider-specific quota semantics. Generic HTTP 429 means only
    RATE_LIMITED here. A provider adapter may specialize a 429 into a longer-lived quota state when
    the provider response explicitly proves that condition.
    """

    def __init__(
        self,
        *,
        user_agent: str = "insight-desk/0.4",
        attempts: int = 2,
        timeout_seconds: int = 90,
        opener: Callable[..., Any] = urllib.request.urlopen,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if attempts < 1:
            raise ValueError("attempts must be >= 1")
        if timeout_seconds < 1:
            raise ValueError("timeout_seconds must be >= 1")
        self.user_agent = user_agent
        self.attempts = attempts
        self.timeout_seconds = timeout_seconds
        self._opener = opener
        self._sleeper = sleeper

    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": self.user_agent,
            **headers,
        }

        for attempt in range(self.attempts):
            request = urllib.request.Request(
                url,
                data=body,
                headers=request_headers,
                method="POST",
            )
            try:
                with self._opener(request, timeout=self.timeout_seconds) as response:
                    raw = response.read().decode("utf-8")
                decoded = json.loads(raw)
                if not isinstance(decoded, dict):
                    raise ProviderTransportError(
                        failure_kind=FailureKind.INVALID_OUTPUT,
                        detail="provider JSON root is not an object",
                    )
                return decoded
            except ProviderTransportError:
                raise
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:1200]
                retry_after = _retry_after_seconds(exc.headers)
                if exc.code == 429:
                    kind = FailureKind.RATE_LIMITED
                elif exc.code in {500, 502, 503, 504}:
                    kind = FailureKind.TRANSIENT_PROVIDER
                else:
                    kind = FailureKind.INVALID_OUTPUT
                if attempt + 1 >= self.attempts or kind is FailureKind.INVALID_OUTPUT:
                    raise ProviderTransportError(
                        failure_kind=kind,
                        status_code=exc.code,
                        detail=detail,
                        retry_after_seconds=retry_after,
                    ) from exc
                delay = retry_after if retry_after is not None else float(2**attempt)
                self._sleeper(min(delay, 30.0))
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt + 1 >= self.attempts:
                    raise ProviderTransportError(
                        failure_kind=FailureKind.TRANSIENT_PROVIDER,
                        detail=str(exc)[:500],
                    ) from exc
                self._sleeper(float(2**attempt))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ProviderTransportError(
                    failure_kind=FailureKind.INVALID_OUTPUT,
                    detail=str(exc)[:500],
                ) from exc

        raise AssertionError("unreachable provider transport state")
