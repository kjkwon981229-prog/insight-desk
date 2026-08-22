from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlencode

from .cache import ResponseCache
from .transport import Transport, UrlLibTransport, decode_json_value

BASE_URL = "https://naverapihub.apigw.ntruss.com"
NEWS_PATH = "/search/v1/news"
TREND_PATH = "/search-trend/v1/search"


class NaverApiError(RuntimeError):
    def __init__(self, kind: str, message: str, status: int | None = None) -> None:
        self.kind = kind
        self.status = status
        super().__init__(message)


@dataclass(frozen=True)
class KeywordGroup:
    name: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class NaverCredentials:
    client_id: str
    client_secret: str

    @classmethod
    def from_environment(cls) -> "NaverCredentials | None":
        client_id = os.environ.get("NCP_CLIENT_ID", "").strip()
        client_secret = os.environ.get("NCP_CLIENT_SECRET", "").strip()
        if not client_id or not client_secret:
            return None
        return cls(client_id=client_id, client_secret=client_secret)


class NaverApiClient:
    def __init__(
        self,
        credentials: NaverCredentials,
        *,
        transport: Transport | None = None,
        cache: ResponseCache | None = None,
        timeout: float = 20.0,
    ) -> None:
        self.credentials = credentials
        self.transport = transport or UrlLibTransport()
        self.cache = cache
        self.timeout = timeout

    def _headers(self, content_type: str | None = None) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "X-NCP-APIGW-API-KEY-ID": self.credentials.client_id,
            "X-NCP-APIGW-API-KEY": self.credentials.client_secret,
        }
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        body: bytes | None = None,
        content_type: str | None = None,
    ) -> dict[str, object]:
        cache_key = ResponseCache.key(method, url, body)
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached
        try:
            response = self.transport.request(
                method, url, self._headers(content_type), body=body, timeout=self.timeout
            )
        except OSError as exc:
            raise NaverApiError("NETWORK", type(exc).__name__) from exc
        if response.status < 200 or response.status >= 300:
            kind = {400: "BAD_REQUEST", 401: "AUTH", 403: "PERMISSION", 429: "RATE_LIMIT"}.get(
                response.status, "HTTP"
            )
            raise NaverApiError(kind, f"NAVER API returned HTTP {response.status}", response.status)
        try:
            payload = decode_json_value(response)
        except ValueError as exc:
            raise NaverApiError("DATA_VALIDATION", str(exc), response.status) from exc
        if not isinstance(payload, dict):
            raise NaverApiError("DATA_VALIDATION", "NAVER API returned non-object JSON", response.status)
        if self.cache:
            self.cache.set(cache_key, payload)
        return payload

    def search_news(
        self,
        query: str,
        *,
        display: int = 100,
        start: int = 1,
        sort: str = "date",
    ) -> dict[str, object]:
        if sort not in {"sim", "date"}:
            raise ValueError("NAVER news sort must be sim or date")
        params = urlencode(
            {"query": query, "display": display, "start": start, "sort": sort, "format": "json"}
        )
        return self._request_json("GET", f"{BASE_URL}{NEWS_PATH}?{params}")

    def search_trend(
        self,
        groups: list[KeywordGroup],
        *,
        start_date: date,
        end_date: date,
        time_unit: str = "date",
    ) -> tuple[str, dict[str, object]]:
        batch_id = uuid.uuid4().hex[:12]
        body = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "timeUnit": time_unit,
            "keywordGroups": [
                {"groupName": group.name, "keywords": list(group.keywords)} for group in groups
            ],
        }
        encoded = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return batch_id, self._request_json(
            "POST", f"{BASE_URL}{TREND_PATH}", body=encoded, content_type="application/json"
        )
