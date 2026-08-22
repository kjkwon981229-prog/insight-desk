from __future__ import annotations

import os
from dataclasses import dataclass

from .transport import Transport, UrlLibTransport, decode_json_value

BASE_URL = "https://ecos.bok.or.kr/api/StatisticSearch"


class EcosApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class EcosClient:
    api_key: str
    transport: Transport | None = None
    timeout: float = 5.0

    @classmethod
    def from_environment(cls, *, transport: Transport | None = None) -> "EcosClient | None":
        api_key = os.environ.get("ECOS_API_KEY", "").strip()
        return cls(api_key, transport) if api_key else None

    def statistic_search(
        self,
        *,
        stat_code: str,
        cycle: str,
        start_period: str,
        end_period: str,
        max_rows: int = 100,
    ) -> dict[str, object]:
        url = "/".join(
            (
                BASE_URL,
                self.api_key,
                "json",
                "kr",
                "1",
                str(max_rows),
                stat_code,
                cycle,
                start_period,
                end_period,
            )
        ) + "/"
        response = (self.transport or UrlLibTransport()).request(
            "GET",
            url,
            {"Accept": "application/json", "User-Agent": "InsightDesk/2.0"},
            timeout=self.timeout,
        )
        if not 200 <= response.status < 300:
            raise EcosApiError(f"ECOS HTTP {response.status}")
        payload = decode_json_value(response)
        if not isinstance(payload, dict):
            raise EcosApiError("ECOS returned non-object JSON")
        if "StatisticSearch" not in payload:
            result = payload.get("RESULT")
            if isinstance(result, dict) and result.get("CODE"):
                raise EcosApiError(f"ECOS API status {result.get('CODE')}")
        return payload
