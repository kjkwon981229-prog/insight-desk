from __future__ import annotations

"""Qualification-only Mistral Medium 3.5 client for Event Understanding V5.

This exact provider/model route is isolated from the frozen historical Mistral Large 3 client. It
is intentionally not exported from ``insight_desk.providers`` and is not wired into production.
"""

import json
import os
from dataclasses import dataclass
from typing import Any

from insight_desk.core import FailureKind

from .transport import JsonHttpTransport, ProviderTransportError, require_secret


MISTRAL_MEDIUM_35 = "mistral-medium-3-5"
MISTRAL_CHAT_URL = "https://api.mistral.ai/v1/chat/completions"


@dataclass(slots=True)
class MistralMedium35StructuredClient:
    api_key: str
    model_id: str = MISTRAL_MEDIUM_35
    transport: JsonHttpTransport | None = None

    def __post_init__(self) -> None:
        if self.model_id != MISTRAL_MEDIUM_35:
            raise ValueError(
                "Mistral Event Understanding V5 candidate is frozen to mistral-medium-3-5"
            )
        if self.transport is None:
            self.transport = JsonHttpTransport()

    @classmethod
    def from_env(
        cls,
        *,
        env: dict[str, str] | None = None,
        transport: JsonHttpTransport | None = None,
    ) -> "MistralMedium35StructuredClient":
        source = dict(os.environ) if env is None else env
        return cls(
            api_key=require_secret(source, "MISTRAL_API_KEY"),
            transport=transport,
        )

    @staticmethod
    def configured(env: dict[str, str] | None = None) -> bool:
        source = os.environ if env is None else env
        return bool(str(source.get("MISTRAL_API_KEY", "")).strip())

    def structured_json(
        self,
        *,
        prompt: str,
        schema: dict[str, object],
        schema_name: str,
        system_prompt: str = "Follow the JSON schema exactly. Do not output commentary.",
    ) -> dict[str, object]:
        assert self.transport is not None
        response = self.transport.post_json(
            MISTRAL_CHAT_URL,
            {
                "model": self.model_id,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema_name,
                        "schema": schema,
                        "strict": True,
                    },
                },
                "temperature": 0,
                "max_tokens": 2048,
            },
            {"Authorization": f"Bearer {self.api_key}"},
        )
        return self._extract_json(response)

    @staticmethod
    def _extract_json(response: dict[str, Any]) -> dict[str, object]:
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="Mistral completion has no choices",
            )
        first = choices[0]
        if not isinstance(first, dict):
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="Mistral completion choice is not an object",
            )
        message = first.get("message")
        if not isinstance(message, dict):
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="Mistral completion has no message",
            )
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="Mistral completion has no model text",
            )
        try:
            decoded = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail=str(exc)[:500],
            ) from exc
        if not isinstance(decoded, dict):
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="Mistral structured output root is not an object",
            )
        return decoded
