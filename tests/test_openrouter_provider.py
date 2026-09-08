from __future__ import annotations

import unittest

from insight_desk.providers.openrouter import (
    OPENROUTER_CHAT_URL,
    OPENROUTER_NEMOTRON_3_SUPER_FREE,
    OpenRouterNemotronStructuredClient,
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


class OpenRouterNemotronStructuredClientTests(unittest.TestCase):
    def test_candidate_is_exact_free_model_and_not_router_or_paid_variant(self) -> None:
        self.assertEqual(
            OPENROUTER_NEMOTRON_3_SUPER_FREE,
            "nvidia/nemotron-3-super-120b-a12b:free",
        )
        self.assertIn("openrouter_nemotron", PROVIDER_CHOICES)
        self.assertEqual(
            _provider_model("openrouter_nemotron"),
            OPENROUTER_NEMOTRON_3_SUPER_FREE,
        )
        with self.assertRaisesRegex(ValueError, "frozen"):
            OpenRouterNemotronStructuredClient(api_key="test", model_id="openrouter/free")
        with self.assertRaisesRegex(ValueError, "frozen"):
            OpenRouterNemotronStructuredClient(
                api_key="test",
                model_id="nvidia/nemotron-3-super-120b-a12b",
            )

    def test_missing_credential_is_not_configured_and_from_env_fails_closed(self) -> None:
        self.assertFalse(OpenRouterNemotronStructuredClient.configured({}))
        self.assertFalse(
            OpenRouterNemotronStructuredClient.configured({"OPENROUTER_API_KEY": "  "})
        )
        self.assertTrue(
            OpenRouterNemotronStructuredClient.configured({"OPENROUTER_API_KEY": "key"})
        )
        with self.assertRaisesRegex(ProviderConfigError, "OPENROUTER_API_KEY"):
            OpenRouterNemotronStructuredClient.from_env(env={})

    def test_structured_json_pins_free_model_and_requires_schema_support(self) -> None:
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
        client = OpenRouterNemotronStructuredClient(api_key="secret", transport=transport)
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
        self.assertEqual(url, OPENROUTER_CHAT_URL)
        self.assertEqual(payload["model"], OPENROUTER_NEMOTRON_3_SUPER_FREE)
        self.assertTrue(str(payload["model"]).endswith(":free"))
        self.assertNotEqual(payload["model"], "openrouter/free")
        self.assertEqual(payload["temperature"], 0)
        self.assertEqual(payload["provider"], {"require_parameters": True})
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
        client = OpenRouterNemotronStructuredClient(
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
