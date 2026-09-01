from __future__ import annotations

import os
from dataclasses import dataclass
import urllib.error
from urllib.parse import urlencode

from .transport import Transport, UrlLibTransport, decode_json_value

BASE_URL = "https://kosis.kr/openapi/Param/statisticsParameterData.do"


class KosisApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class KosisClient:
    api_key: str
    transport: Transport | None = None
    timeout: float = 20.0
    transport_attempts: int = 3

    @classmethod
    def from_environment(cls, *, transport: Transport | None = None) -> "KosisClient | None":
        api_key = os.environ.get("KOSIS_API_KEY", "").strip()
        return cls(api_key, transport) if api_key else None

    def statistics(
        self,
        *,
        org_id: str,
        table_id: str,
        object_l1: str,
        item_id: str,
        period_type: str,
        max_periods: int,
        object_l2: str | None = None,
    ) -> object:
        if self.transport_attempts < 1:
            raise ValueError("KOSIS transport_attempts must be at least 1")
        params: dict[str, str] = {
            "method": "getList",
            "apiKey": self.api_key,
            "format": "json",
            "orgId": org_id,
            "tblId": table_id,
            "objL1": object_l1,
            "itmId": item_id,
            "prdSe": period_type,
            "newEstPrdCnt": str(max_periods),
        }
        if object_l2:
            params["objL2"] = object_l2
        transport = self.transport or UrlLibTransport()
        response = None
        for attempt in range(self.transport_attempts):
            try:
                response = transport.request(
                    "GET",
                    f"{BASE_URL}?{urlencode(params)}",
                    {"Accept": "application/json", "User-Agent": "InsightDesk/2.0"},
                    timeout=self.timeout,
                )
                break
            except (urllib.error.URLError, TimeoutError, OSError):
                if attempt + 1 >= self.transport_attempts:
                    raise
        assert response is not None
        if not 200 <= response.status < 300:
            raise KosisApiError(f"KOSIS HTTP {response.status}")
        payload = decode_json_value(response)
        if isinstance(payload, dict):
            error_code = str(payload.get("err") or payload.get("errorCode") or "").strip()
            if error_code:
                raise KosisApiError(f"KOSIS API status {error_code}")
        if not isinstance(payload, (dict, list)):
            raise KosisApiError("KOSIS returned unsupported JSON")
        return payload
