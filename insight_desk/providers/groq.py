from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from insight_desk.core import FailureKind, TemporalState

from .transport import JsonHttpTransport, ProviderTransportError, require_secret


GROQ_20B = "openai/gpt-oss-20b"
GROQ_120B = "openai/gpt-oss-120b"
ALLOWED_GROQ_MODELS = frozenset({GROQ_20B, GROQ_120B})


@dataclass(slots=True)
class GroqFreeClient:
    api_key: str
    model_id: str
    transport: JsonHttpTransport
    delay_seconds: float = 2.1
    clock: Callable[[], float] = time.monotonic
    sleeper: Callable[[float], None] = time.sleep
    _last_call_started: float | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.model_id not in ALLOWED_GROQ_MODELS:
            raise ValueError(f"Groq model is outside frozen zero-cost allowlist: {self.model_id}")
        if self.delay_seconds < 0:
            raise ValueError("delay_seconds must be >= 0")

    @classmethod
    def from_env(
        cls,
        model_id: str,
        *,
        transport: JsonHttpTransport | None = None,
        env: dict[str, str] | None = None,
        delay_seconds: float = 2.1,
    ) -> "GroqFreeClient":
        source = dict(os.environ) if env is None else env
        return cls(
            api_key=require_secret(source, "GROQ_API_KEY"),
            model_id=model_id,
            transport=transport or JsonHttpTransport(),
            delay_seconds=delay_seconds,
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
        self._validate_strict_schema(schema)
        self._pace()

        response = self.transport.post_json(
            "https://api.groq.com/openai/v1/chat/completions",
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
                "reasoning_effort": "low",
            },
            {"Authorization": f"Bearer {self.api_key}"},
        )
        try:
            content: Any = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="unexpected Groq response envelope",
            ) from exc

        if isinstance(content, dict):
            decoded = content
        elif isinstance(content, str):
            try:
                decoded = json.loads(content)
            except json.JSONDecodeError as exc:
                raise ProviderTransportError(
                    failure_kind=FailureKind.INVALID_OUTPUT,
                    detail="Groq content is not valid JSON",
                ) from exc
        else:
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="Groq content is neither object nor JSON text",
            )
        if not isinstance(decoded, dict):
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="Groq JSON root is not an object",
            )
        return decoded

    def classify_temporal(self, text: str) -> TemporalState:
        if self.model_id != GROQ_120B:
            raise ValueError("temporal auxiliary is frozen to Groq 120B")
        schema = {
            "type": "object",
            "properties": {
                "temporal_state": {
                    "type": "string",
                    "enum": [state.value for state in TemporalState],
                }
            },
            "required": ["temporal_state"],
            "additionalProperties": False,
        }
        result = self.structured_json(
            prompt=(
                "Classify only the temporal/lifecycle state explicitly expressed by the Korean "
                "text. Use only the text; do not use external knowledge. Choose exactly one enum "
                "using these boundaries:\n"
                "- planned: a non-resumption action/event is a future plan or decision and has not "
                "started yet. Korean future forms such as '-한다', '-할 예정이다', a future date "
                "+ action, and '-하기로 했다' are planned unless the text is explicitly reporting "
                "a prospective announcement.\n"
                "- announced_prospective: the text explicitly reports that someone announced or "
                "stated a future status/action, such as '-한다고 밝혔다' or '-한다고 발표했다'. "
                "The future action itself has not happened yet.\n"
                "- resuming: a previously stopped/suspended activity is stated to resume but has "
                "not yet resumed.\n"
                "- resumed: a previously stopped/suspended activity has already resumed.\n"
                "- ongoing: the action/event is explicitly happening or continuing now. Require "
                "current-progress meaning such as '진행 중' or '-하고 있다'. NEVER use ongoing for "
                "a simple future action or a simple past-completed action.\n"
                "- completed: the action/event already occurred or finished. Korean past-completed "
                "forms such as '열었다', '했다', or '떠났다' are completed unless the verb only "
                "describes making a future plan/decision.\n"
                "- cancelled: the action/event is explicitly cancelled or withdrawn.\n"
                "Do not infer completion from a future announcement. Do not infer ongoing merely "
                "because an event is mentioned. Preserve Korean tense/aspect exactly.\n\nTEXT:\n"
                + text
            ),
            schema=schema,
            schema_name="insight_desk_temporal_state",
        )
        try:
            return TemporalState(result["temporal_state"])
        except (KeyError, ValueError, TypeError) as exc:
            raise ProviderTransportError(
                failure_kind=FailureKind.INVALID_OUTPUT,
                detail="Groq temporal_state is outside contract enum",
            ) from exc

    def _pace(self) -> None:
        now = self.clock()
        if self._last_call_started is not None:
            remaining = self.delay_seconds - (now - self._last_call_started)
            if remaining > 0:
                self.sleeper(remaining)
                now = self.clock()
        self._last_call_started = now

    @staticmethod
    def _validate_strict_schema(schema: dict[str, Any]) -> None:
        if schema.get("type") != "object":
            raise ValueError("Groq strict schema root must be object")
        properties = schema.get("properties")
        required = schema.get("required")
        if not isinstance(properties, dict) or not properties:
            raise ValueError("Groq strict schema must define properties")
        if set(required or ()) != set(properties):
            raise ValueError("Groq strict schema requires every property")
        if schema.get("additionalProperties") is not False:
            raise ValueError("Groq strict schema must set additionalProperties=false")
