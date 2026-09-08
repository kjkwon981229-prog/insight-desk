from __future__ import annotations

"""Qualification-only Cohere Command A+ structured client for Event Understanding.

This provider is intentionally not exported from ``insight_desk.providers`` and is not wired into
production. It exists only as a dedicated Event Understanding candidate until the frozen bounded
qualification proves minimum compatibility.
"""

import json
import os
from dataclasses import dataclass
from typing import Any

from insight_desk.core import FailureKind

from .transport import JsonHttpTransport, ProviderTransportError, require_secret


COHERE_COMMAND_A_PLUS = "command-a-plus-05-2026"
COHERE_COMPAT_CHAT_URL = "https://api.cohere.ai/compatibility/v1/chat/completions"


@dataclass(slots=True)
class CohereCommandAPlusStructuredClient:
    api_key: str
    model_id: str = COHERE_COMMAND_A_PLUS
    transport: JsonHttpTransport | None = None

    def __post_init__(self) -> None:
        if self.model_id != COHERE_COMMAND_A_PLUS:
            raise ValueError(
                "Cohere Event Understanding candidate is frozen to command-a-plus-05-2026"
            )
        if self.transport is None:
            self.transport = JsonHttpTransport()

    @classmethod
    def from_env(
        cls,
        *,
        env: dict[str, str] | None = None,
        transport: JsonHttpTransport | None = None,
    ) -> "CohereCommandAPlusStructuredClient":
        source = dict(os.environ) if env is None else env
        return cls(
            api_key=require_secret(source, "COHERE_API_KEY"),
            transport=transport,
        )

    @staticmethod
    def configured(env: dict[str, str] | None = None) -> bool:
        source = os.environ if env is None else env
        return bool(str(source.get("COHERE_API_KEY", "")).strip())

    def structured_json(
        self,
        *,
        prompt: str,
        schema: dict[str, object],
        schema_name: str,
        system_prompt: str = "Follow the JSON schema exactly. Do not output commentary.",
    ) -> dict[str, object]:
        del schema_name  # Cohere's compatibility schema mode does not use a schema-name field.
        assert self.transport is not None
        response = self.transport.post_json(
            COHERE_COMPAT_CHAT_URL,
            {
                "model": self.model_id,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {
                    "type": "json_object",
                    "schema": schema,
                },
                "temperature": 0,
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
                detail="Cohere completion has no choices",
            )
        first = choices[0]
        if not isinstance(first, dict):
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="Cohere completion choice is not an object",
            )
        message = first.get("message")
        if not isinstance(message, dict):
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="Cohere completion has no message",
            )
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="Cohere completion has no model text",
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
                detail="Cohere structured output root is not an object",
            )
        return decoded
