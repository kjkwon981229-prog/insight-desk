from __future__ import annotations

import unittest

from insight_desk.providers.gemini37 import (
    GEMINI_37_FLASH,
    Gemini37FlashStructuredClient,
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


class Gemini37FlashStructuredClientTests(unittest.TestCase):
    def test_candidate_is_exact_model_and_distinct_from_verification_failover(self) -> None:
        self.assertEqual(GEMINI_37_FLASH, "gemini-3.7-flash")
        self.assertIn("gemini_37_flash", PROVIDER_CHOICES)
        self.assertEqual(_provider_model("gemini_37_flash"), GEMINI_37_FLASH)
        with self.assertRaisesRegex(ValueError, "frozen"):
            Gemini37FlashStructuredClient(api_key="test", model_id="gemini-3.1-flash-lite")

    def test_missing_credential_is_not_configured_and_from_env_fails_closed(self) -> None:
        self.assertFalse(Gemini37FlashStructuredClient.configured({}))
        self.assertFalse(Gemini37FlashStructuredClient.configured({"GEMINI_API_KEY": "  "}))
        self.assertTrue(Gemini37FlashStructuredClient.configured({"GEMINI_API_KEY": "key"}))
        with self.assertRaisesRegex(ProviderConfigError, "GEMINI_API_KEY"):
            Gemini37FlashStructuredClient.from_env(env={})

    def test_structured_json_uses_schema_bound_interactions_api_and_parses_object(self) -> None:
        transport = _FakeTransport(
            {
                "steps": [
                    {
                        "type": "model_output",
                        "content": [
                            {
                                "type": "text",
                                "text": '{"status":"resolved","uncertainty_reasons":[],"events":[]}',
                            }
                        ],
                    }
                ]
            }
        )
        client = Gemini37FlashStructuredClient(api_key="secret", transport=transport)
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
        self.assertEqual(payload["model"], GEMINI_37_FLASH)
        self.assertEqual(payload["input"], "system\n\nsource-bound prompt")
        self.assertEqual(
            payload["response_format"],
            {
                "type": "text",
                "mime_type": "application/json",
                "schema": schema,
            },
        )
        self.assertEqual(headers, {"x-goog-api-key": "secret"})

    def test_invalid_provider_shape_is_transport_invalid_output(self) -> None:
        client = Gemini37FlashStructuredClient(
            api_key="secret", transport=_FakeTransport({"steps": []})
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