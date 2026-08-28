from __future__ import annotations

"""Qualification-only Gemini 2.5 Flash client for Event Understanding V4.

This client is deliberately isolated from the production Gemini 3.1 Flash-Lite verification-
failover owner. Gemini 2.5 Flash is qualified through the official generateContent structured-
output route rather than the Interactions route that proved unavailable for Gemini 2.5 Pro.
It is not exported from ``insight_desk.providers`` and is not production-wired.
"""

import json
import os
from dataclasses import dataclass
from typing import Any

from insight_desk.core import FailureKind

from .transport import JsonHttpTransport, ProviderTransportError, require_secret


GEMINI_25_FLASH = "gemini-2.5-flash"
GEMINI_25_GENERATE_CONTENT_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_25_FLASH}:generateContent"
)


@dataclass(slots=True)
class Gemini25FlashStructuredClient:
    api_key: str
    model_id: str = GEMINI_25_FLASH
    transport: JsonHttpTransport | None = None

    def __post_init__(self) -> None:
        if self.model_id != GEMINI_25_FLASH:
            raise ValueError("Gemini Event Understanding candidate is frozen to gemini-2.5-flash")
        if self.transport is None:
            self.transport = JsonHttpTransport(attempts=1)

    @classmethod
    def from_env(
        cls,
        *,
        env: dict[str, str] | None = None,
        transport: JsonHttpTransport | None = None,
    ) -> "Gemini25FlashStructuredClient":
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
            GEMINI_25_GENERATE_CONTENT_URL,
            {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": system_prompt + "\n\n" + prompt}],
                    }
                ],
                "generationConfig": {
                    "responseFormat": {
                        "text": {
                            "mimeType": "application/json",
                            "schema": schema,
                        }
                    }
                },
            },
            {"x-goog-api-key": self.api_key},
        )
        return self._extract_json(response)

    @staticmethod
    def _extract_json(response: dict[str, Any]) -> dict[str, object]:
        candidates = response.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="Gemini 2.5 Flash generateContent response has no candidates",
            )
        candidate = candidates[0]
        if not isinstance(candidate, dict):
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="Gemini 2.5 Flash candidate is not an object",
            )
        content = candidate.get("content")
        if not isinstance(content, dict):
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="Gemini 2.5 Flash candidate has no content object",
            )
        parts = content.get("parts")
        if not isinstance(parts, list) or not parts:
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="Gemini 2.5 Flash candidate has no content parts",
            )
        text_parts: list[str] = []
        for part in parts:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str):
                text_parts.append(text)
        text = "".join(text_parts).strip()
        if not text:
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="Gemini 2.5 Flash candidate has no text",
            )
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="Gemini 2.5 Flash model text is not valid JSON",
            ) from exc
        if not isinstance(decoded, dict):
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="Gemini 2.5 Flash structured output root is not an object",
            )
        return decoded
