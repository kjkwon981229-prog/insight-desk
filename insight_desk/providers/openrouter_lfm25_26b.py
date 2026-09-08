from __future__ import annotations

"""Qualification-only OpenRouter LFM2.5-2.6B structured client for Event Understanding V5."""

import json
import os
from dataclasses import dataclass
from typing import Any

from insight_desk.core import FailureKind

from .transport import JsonHttpTransport, ProviderTransportError, require_secret


OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_LFM25_26B_FREE = "liquid/lfm-2.5-2.6b:free"


@dataclass(slots=True)
class OpenRouterLFM2526BStructuredClient:
    api_key: str
    model_id: str = OPENROUTER_LFM25_26B_FREE
    transport: JsonHttpTransport | None = None

    def __post_init__(self) -> None:
        if self.model_id != OPENROUTER_LFM25_26B_FREE:
            raise ValueError(
                "OpenRouter V5 candidate is frozen to liquid/lfm-2.5-2.6b:free"
            )
        if self.transport is None:
            self.transport = JsonHttpTransport(attempts=1)

    @classmethod
    def from_env(
        cls,
        *,
        env: dict[str, str] | None = None,
        transport: JsonHttpTransport | None = None,
    ) -> "OpenRouterLFM2526BStructuredClient":
        source = dict(os.environ) if env is None else env
        return cls(
            api_key=require_secret(source, "OPENROUTER_API_KEY"),
            transport=transport,
        )

    @staticmethod
    def configured(env: dict[str, str] | None = None) -> bool:
        source = os.environ if env is None else env
        return bool(str(source.get("OPENROUTER_API_KEY", "")).strip())

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
            OPENROUTER_CHAT_URL,
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
                        "strict": True,
                        "schema": schema,
                    },
                },
                "provider": {"require_parameters": True},
                "temperature": 0,
                "max_tokens": 4096,
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
                detail="OpenRouter completion has no choices",
            )
        first = choices[0]
        if not isinstance(first, dict):
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="OpenRouter completion choice is not an object",
            )
        message = first.get("message")
        if not isinstance(message, dict):
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="OpenRouter completion has no message",
            )
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="OpenRouter completion has no model text",
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
                detail="OpenRouter structured output root is not an object",
            )
        return decoded
