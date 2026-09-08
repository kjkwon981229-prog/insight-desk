from __future__ import annotations

import unittest

from insight_desk.providers.openrouter_glm52 import (
    OPENROUTER_GLM_52_FREE,
    OpenRouterGlm52StructuredClient,
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


class OpenRouterGlm52StructuredClientTests(unittest.TestCase):
    def test_candidate_is_exact_fixed_free_model(self) -> None:
        self.assertEqual(OPENROUTER_GLM_52_FREE, "z-ai/glm-5.2:free")
        self.assertIn("openrouter_glm52_free", PROVIDER_CHOICES)
        self.assertEqual(_provider_model("openrouter_glm52_free"), OPENROUTER_GLM_52_FREE)
        with self.assertRaisesRegex(ValueError, "frozen"):
            OpenRouterGlm52StructuredClient(
                api_key="test", model_id="openrouter/free"
            )

    def test_missing_credential_is_not_configured_and_from_env_fails_closed(self) -> None:
        self.assertFalse(OpenRouterGlm52StructuredClient.configured({}))
        self.assertFalse(
            OpenRouterGlm52StructuredClient.configured({"OPENROUTER_API_KEY": "  "})
        )
        self.assertTrue(
            OpenRouterGlm52StructuredClient.configured({"OPENROUTER_API_KEY": "key"})
        )
        with self.assertRaisesRegex(ProviderConfigError, "OPENROUTER_API_KEY"):
            OpenRouterGlm52StructuredClient.from_env(env={})

    def test_structured_json_uses_exact_model_and_strict_schema(self) -> None:
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
        client = OpenRouterGlm52StructuredClient(api_key="secret", transport=transport)
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
        self.assertEqual(payload["model"], OPENROUTER_GLM_52_FREE)
        self.assertEqual(payload["temperature"], 0)
        self.assertEqual(payload["provider"], {"require_parameters": True})
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
        client = OpenRouterGlm52StructuredClient(
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
