from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from insight_desk.providers.openrouter_dots3note import OPENROUTER_DOTS3_NOTE_FREE
from insight_desk.providers.openrouter_nexn2pro import OPENROUTER_NEX_N2_PRO_FREE
from insight_desk.providers.openrouter_qwen3next80b import OPENROUTER_QWEN3_NEXT_80B_FREE
from insight_desk.providers.openrouter_lfm25_26b import (
    OPENROUTER_CHAT_URL,
    OPENROUTER_LFM25_26B_FREE,
    OpenRouterLFM2526BStructuredClient,
)
from insight_desk.providers.transport import ProviderConfigError, ProviderTransportError
from scripts import qualify_event_understanding_provider as v3
from scripts import qualify_event_understanding_provider_v4 as v4
from scripts import qualify_event_understanding_provider_v5 as v5
from scripts import qualify_openrouter_lfm25_26b_v5 as lane


class _FakeTransport:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, object], dict[str, str]]] = []

    def post_json(self, url, payload, headers):
        self.calls.append((url, payload, headers))
        return self.response


class OpenRouterLFM2526BV5QualificationTests(unittest.TestCase):
    def test_candidate_is_exact_new_route_not_frozen_openrouter_models(self) -> None:
        self.assertEqual(OPENROUTER_LFM25_26B_FREE, "liquid/lfm-2.5-2.6b:free")
        self.assertNotEqual(OPENROUTER_LFM25_26B_FREE, OPENROUTER_DOTS3_NOTE_FREE)
        self.assertNotEqual(OPENROUTER_LFM25_26B_FREE, OPENROUTER_NEX_N2_PRO_FREE)
        self.assertNotEqual(OPENROUTER_LFM25_26B_FREE, OPENROUTER_QWEN3_NEXT_80B_FREE)
        self.assertEqual(lane.CANDIDATE_PROVIDER, "openrouter_lfm25_26b")
        self.assertNotIn(lane.CANDIDATE_PROVIDER, v3.PROVIDER_CHOICES)
        self.assertNotIn(lane.CANDIDATE_PROVIDER, v4.PROVIDER_CHOICES)
        self.assertNotIn(lane.CANDIDATE_PROVIDER, v5.PROVIDER_CHOICES)
        with self.assertRaisesRegex(ValueError, "frozen"):
            OpenRouterLFM2526BStructuredClient(
                api_key="test",
                model_id=OPENROUTER_QWEN3_NEXT_80B_FREE,
            )

    def test_credential_reuses_openrouter_secret_without_fallback(self) -> None:
        self.assertFalse(OpenRouterLFM2526BStructuredClient.configured({}))
        self.assertFalse(
            OpenRouterLFM2526BStructuredClient.configured({"OPENROUTER_API_KEY": "  "})
        )
        self.assertTrue(
            OpenRouterLFM2526BStructuredClient.configured({"OPENROUTER_API_KEY": "key"})
        )
        with self.assertRaisesRegex(ProviderConfigError, "OPENROUTER_API_KEY"):
            OpenRouterLFM2526BStructuredClient.from_env(env={})

    def test_default_transport_disables_hidden_retry(self) -> None:
        client = OpenRouterLFM2526BStructuredClient(api_key="test")
        self.assertIsNotNone(client.transport)
        self.assertEqual(client.transport.attempts, 1)

    def test_structured_json_uses_exact_free_route_and_strict_schema(self) -> None:
        transport = _FakeTransport(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": '{"status":"resolved","uncertainty_reasons":[],"events":[]}',
                        }
                    }
                ]
            }
        )
        client = OpenRouterLFM2526BStructuredClient(api_key="test", transport=transport)
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
        self.assertEqual(headers, {"Authorization": "Bearer test"})
        self.assertEqual(payload["model"], OPENROUTER_LFM25_26B_FREE)
        self.assertEqual(
            payload["messages"],
            [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "source-bound prompt"},
            ],
        )
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
        self.assertEqual(payload["provider"], {"require_parameters": True})
        self.assertEqual(payload["temperature"], 0)
        self.assertEqual(payload["max_tokens"], 4096)

    def test_missing_or_invalid_text_maps_to_bounded_transport_failure(self) -> None:
        for response in (
            {},
            {"choices": []},
            {"choices": [{"message": {"content": "not-json"}}]},
        ):
            with self.subTest(response=response):
                client = OpenRouterLFM2526BStructuredClient(
                    api_key="test",
                    transport=_FakeTransport(response),
                )
                with self.assertRaises(ProviderTransportError):
                    client.structured_json(
                        prompt="prompt",
                        schema={"type": "object"},
                        schema_name="schema",
                        system_prompt="system",
                    )

    def test_candidate_registration_is_scoped_to_v5_runner_only(self) -> None:
        original_choices = v5.PROVIDER_CHOICES
        original_model = v5._provider_model
        original_configured = v5._provider_configured
        original_client = v5._provider_client

        with patch.dict(os.environ, {}, clear=True):
            with lane.registered_candidate_provider():
                self.assertEqual(v5.PROVIDER_CHOICES[-1], lane.CANDIDATE_PROVIDER)
                self.assertEqual(
                    v5._provider_model(lane.CANDIDATE_PROVIDER),
                    OPENROUTER_LFM25_26B_FREE,
                )
                self.assertFalse(v5._provider_configured(lane.CANDIDATE_PROVIDER))
                self.assertNotIn(lane.CANDIDATE_PROVIDER, v3.PROVIDER_CHOICES)
                self.assertNotIn(lane.CANDIDATE_PROVIDER, v4.PROVIDER_CHOICES)

        self.assertEqual(v5.PROVIDER_CHOICES, original_choices)
        self.assertIs(v5._provider_model, original_model)
        self.assertIs(v5._provider_configured, original_configured)
        self.assertIs(v5._provider_client, original_client)

    def test_missing_credential_reuses_active_v5_not_configured_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / "report.json"
            with patch.dict(os.environ, {}, clear=True):
                code = lane.qualify(report_path=report_path)

            self.assertEqual(code, 2)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "NOT_CONFIGURED")
            self.assertEqual(report["provider"], lane.CANDIDATE_PROVIDER)
            self.assertEqual(report["model"], OPENROUTER_LFM25_26B_FREE)
            self.assertEqual(report["qualification_protocol"], 5)
            self.assertEqual(report["core_contract"], "event_understanding_v2")
            self.assertEqual(report["structured_output_schema"], "event_understanding_schema_v4")
            self.assertEqual(report["evaluated_cases"], 0)
            self.assertEqual(report["passed_cases"], 0)
            self.assertEqual(report["source_mode"], "historical_exact_source_excerpt_only")
            self.assertFalse(report["full_production_correctness_claimed"])


if __name__ == "__main__":
    unittest.main()
