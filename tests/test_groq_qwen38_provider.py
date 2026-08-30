from __future__ import annotations

import unittest

from insight_desk.providers.groq_qwen38 import (
    GROQ_QWEN_38_27B,
    GroqQwen38StructuredClient,
)
from insight_desk.providers.transport import ProviderConfigError, ProviderTransportError
from scripts.qualify_event_understanding_provider import PROVIDER_CHOICES, _provider_model


class _FakeTransport:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, object], dict[str, str]]] = []

    def post_json(self, url, payload, headers):
        self.calls.append((url, payload, headers))
        return self.response


class GroqQwen38StructuredClientTests(unittest.TestCase):
    def test_candidate_is_exact_model_and_distinct_from_existing_groq_owner(self) -> None:
        self.assertEqual(GROQ_QWEN_38_27B, "qwen/qwen3.8-27b")
        self.assertIn("groq_qwen38_27b", PROVIDER_CHOICES)
        self.assertEqual(_provider_model("groq_qwen38_27b"), GROQ_QWEN_38_27B)
        with self.assertRaisesRegex(ValueError, "frozen"):
            GroqQwen38StructuredClient(api_key="test", model_id="qwen/qwen3.6-27b")

    def test_missing_credential_is_not_configured_and_from_env_fails_closed(self) -> None:
        self.assertFalse(GroqQwen38StructuredClient.configured({}))
        self.assertFalse(GroqQwen38StructuredClient.configured({"GROQ_API_KEY": "  "}))
        self.assertTrue(GroqQwen38StructuredClient.configured({"GROQ_API_KEY": "key"}))
        with self.assertRaisesRegex(ProviderConfigError, "GROQ_API_KEY"):
            GroqQwen38StructuredClient.from_env(env={})

    def test_structured_json_uses_strict_schema_mode_and_parses_object(self) -> None:
        transport = _FakeTransport(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"status":"resolved","uncertainty_reasons":[],"events":[]}'
                        }
                    }
                ]
            }
        )
        client = GroqQwen38StructuredClient(api_key="secret", transport=transport)
        schema = {
            "type": "object",
            "properties": {"status": {"type": "string"}},
            "required": ["status"],
            "additionalProperties": False,
        }
        result = client.structured_json(
            prompt="source-bound prompt",
            schema=schema,
            schema_name="event_understanding",
            system_prompt="system",
        )
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(len(transport.calls), 1)
        _, payload, headers = transport.calls[0]
        self.assertEqual(payload["model"], GROQ_QWEN_38_27B)
        self.assertEqual(payload["temperature"], 0)
        self.assertEqual(
            payload["response_format"],
            {
                "type": "json_schema",
                "json_schema": {
                    "name": "event_understanding",
                    "strict": True,
                    "schema": schema,
                },
            },
        )
        self.assertEqual(headers, {"Authorization": "Bearer secret"})

    def test_invalid_provider_shape_is_transport_invalid_output(self) -> None:
        client = GroqQwen38StructuredClient(
            api_key="secret", transport=_FakeTransport({"choices": []})
        )
        with self.assertRaises(ProviderTransportError):
            client.structured_json(
                prompt="prompt",
                schema={"type": "object"},
                schema_name="schema",
                system_prompt="system",
            )


if __name__ == "__main__":
    unittest.main()
