from __future__ import annotations

"""Qualification-only Hugging Face/Nscale Qwen3 235B 2507 structured client.

This client is intentionally not exported from ``insight_desk.providers`` and is not wired into
production. Both the model and provider route are frozen so qualification cannot silently move to
another provider, alias, or fallback model.
"""

import json
import os
from dataclasses import dataclass
from typing import Any

from insight_desk.core import FailureKind

from .transport import JsonHttpTransport, ProviderTransportError, require_secret


HF_ROUTER_CHAT_URL = "https://router.huggingface.co/v1/chat/completions"
HF_QWEN3_235B_2507_NSCALE = "Qwen/Qwen3-235B-A22B-Instruct-2507:nscale"


@dataclass(slots=True)
class HuggingFaceQwen235B2507NscaleStructuredClient:
    api_key: str
    model_id: str = HF_QWEN3_235B_2507_NSCALE
    transport: JsonHttpTransport | None = None

    def __post_init__(self) -> None:
        if self.model_id != HF_QWEN3_235B_2507_NSCALE:
            raise ValueError(
                "Hugging Face Qwen3 235B 2507 Nscale Event Understanding candidate is frozen to "
                "Qwen/Qwen3-235B-A22B-Instruct-2507:nscale"
            )
        if self.transport is None:
            self.transport = JsonHttpTransport()

    @classmethod
    def from_env(
        cls,
        *,
        env: dict[str, str] | None = None,
        transport: JsonHttpTransport | None = None,
    ) -> "HuggingFaceQwen235B2507NscaleStructuredClient":
        source = dict(os.environ) if env is None else env
        return cls(
            api_key=require_secret(source, "HF_TOKEN"),
            transport=transport,
        )

    @staticmethod
    def configured(env: dict[str, str] | None = None) -> bool:
        source = os.environ if env is None else env
        return bool(str(source.get("HF_TOKEN", "")).strip())

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
            HF_ROUTER_CHAT_URL,
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
                detail="Hugging Face completion has no choices",
            )
        first = choices[0]
        if not isinstance(first, dict):
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="Hugging Face completion choice is not an object",
            )
        message = first.get("message")
        if not isinstance(message, dict):
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="Hugging Face completion has no message",
            )
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="Hugging Face completion has no model text",
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
                detail="Hugging Face structured output root is not an object",
            )
        return decoded
