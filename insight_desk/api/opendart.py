from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlencode

from .transport import Transport, UrlLibTransport, decode_json_value

BASE_URL = "https://opendart.fss.or.kr/api/list.json"


class OpenDartApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class OpenDartClient:
    api_key: str
    transport: Transport | None = None
    timeout: float = 5.0

    @classmethod
    def from_environment(cls, *, transport: Transport | None = None) -> "OpenDartClient | None":
        api_key = os.environ.get("OPENDART_API_KEY", "").strip()
        return cls(api_key, transport) if api_key else None

    def list_filings(
        self,
        *,
        corp_code: str,
        begin_date: date,
        end_date: date,
        disclosure_type: str = "A",
        page_no: int = 1,
        page_count: int = 100,
    ) -> dict[str, object]:
        query = urlencode(
            {
                "crtfc_key": self.api_key,
                "corp_code": corp_code,
                "bgn_de": begin_date.strftime("%Y%m%d"),
                "end_de": end_date.strftime("%Y%m%d"),
                "pblntf_ty": disclosure_type,
                "sort": "date",
                "sort_mth": "desc",
                "page_no": str(page_no),
                "page_count": str(page_count),
            }
        )
        response = (self.transport or UrlLibTransport()).request(
            "GET",
            f"{BASE_URL}?{query}",
            {"Accept": "application/json", "User-Agent": "InsightDesk/2.0"},
            timeout=self.timeout,
        )
        if not 200 <= response.status < 300:
            raise OpenDartApiError(f"OpenDART HTTP {response.status}")
        payload = decode_json_value(response)
        if not isinstance(payload, dict):
            raise OpenDartApiError("OpenDART returned non-object JSON")
        status = str(payload.get("status") or "").strip()
        # OpenDART documents 013 as a valid empty-result response. Treating it as a provider
        # failure makes a quiet disclosure window indistinguishable from authentication or
        # transport failure and pollutes the enrichment error audit.
        if status == "013":
            return {**payload, "list": []}
        if status and status != "000":
            raise OpenDartApiError(f"OpenDART API status {status}")
        return payload
