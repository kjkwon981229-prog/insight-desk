from __future__ import annotations

"""Qualification-only Cohere Command A Reasoning client for Event Understanding V5.

This exact provider/model route uses Cohere Chat API V2 so reasoning/thinking content blocks can be
ignored mechanically while the final structured text block is parsed. It is not exported from
``insight_desk.providers`` and is not wired into production.
"""

import json
import os
from dataclasses import dataclass
from typing import Any

from insight_desk.core import FailureKind

from .transport import JsonHttpTransport, ProviderTransportError, require_secret


COHERE_COMMAND_A_REASONING = "command-a-reasoning-08-2025"
COHERE_V2_CHAT_URL = "https://api.cohere.com/v2/chat"


@dataclass(slots=True)
class CohereCommandAReasoningStructuredClient:
    api_key: str
    model_id: str = COHERE_COMMAND_A_REASONING
    transport: JsonHttpTransport | None = None

    def __post_init__(self) -> None:
        if self.model_id != COHERE_COMMAND_A_REASONING:
            raise ValueError(
                "Cohere Event Understanding V5 candidate is frozen to "
                "command-a-reasoning-08-2025"
            )
        if self.transport is None:
            self.transport = JsonHttpTransport()

    @classmethod
    def from_env(
        cls,
        *,
        env: dict[str, str] | None = None,
        transport: JsonHttpTransport | None = None,
    ) -> "CohereCommandAReasoningStructuredClient":
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
        del schema_name  # Cohere V2 JSON-Schema mode has no schema-name field.
        assert self.transport is not None
        response = self.transport.post_json(
            COHERE_V2_CHAT_URL,
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
                "max_tokens": 4096,
            },
            {"Authorization": f"Bearer {self.api_key}"},
        )
        return self._extract_json(response)

    @staticmethod
    def _extract_json(response: dict[str, Any]) -> dict[str, object]:
        message = response.get("message")
        if not isinstance(message, dict):
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="Cohere V2 response has no message",
            )
        content = message.get("content")
        if not isinstance(content, list) or not content:
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="Cohere V2 response has no content blocks",
            )
        text_blocks = [
            item.get("text")
            for item in content
            if isinstance(item, dict)
            and item.get("type") == "text"
            and isinstance(item.get("text"), str)
            and item.get("text", "").strip()
        ]
        if len(text_blocks) != 1:
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="Cohere V2 response must contain exactly one final text block",
            )
        try:
            decoded = json.loads(text_blocks[0])
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
