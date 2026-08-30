from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from insight_desk.core import FailureKind, VerificationCheck

from .transport import JsonHttpTransport, ProviderConfigError, ProviderTransportError


CLOUDFLARE_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
CLOUDFLARE_VERIFIER_ID = "cloudflare"
_CLOUDFLARE_DAILY_FREE_ALLOCATION_CODE = 3036


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
        gemini_transport: JsonHttpTransport | None = None,
        env: dict[str, str] | None = None,
    ):
        """Build the logical primary-verifier slot from whichever zero-cost routes exist.

        Cloudflare remains the first route when fully configured. Gemini is the next route when its
        free-tier key is configured. Missing Cloudflare credentials are an availability state rather
        than a reason to abort construction; partially configured Cloudflare credentials remain a
        real configuration error and fail fast. The logical verifier id stays `cloudflare` so the
        frozen two-slot verification policy is unchanged.
        """

        from .gemini import GeminiClaimVerifier, GeminiStructuredClient
        from .resilience import FailoverClaimVerifier, UnavailableClaimVerifier

        source = dict(os.environ) if env is None else env
        account_id = str(source.get("CLOUDFLARE_ACCOUNT_ID", "")).strip()
        api_token = str(source.get("CLOUDFLARE_API_TOKEN", "")).strip()
        if bool(account_id) != bool(api_token):
            raise ProviderConfigError(
                "Cloudflare verifier requires both CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN"
            )

        routes: list[object] = []
        if account_id and api_token:
            routes.append(
                cls(
                    account_id=account_id,
                    api_token=api_token,
                    transport=transport or JsonHttpTransport(),
                )
            )

        if GeminiStructuredClient.configured(source):
            routes.append(
                GeminiClaimVerifier(
                    GeminiStructuredClient.from_env(
                        env=source,
                        transport=gemini_transport,
                    )
                )
            )

        if not routes:
            return UnavailableClaimVerifier(
                verifier_id=CLOUDFLARE_VERIFIER_ID,
                model_id="unavailable:external-primary",
                error_code="config_missing",
            )
        return FailoverClaimVerifier(
            verifier_id=CLOUDFLARE_VERIFIER_ID,
            routes=tuple(routes),
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
    def _is_daily_free_allocation_exhausted(exc: ProviderTransportError) -> bool:
        if exc.status_code != 429:
            return False
        try:
            payload = json.loads(exc.detail)
        except (json.JSONDecodeError, TypeError):
            payload = None
        if isinstance(payload, dict):
            errors = payload.get("errors")
            if isinstance(errors, list):
                for item in errors:
                    if isinstance(item, dict) and item.get("code") == _CLOUDFLARE_DAILY_FREE_ALLOCATION_CODE:
                        return True
        lowered = exc.detail.casefold()
        return "daily free allocation" in lowered or (
            "3036" in lowered and "allocation" in lowered
        )

    @classmethod
    def _error_code(cls, exc: ProviderTransportError) -> str:
        status = str(exc.status_code) if exc.status_code is not None else "none"
        if (
            exc.failure_kind is FailureKind.RATE_LIMITED
            and cls._is_daily_free_allocation_exhausted(exc)
        ):
            return f"{FailureKind.FREE_QUOTA_EXHAUSTED.value}:{status}"
        return f"{exc.failure_kind.value}:{status}"
