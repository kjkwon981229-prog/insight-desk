from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from insight_desk.core import VerificationCheck
from insight_desk.generation import (
    GENERATION_SCHEMA,
    GeneratedDraft,
    GenerationContractError,
    GenerationRequest,
    build_generation_prompt,
    validate_generated_actor_preservation,
)

from .transport import JsonHttpTransport, ProviderTransportError, require_secret


GEMINI_FLASH_LITE = "gemini-3.1-flash-lite"
GEMINI_VERIFIER_ID = "gemini"
GEMINI_INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"


@dataclass(slots=True)
class GeminiStructuredClient:
    api_key: str
    model_id: str = GEMINI_FLASH_LITE
    transport: JsonHttpTransport | None = None

    def __post_init__(self) -> None:
        if self.model_id != GEMINI_FLASH_LITE:
            raise ValueError("Gemini zero-cost route is frozen to gemini-3.1-flash-lite")
        if self.transport is None:
            self.transport = JsonHttpTransport()

    @classmethod
    def from_env(
        cls,
        *,
        env: dict[str, str] | None = None,
        transport: JsonHttpTransport | None = None,
    ) -> "GeminiStructuredClient":
        source = dict(os.environ) if env is None else env
        return cls(
            api_key=require_secret(source, "GEMINI_API_KEY"),
            transport=transport,
        )

    @staticmethod
    def configured(env: dict[str, str] | None = None) -> bool:
        source = os.environ if env is None else env
        return bool(str(source.get("GEMINI_API_KEY", "")).strip())

    def structured_json(
        self,
        *,
        prompt: str,
        schema: dict[str, object],
        schema_name: str,
        system_prompt: str = "Follow the JSON schema exactly. Do not output commentary.",
    ) -> dict[str, object]:
        del schema_name
        assert self.transport is not None
        response = self.transport.post_json(
            GEMINI_INTERACTIONS_URL,
            {
                "model": self.model_id,
                "input": system_prompt + "\n\n" + prompt,
                "response_format": {
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": schema,
                },
            },
            {"x-goog-api-key": self.api_key},
        )
        return self._extract_json(response)

    @staticmethod
    def _extract_json(response: dict[str, Any]) -> dict[str, object]:
        steps = response.get("steps")
        if not isinstance(steps, list) or not steps:
            raise ValueError("Gemini interaction has no steps")
        text_parts: list[str] = []
        for step in steps:
            if not isinstance(step, dict) or step.get("type") != "model_output":
                continue
            content = step.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict) or part.get("type") != "text":
                    continue
                text = part.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
        text = "".join(text_parts).strip()
        if not text:
            raise ValueError("Gemini interaction has no model text")
        decoded = json.loads(text)
        if not isinstance(decoded, dict):
            raise TypeError("Gemini structured output root is not an object")
        return decoded


@dataclass(slots=True)
class GeminiBriefingGenerator:
    client: GeminiStructuredClient

    def generate(self, request: GenerationRequest) -> GeneratedDraft:
        result = self.client.structured_json(
            prompt=build_generation_prompt(request),
            schema=GENERATION_SCHEMA,
            schema_name="insight_desk_briefing_generation",
            system_prompt=(
                "Write only evidence-grounded Korean briefing text. "
                "Return JSON matching the schema exactly."
            ),
        )
        headline = result.get("headline")
        summary = result.get("summary")
        if not isinstance(headline, str) or not isinstance(summary, str):
            raise GenerationContractError(
                "Gemini generation output is outside headline/summary contract"
            )
        draft = GeneratedDraft(
            event_id=request.event.event_id,
            headline=headline,
            summary=summary,
            evidence_ids=request.evidence_ids,
        )
        validate_generated_actor_preservation(request, draft)
        return draft


@dataclass(slots=True)
class GeminiClaimVerifier:
    client: GeminiStructuredClient
    verifier_id: str = GEMINI_VERIFIER_ID

    @property
    def model_id(self) -> str:
        return self.client.model_id

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
            "Do not use outside knowledge. Time/state must match exactly. "
            "Return entailed=true only when every material part is supported.\n\n"
            f"EVIDENCE:\n{evidence_text}\n\nCLAIM:\n{claim_text}"
        )
        try:
            result = self.client.structured_json(
                prompt=prompt,
                schema={
                    "type": "object",
                    "properties": {"entailed": {"type": "boolean"}},
                    "required": ["entailed"],
                    "additionalProperties": False,
                },
                schema_name="insight_desk_claim_verification",
                system_prompt="Return only the evidence-grounded entailment JSON.",
            )
            entailed = result.get("entailed")
            if not isinstance(entailed, bool):
                raise TypeError("Gemini entailed is not boolean")
            return VerificationCheck(
                check_id=check_id,
                verifier_id=self.verifier_id,
                model_id=self.model_id,
                evidence_ids=evidence_ids,
                entailed=entailed,
                zero_cost=True,
            )
        except ProviderTransportError as exc:
            status = str(exc.status_code) if exc.status_code is not None else "none"
            return VerificationCheck(
                check_id=check_id,
                verifier_id=self.verifier_id,
                model_id=self.model_id,
                evidence_ids=evidence_ids,
                entailed=None,
                error_code=f"{exc.failure_kind.value}:{status}",
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
