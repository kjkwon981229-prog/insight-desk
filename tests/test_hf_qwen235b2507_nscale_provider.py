from __future__ import annotations

import unittest

from insight_desk.providers.hf_qwen235b2507_nscale import (
    HF_QWEN3_235B_2507_NSCALE,
    HF_ROUTER_CHAT_URL,
    HuggingFaceQwen235B2507NscaleStructuredClient,
)
from insight_desk.providers.transport import ProviderConfigError, ProviderTransportError


class _FakeTransport:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, object], dict[str, str]]] = []

    def post_json(self, url, payload, headers):
        self.calls.append((url, payload, headers))
        return self.response


class HuggingFaceQwen235B2507NscaleStructuredClientTests(unittest.TestCase):
    def test_candidate_is_exact_fixed_model_and_provider_route(self) -> None:
        self.assertEqual(
            HF_QWEN3_235B_2507_NSCALE,
            "Qwen/Qwen3-235B-A22B-Instruct-2507:nscale",
        )
        self.assertEqual(
            HF_ROUTER_CHAT_URL,
            "https://router.huggingface.co/v1/chat/completions",
        )
        with self.assertRaisesRegex(ValueError, "frozen"):
            HuggingFaceQwen235B2507NscaleStructuredClient(
                api_key="test",
                model_id="Qwen/Qwen3-235B-A22B-Instruct-2507:fastest",
            )

    def test_missing_credential_is_not_configured_and_from_env_fails_closed(self) -> None:
        self.assertFalse(HuggingFaceQwen235B2507NscaleStructuredClient.configured({}))
        self.assertFalse(
            HuggingFaceQwen235B2507NscaleStructuredClient.configured({"HF_TOKEN": "  "})
        )
        self.assertTrue(
            HuggingFaceQwen235B2507NscaleStructuredClient.configured({"HF_TOKEN": "key"})
        )
        with self.assertRaisesRegex(ProviderConfigError, "HF_TOKEN"):
            HuggingFaceQwen235B2507NscaleStructuredClient.from_env(env={})

    def test_structured_json_uses_exact_route_and_strict_schema(self) -> None:
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
        client = HuggingFaceQwen235B2507NscaleStructuredClient(
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
        self.assertEqual(url, HF_ROUTER_CHAT_URL)
        self.assertEqual(payload["model"], HF_QWEN3_235B_2507_NSCALE)
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
        client = HuggingFaceQwen235B2507NscaleStructuredClient(
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
