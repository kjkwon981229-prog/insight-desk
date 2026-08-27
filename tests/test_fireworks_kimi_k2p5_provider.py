from __future__ import annotations

import unittest

from insight_desk.providers.fireworks_kimi_k2p5 import (
    FIREWORKS_KIMI_K2P5,
    FireworksKimiK2P5StructuredClient,
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


class FireworksKimiK2P5StructuredClientTests(unittest.TestCase):
    def test_candidate_is_exact_fixed_serverless_model(self) -> None:
        self.assertEqual(
            FIREWORKS_KIMI_K2P5,
            "accounts/fireworks/models/kimi-k2p5",
        )
        self.assertIn("fireworks_kimi_k2p5", PROVIDER_CHOICES)
        self.assertEqual(
            _provider_model("fireworks_kimi_k2p5"),
            FIREWORKS_KIMI_K2P5,
        )
        with self.assertRaisesRegex(ValueError, "frozen"):
            FireworksKimiK2P5StructuredClient(
                api_key="test", model_id="accounts/fireworks/models/kimi-k2"
            )

    def test_missing_credential_is_not_configured_and_from_env_fails_closed(self) -> None:
        self.assertFalse(FireworksKimiK2P5StructuredClient.configured({}))
        self.assertFalse(
            FireworksKimiK2P5StructuredClient.configured({"FIREWORKS_API_KEY": "  "})
        )
        self.assertTrue(
            FireworksKimiK2P5StructuredClient.configured({"FIREWORKS_API_KEY": "key"})
        )
        with self.assertRaisesRegex(ProviderConfigError, "FIREWORKS_API_KEY"):
            FireworksKimiK2P5StructuredClient.from_env(env={})

    def test_structured_json_uses_exact_model_and_json_schema(self) -> None:
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
        client = FireworksKimiK2P5StructuredClient(
            api_key="secret", transport=transport
        )
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
        self.assertEqual(url, "https://api.fireworks.ai/inference/v1/chat/completions")
        self.assertEqual(payload["model"], FIREWORKS_KIMI_K2P5)
        self.assertEqual(payload["temperature"], 0)
        self.assertEqual(
            payload["response_format"],
            {
                "type": "json_schema",
                "json_schema": {
                    "name": "event_understanding",
                    "schema": schema,
                },
            },
        )
        self.assertEqual(headers, {"Authorization": "Bearer secret"})

    def test_invalid_provider_shape_is_transport_invalid_output(self) -> None:
        client = FireworksKimiK2P5StructuredClient(
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
