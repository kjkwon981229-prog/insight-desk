from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import insight_desk.providers as production_providers
from insight_desk.providers.cerebras import CEREBRAS_GLM_47
from insight_desk.providers.cerebras_gemma4_31b import (
    CEREBRAS_CHAT_URL,
    CEREBRAS_GEMMA4_31B,
    CerebrasGemma4_31BStructuredClient,
)
from insight_desk.providers.transport import ProviderConfigError, ProviderTransportError
from scripts import qualify_event_understanding_provider as v3
from scripts import qualify_event_understanding_provider_v4 as v4
from scripts import qualify_cerebras_gemma4_31b_v4 as lane


class _FakeTransport:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, object], dict[str, str]]] = []

    def post_json(self, url, payload, headers):
        self.calls.append((url, payload, headers))
        return self.response


class CerebrasGemma4_31BV4QualificationTests(unittest.TestCase):
    def test_candidate_is_exact_new_model_and_not_a_production_export(self) -> None:
        self.assertEqual(CEREBRAS_GEMMA4_31B, "gemma-4-31b")
        self.assertEqual(CEREBRAS_GLM_47, "zai-glm-4.7")
        self.assertNotEqual(CEREBRAS_GEMMA4_31B, CEREBRAS_GLM_47)
        self.assertEqual(lane.CANDIDATE_PROVIDER, "cerebras_gemma4_31b")
        self.assertFalse(hasattr(production_providers, "CerebrasGemma4_31BStructuredClient"))
        self.assertNotIn(lane.CANDIDATE_PROVIDER, v3.PROVIDER_CHOICES)
        self.assertNotIn(lane.CANDIDATE_PROVIDER, v4.PROVIDER_CHOICES)
        with self.assertRaisesRegex(ValueError, "frozen"):
            CerebrasGemma4_31BStructuredClient(
                api_key="test",
                model_id=CEREBRAS_GLM_47,
            )

    def test_default_transport_disables_hidden_http_retry(self) -> None:
        client = CerebrasGemma4_31BStructuredClient(api_key="test")
        self.assertIsNotNone(client.transport)
        self.assertEqual(client.transport.attempts, 1)

    def test_credential_reuses_cerebras_secret_without_fallback(self) -> None:
        self.assertFalse(CerebrasGemma4_31BStructuredClient.configured({}))
        self.assertFalse(CerebrasGemma4_31BStructuredClient.configured({"CEREBRAS_API_KEY": "  "}))
        self.assertTrue(CerebrasGemma4_31BStructuredClient.configured({"CEREBRAS_API_KEY": "key"}))
        with self.assertRaisesRegex(ProviderConfigError, "CEREBRAS_API_KEY"):
            CerebrasGemma4_31BStructuredClient.from_env(env={})

    def test_structured_json_uses_exact_schema_and_one_transport_call(self) -> None:
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
        client = CerebrasGemma4_31BStructuredClient(api_key="test", transport=transport)
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
        self.assertEqual(headers, {"Authorization": "Bearer test"})
        self.assertEqual(payload["model"], CEREBRAS_GEMMA4_31B)
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
        self.assertEqual(payload["temperature"], 0)
        self.assertEqual(payload["max_completion_tokens"], 2048)

    def test_invalid_provider_shape_maps_to_bounded_transport_failure(self) -> None:
        client = CerebrasGemma4_31BStructuredClient(api_key="test", transport=_FakeTransport({}))
        with self.assertRaises(ProviderTransportError):
            client.structured_json(
                prompt="prompt",
                schema={"type": "object"},
                schema_name="schema",
                system_prompt="system",
            )

    def test_candidate_registration_is_scoped_to_v4_runner_only(self) -> None:
        original_choices = v4.PROVIDER_CHOICES
        original_model = v4._provider_model
        original_configured = v4._provider_configured
        original_client = v4._provider_client

        with patch.dict(os.environ, {}, clear=True):
            with lane.registered_candidate_provider():
                self.assertEqual(v4.PROVIDER_CHOICES[-1], lane.CANDIDATE_PROVIDER)
                self.assertEqual(v4._provider_model(lane.CANDIDATE_PROVIDER), CEREBRAS_GEMMA4_31B)
                self.assertFalse(v4._provider_configured(lane.CANDIDATE_PROVIDER))
                self.assertNotIn(lane.CANDIDATE_PROVIDER, v3.PROVIDER_CHOICES)

        self.assertEqual(v4.PROVIDER_CHOICES, original_choices)
        self.assertIs(v4._provider_model, original_model)
        self.assertIs(v4._provider_configured, original_configured)
        self.assertIs(v4._provider_client, original_client)
        self.assertNotIn(lane.CANDIDATE_PROVIDER, v3.PROVIDER_CHOICES)

    def test_missing_credential_reuses_active_v4_not_configured_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / "report.json"
            with patch.dict(os.environ, {}, clear=True):
                code = lane.qualify(report_path=report_path)

            self.assertEqual(code, 2)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "NOT_CONFIGURED")
            self.assertEqual(report["provider"], lane.CANDIDATE_PROVIDER)
            self.assertEqual(report["model"], CEREBRAS_GEMMA4_31B)
            self.assertEqual(report["qualification_protocol"], 4)
            self.assertEqual(report["core_contract"], "event_understanding_v2")
            self.assertEqual(report["structured_output_schema"], "event_understanding_schema_v3")
            self.assertEqual(report["evaluated_cases"], 0)
            self.assertEqual(report["source_mode"], "historical_exact_source_excerpt_only")
            self.assertFalse(report["full_production_correctness_claimed"])


if __name__ == "__main__":
    unittest.main()
