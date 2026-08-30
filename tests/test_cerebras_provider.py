from __future__ import annotations

import unittest

from insight_desk.providers.cerebras import (
    CEREBRAS_CHAT_URL,
    CEREBRAS_GLM_47,
    CerebrasGlm47StructuredClient,
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


class CerebrasGlm47StructuredClientTests(unittest.TestCase):
    def test_candidate_is_exact_model_and_not_alias(self) -> None:
        self.assertEqual(CEREBRAS_GLM_47, "zai-glm-4.7")
        self.assertIn("cerebras_glm_47", PROVIDER_CHOICES)
        self.assertEqual(_provider_model("cerebras_glm_47"), CEREBRAS_GLM_47)
        with self.assertRaisesRegex(ValueError, "frozen"):
            CerebrasGlm47StructuredClient(api_key="test", model_id="glm-4.7")

    def test_missing_credential_is_not_configured_and_from_env_fails_closed(self) -> None:
        self.assertFalse(CerebrasGlm47StructuredClient.configured({}))
        self.assertFalse(CerebrasGlm47StructuredClient.configured({"CEREBRAS_API_KEY": "  "}))
        self.assertTrue(CerebrasGlm47StructuredClient.configured({"CEREBRAS_API_KEY": "key"}))
        with self.assertRaisesRegex(ProviderConfigError, "CEREBRAS_API_KEY"):
            CerebrasGlm47StructuredClient.from_env(env={})

    def test_structured_json_uses_strict_json_schema_and_parses_object(self) -> None:
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
        client = CerebrasGlm47StructuredClient(api_key="secret", transport=transport)
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
        self.assertEqual(url, CEREBRAS_CHAT_URL)
        self.assertEqual(payload["model"], CEREBRAS_GLM_47)
        self.assertEqual(payload["temperature"], 0)
        self.assertEqual(payload["max_completion_tokens"], 2048)
        messages = payload["messages"]
        self.assertEqual(messages[0], {"role": "system", "content": "system"})
        self.assertEqual(messages[1], {"role": "user", "content": "source-bound prompt"})
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
        client = CerebrasGlm47StructuredClient(
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
