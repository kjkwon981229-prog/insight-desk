from __future__ import annotations

"""Qualification-only Gemini 3.7 Flash client for Event Understanding.

This model is intentionally isolated from the existing Gemini Flash-Lite verification-failover
owner. It is not exported from ``insight_desk.providers`` and is not production-wired.
"""

import json
import os
from dataclasses import dataclass
from typing import Any

from insight_desk.core import FailureKind

from .transport import JsonHttpTransport, ProviderTransportError, require_secret


GEMINI_37_FLASH = "gemini-3.7-flash"
GEMINI_37_INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"


@dataclass(slots=True)
class Gemini37FlashStructuredClient:
    api_key: str
    model_id: str = GEMINI_37_FLASH
    transport: JsonHttpTransport | None = None

    def __post_init__(self) -> None:
        if self.model_id != GEMINI_37_FLASH:
            raise ValueError("Gemini Event Understanding candidate is frozen to gemini-3.7-flash")
        if self.transport is None:
            self.transport = JsonHttpTransport()

    @classmethod
    def from_env(
        cls,
        *,
        env: dict[str, str] | None = None,
        transport: JsonHttpTransport | None = None,
    ) -> "Gemini37FlashStructuredClient":
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
            GEMINI_37_INTERACTIONS_URL,
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
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="Gemini 3.7 interaction has no steps",
            )
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
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="Gemini 3.7 interaction has no model text",
            )
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="Gemini 3.7 model text is not valid JSON",
            ) from exc
        if not isinstance(decoded, dict):
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="Gemini 3.7 structured output root is not an object",
            )
        return decoded
