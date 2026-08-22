from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from insight_desk.core import VerificationCheck

from .transport import JsonHttpTransport, ProviderTransportError, require_secret


CLOUDFLARE_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
CLOUDFLARE_VERIFIER_ID = "cloudflare"


@dataclass(slots=True)
class CloudflareClaimVerifier:
    account_id: str
    api_token: str
    transport: JsonHttpTransport
    verifier_id: str = CLOUDFLARE_VERIFIER_ID
    model_id: str = CLOUDFLARE_MODEL

    @classmethod
    def from_env(
        cls,
        *,
        transport: JsonHttpTransport | None = None,
        env: dict[str, str] | None = None,
    ) -> "CloudflareClaimVerifier":
        source = dict(os.environ) if env is None else env
        return cls(
            account_id=require_secret(source, "CLOUDFLARE_ACCOUNT_ID"),
            api_token=require_secret(source, "CLOUDFLARE_API_TOKEN"),
            transport=transport or JsonHttpTransport(),
        )

    def verify(
        self,
        *,
        check_id: str,
        claim_text: str,
        evidence_text: str,
        evidence_ids: tuple[str, ...],
    ) -> VerificationCheck:
        prompt = (
            "Judge whether the CLAIM is fully supported by the EVIDENCE only. "
            "Do not use outside knowledge. Time/state must match exactly: future is not completed, "
            "announced is not already happened, and different dates are different facts. "
            "Return entailed=true only when every material part of the claim is supported.\n\n"
            f"EVIDENCE:\n{evidence_text}\n\nCLAIM:\n{claim_text}"
        )
        schema = {
            "type": "object",
            "properties": {"entailed": {"type": "boolean"}},
            "required": ["entailed"],
            "additionalProperties": False,
        }
        try:
            response = self.transport.post_json(
                f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/ai/run/{self.model_id}",
                {
                    "messages": [
                        {
                            "role": "system",
                            "content": "Return only JSON matching the supplied schema.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "response_format": {"type": "json_schema", "json_schema": schema},
                    "max_tokens": 96,
                    "temperature": 0,
                },
                {"Authorization": f"Bearer {self.api_token}"},
            )
            entailed = self._extract_entailed(response)
            return VerificationCheck(
                check_id=check_id,
                verifier_id=self.verifier_id,
                model_id=self.model_id,
                evidence_ids=evidence_ids,
                entailed=entailed,
                zero_cost=True,
            )
        except ProviderTransportError as exc:
            return VerificationCheck(
                check_id=check_id,
                verifier_id=self.verifier_id,
                model_id=self.model_id,
                evidence_ids=evidence_ids,
                entailed=None,
                error_code=self._error_code(exc),
                zero_cost=True,
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return VerificationCheck(
                check_id=check_id,
                verifier_id=self.verifier_id,
                model_id=self.model_id,
                evidence_ids=evidence_ids,
                entailed=None,
                error_code="invalid_output",
                zero_cost=True,
            )

    @staticmethod
    def _extract_entailed(response: dict[str, Any]) -> bool:
        if response.get("success") is False:
            raise ValueError("Cloudflare success=false")
        result: Any = response.get("result", response)
        if isinstance(result, dict) and "response" in result:
            result = result["response"]
        if isinstance(result, str):
            result = json.loads(result)
        if not isinstance(result, dict):
            raise TypeError("Cloudflare response is not an object")
        value = result.get("entailed")
        if not isinstance(value, bool):
            raise TypeError("Cloudflare entailed is not boolean")
        return value

    @staticmethod
    def _error_code(exc: ProviderTransportError) -> str:
        status = str(exc.status_code) if exc.status_code is not None else "none"
        return f"{exc.failure_kind.value}:{status}"
