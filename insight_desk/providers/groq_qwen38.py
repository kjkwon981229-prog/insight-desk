from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from insight_desk.core import FailureKind

from .transport import JsonHttpTransport, ProviderTransportError, require_secret


GROQ_QWEN_38_27B = "qwen/qwen3.8-27b"
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"


@dataclass(slots=True)
class GroqQwen38StructuredClient:
    """Qualification-only structured client for the frozen Qwen 3.8 27B candidate."""

    api_key: str
    model_id: str = GROQ_QWEN_38_27B
    transport: JsonHttpTransport | None = None

    def __post_init__(self) -> None:
        if self.model_id != GROQ_QWEN_38_27B:
            raise ValueError(f"Groq Qwen qualification model is frozen to {GROQ_QWEN_38_27B}")
        if self.transport is None:
            self.transport = JsonHttpTransport()

    @classmethod
    def configured(cls, env: dict[str, str] | None = None) -> bool:
        source = os.environ if env is None else env
        return bool(str(source.get("GROQ_API_KEY", "")).strip())

    @classmethod
    def from_env(
        cls,
        *,
        env: dict[str, str] | None = None,
        transport: JsonHttpTransport | None = None,
    ) -> "GroqQwen38StructuredClient":
        source = dict(os.environ) if env is None else env
        return cls(
            api_key=require_secret(source, "GROQ_API_KEY"),
            transport=transport or JsonHttpTransport(),
        )

    def structured_json(
        self,
        *,
        prompt: str,
        schema: dict[str, Any],
        schema_name: str,
        system_prompt: str = "Follow the JSON schema exactly. Do not output commentary.",
    ) -> dict[str, Any]:
        if not prompt.strip():
            raise ValueError("prompt must be non-empty")
        if not schema_name.strip():
            raise ValueError("schema_name must be non-empty")
        assert self.transport is not None
        try:
            response = self.transport.post_json(
                GROQ_CHAT_URL,
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
                    "reasoning_effort": "low",
                },
                {"Authorization": f"Bearer {self.api_key}"},
            )
            content: Any = response["choices"][0]["message"]["content"]
            if isinstance(content, dict):
                decoded = content
            elif isinstance(content, str):
                decoded = json.loads(content)
            else:
                raise ProviderTransportError(
                    failure_kind=FailureKind.INVALID_OUTPUT,
                    detail="Groq Qwen content is neither object nor JSON text",
                )
            if not isinstance(decoded, dict):
                raise ProviderTransportError(
                    failure_kind=FailureKind.INVALID_OUTPUT,
                    detail="Groq Qwen JSON root is not an object",
                )
            return decoded
        except ProviderTransportError:
            raise
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="unexpected Groq Qwen structured response envelope",
            ) from exc
