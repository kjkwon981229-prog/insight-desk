from __future__ import annotations

import unittest

from insight_desk.providers.mistral import (
    MISTRAL_CHAT_URL,
    MISTRAL_LARGE_3,
    MistralStructuredClient,
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


class MistralStructuredClientTests(unittest.TestCase):
    def test_candidate_is_exact_model_and_not_alias(self) -> None:
        self.assertEqual(MISTRAL_LARGE_3, "mistral-large-2512")
        self.assertIn("mistral", PROVIDER_CHOICES)
        self.assertEqual(_provider_model("mistral"), MISTRAL_LARGE_3)
        with self.assertRaisesRegex(ValueError, "frozen"):
            MistralStructuredClient(api_key="test", model_id="mistral-large-latest")

    def test_missing_credential_is_not_configured_and_from_env_fails_closed(self) -> None:
        self.assertFalse(MistralStructuredClient.configured({}))
        self.assertFalse(MistralStructuredClient.configured({"MISTRAL_API_KEY": "  "}))
        self.assertTrue(MistralStructuredClient.configured({"MISTRAL_API_KEY": "key"}))
        with self.assertRaisesRegex(ProviderConfigError, "MISTRAL_API_KEY"):
            MistralStructuredClient.from_env(env={})

    def test_structured_json_uses_schema_mode_and_parses_object(self) -> None:
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
        client = MistralStructuredClient(api_key="secret", transport=transport)
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
        url, payload, headers = transport.calls[0]
        self.assertEqual(url, MISTRAL_CHAT_URL)
        self.assertEqual(payload["model"], MISTRAL_LARGE_3)
        self.assertEqual(payload["temperature"], 0)
        messages = payload["messages"]
        self.assertEqual(messages[0], {"role": "system", "content": "system"})
        self.assertEqual(messages[1], {"role": "user", "content": "source-bound prompt"})
        response_format = payload["response_format"]
        self.assertEqual(response_format["type"], "json_schema")
        json_schema = response_format["json_schema"]
        self.assertEqual(json_schema["name"], "event_understanding")
        self.assertIs(json_schema["strict"], True)
        self.assertEqual(json_schema["schema"], schema)
        self.assertEqual(headers, {"Authorization": "Bearer secret"})

    def test_invalid_provider_shape_is_transport_invalid_output(self) -> None:
        client = MistralStructuredClient(api_key="secret", transport=_FakeTransport({"choices": []}))
        with self.assertRaises(ProviderTransportError):
            client.structured_json(
                prompt="prompt",
                schema={"type": "object"},
                schema_name="schema",
                system_prompt="system",
            )


if __name__ == "__main__":
    unittest.main()
