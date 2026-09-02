from __future__ import annotations

import os
from dataclasses import dataclass
import urllib.error
from urllib.parse import urlencode

from .transport import Transport, UrlLibTransport, decode_json_value

BASE_URL = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
_PROBE_OUTPUT_FIELDS_ENV = "INSIGHT_DESK_KOSIS_PROBE_OUTPUT_FIELDS"


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
        output_fields: tuple[str, ...] | None = None,
    ) -> object:
        if self.transport_attempts < 1:
            raise ValueError("KOSIS transport_attempts must be at least 1")
        requested_fields = output_fields
        if requested_fields is None:
            probe_fields = os.environ.get(_PROBE_OUTPUT_FIELDS_ENV, "").strip()
            requested_fields = tuple(probe_fields.split()) if probe_fields else None
        if requested_fields is not None:
            normalized_fields = tuple(field.strip() for field in requested_fields)
            if not normalized_fields or any(not field for field in normalized_fields):
                raise ValueError("KOSIS output_fields must contain non-empty field names")
        else:
            normalized_fields = ()
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
        if normalized_fields:
            # KOSIS documents outputFields as an optional response-field selector. A space-separated
            # value is encoded as '+' by urlencode, matching the URL-generator form contract.
            params["outputFields"] = " ".join(normalized_fields)
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
