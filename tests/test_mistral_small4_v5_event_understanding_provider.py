from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from insight_desk.providers.mistral import MISTRAL_LARGE_3
from insight_desk.providers.mistral_medium35 import MISTRAL_MEDIUM_35
from insight_desk.providers.mistral_small4 import (
    MISTRAL_CHAT_URL,
    MISTRAL_SMALL_4,
    MistralSmall4StructuredClient,
)
from insight_desk.providers.transport import ProviderConfigError, ProviderTransportError
from scripts import qualify_event_understanding_provider as v3
from scripts import qualify_event_understanding_provider_v4 as v4
from scripts import qualify_event_understanding_provider_v5 as v5
from scripts import qualify_mistral_small4_v5 as lane


class _FakeTransport:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, object], dict[str, str]]] = []

    def post_json(self, url, payload, headers):
        self.calls.append((url, payload, headers))
        return self.response


class MistralSmall4V5QualificationTests(unittest.TestCase):
    def test_candidate_is_exact_new_model_and_frozen_mistral_routes_are_unchanged(self) -> None:
        self.assertEqual(MISTRAL_SMALL_4, "mistral-small-2603")
        self.assertEqual(MISTRAL_MEDIUM_35, "mistral-medium-3-5")
        self.assertEqual(MISTRAL_LARGE_3, "mistral-large-2512")
        self.assertNotEqual(MISTRAL_SMALL_4, MISTRAL_MEDIUM_35)
        self.assertNotEqual(MISTRAL_SMALL_4, MISTRAL_LARGE_3)
        self.assertEqual(lane.CANDIDATE_PROVIDER, "mistral_small4")
        self.assertNotIn(lane.CANDIDATE_PROVIDER, v3.PROVIDER_CHOICES)
        self.assertNotIn(lane.CANDIDATE_PROVIDER, v4.PROVIDER_CHOICES)
        self.assertNotIn(lane.CANDIDATE_PROVIDER, v5.PROVIDER_CHOICES)
        with self.assertRaisesRegex(ValueError, "frozen"):
            MistralSmall4StructuredClient(api_key="test", model_id=MISTRAL_MEDIUM_35)

    def test_credential_reuses_mistral_secret_without_fallback(self) -> None:
        self.assertFalse(MistralSmall4StructuredClient.configured({}))
        self.assertFalse(MistralSmall4StructuredClient.configured({"MISTRAL_API_KEY": "  "}))
        self.assertTrue(MistralSmall4StructuredClient.configured({"MISTRAL_API_KEY": "key"}))
        with self.assertRaisesRegex(ProviderConfigError, "MISTRAL_API_KEY"):
            MistralSmall4StructuredClient.from_env(env={})

    def test_structured_json_is_schema_bound_and_makes_one_transport_call(self) -> None:
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
        client = MistralSmall4StructuredClient(api_key="test", transport=transport)
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
        self.assertEqual(headers, {"Authorization": "Bearer test"})
        self.assertEqual(payload["model"], MISTRAL_SMALL_4)
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
                    "schema": schema,
                    "strict": True,
                },
            },
        )
        self.assertEqual(payload["temperature"], 0)
        self.assertEqual(payload["max_tokens"], 2048)

    def test_invalid_provider_shape_maps_to_bounded_transport_failure(self) -> None:
        client = MistralSmall4StructuredClient(
            api_key="test", transport=_FakeTransport({"choices": []})
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
                self.assertEqual(v5._provider_model(lane.CANDIDATE_PROVIDER), MISTRAL_SMALL_4)
                self.assertFalse(v5._provider_configured(lane.CANDIDATE_PROVIDER))
                self.assertNotIn(lane.CANDIDATE_PROVIDER, v3.PROVIDER_CHOICES)
                self.assertNotIn(lane.CANDIDATE_PROVIDER, v4.PROVIDER_CHOICES)

        self.assertEqual(v5.PROVIDER_CHOICES, original_choices)
        self.assertIs(v5._provider_model, original_model)
        self.assertIs(v5._provider_configured, original_configured)
        self.assertIs(v5._provider_client, original_client)
        self.assertNotIn(lane.CANDIDATE_PROVIDER, v3.PROVIDER_CHOICES)
        self.assertNotIn(lane.CANDIDATE_PROVIDER, v4.PROVIDER_CHOICES)

    def test_missing_credential_reuses_active_v5_not_configured_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / "report.json"
            with patch.dict(os.environ, {}, clear=True):
                code = lane.qualify(report_path=report_path)

            self.assertEqual(code, 2)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "NOT_CONFIGURED")
            self.assertEqual(report["provider"], lane.CANDIDATE_PROVIDER)
            self.assertEqual(report["model"], MISTRAL_SMALL_4)
            self.assertEqual(report["qualification_protocol"], 5)
            self.assertEqual(report["core_contract"], "event_understanding_v2")
            self.assertEqual(report["structured_output_schema"], "event_understanding_schema_v4")
            self.assertEqual(report["evaluated_cases"], 0)
            self.assertEqual(report["passed_cases"], 0)
            self.assertEqual(report["source_mode"], "historical_exact_source_excerpt_only")
            self.assertFalse(report["full_production_correctness_claimed"])


if __name__ == "__main__":
    unittest.main()
