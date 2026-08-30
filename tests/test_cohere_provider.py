from __future__ import annotations

import unittest

from insight_desk.providers.cohere import (
    COHERE_COMMAND_A_PLUS,
    COHERE_COMPAT_CHAT_URL,
    CohereCommandAPlusStructuredClient,
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


class CohereCommandAPlusStructuredClientTests(unittest.TestCase):
    def test_candidate_is_exact_model_and_not_alias(self) -> None:
        self.assertEqual(COHERE_COMMAND_A_PLUS, "command-a-plus-05-2026")
        self.assertIn("cohere_command_a_plus", PROVIDER_CHOICES)
        self.assertEqual(_provider_model("cohere_command_a_plus"), COHERE_COMMAND_A_PLUS)
        with self.assertRaisesRegex(ValueError, "frozen"):
            CohereCommandAPlusStructuredClient(api_key="test", model_id="command-a-plus")

    def test_missing_credential_is_not_configured_and_from_env_fails_closed(self) -> None:
        self.assertFalse(CohereCommandAPlusStructuredClient.configured({}))
        self.assertFalse(CohereCommandAPlusStructuredClient.configured({"COHERE_API_KEY": "  "}))
        self.assertTrue(CohereCommandAPlusStructuredClient.configured({"COHERE_API_KEY": "key"}))
        with self.assertRaisesRegex(ProviderConfigError, "COHERE_API_KEY"):
            CohereCommandAPlusStructuredClient.from_env(env={})

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
        client = CohereCommandAPlusStructuredClient(api_key="secret", transport=transport)
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
        self.assertEqual(url, COHERE_COMPAT_CHAT_URL)
        self.assertEqual(payload["model"], COHERE_COMMAND_A_PLUS)
        self.assertEqual(payload["temperature"], 0)
        messages = payload["messages"]
        self.assertEqual(messages[0], {"role": "system", "content": "system"})
        self.assertEqual(messages[1], {"role": "user", "content": "source-bound prompt"})
        response_format = payload["response_format"]
        self.assertEqual(response_format["type"], "json_object")
        self.assertEqual(response_format["schema"], schema)
        self.assertNotIn("json_schema", response_format)
        self.assertEqual(headers, {"Authorization": "Bearer secret"})

    def test_invalid_provider_shape_is_transport_invalid_output(self) -> None:
        client = CohereCommandAPlusStructuredClient(
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
