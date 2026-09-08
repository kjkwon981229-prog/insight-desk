from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from insight_desk.providers.cohere import COHERE_COMMAND_A_PLUS
from insight_desk.providers.cohere_command_a_reasoning import (
    COHERE_COMMAND_A_REASONING,
    COHERE_V2_CHAT_URL,
    CohereCommandAReasoningStructuredClient,
)
from insight_desk.providers.transport import ProviderConfigError, ProviderTransportError
from scripts import qualify_event_understanding_provider as v3
from scripts import qualify_event_understanding_provider_v4 as v4
from scripts import qualify_event_understanding_provider_v5 as v5
from scripts import qualify_cohere_command_a_reasoning_v5 as lane


class _FakeTransport:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, object], dict[str, str]]] = []

    def post_json(self, url, payload, headers):
        self.calls.append((url, payload, headers))
        return self.response


class CohereCommandAReasoningV5QualificationTests(unittest.TestCase):
    def test_candidate_is_exact_new_model_and_frozen_a_plus_route_is_unchanged(self) -> None:
        self.assertEqual(COHERE_COMMAND_A_REASONING, "command-a-reasoning-08-2025")
        self.assertEqual(COHERE_COMMAND_A_PLUS, "command-a-plus-05-2026")
        self.assertNotEqual(COHERE_COMMAND_A_REASONING, COHERE_COMMAND_A_PLUS)
        self.assertEqual(lane.CANDIDATE_PROVIDER, "cohere_command_a_reasoning")
        self.assertNotIn(lane.CANDIDATE_PROVIDER, v3.PROVIDER_CHOICES)
        self.assertNotIn(lane.CANDIDATE_PROVIDER, v4.PROVIDER_CHOICES)
        self.assertNotIn(lane.CANDIDATE_PROVIDER, v5.PROVIDER_CHOICES)
        with self.assertRaisesRegex(ValueError, "frozen"):
            CohereCommandAReasoningStructuredClient(
                api_key="test",
                model_id=COHERE_COMMAND_A_PLUS,
            )

    def test_credential_reuses_cohere_secret_without_fallback(self) -> None:
        self.assertFalse(CohereCommandAReasoningStructuredClient.configured({}))
        self.assertFalse(
            CohereCommandAReasoningStructuredClient.configured({"COHERE_API_KEY": "  "})
        )
        self.assertTrue(
            CohereCommandAReasoningStructuredClient.configured({"COHERE_API_KEY": "key"})
        )
        with self.assertRaisesRegex(ProviderConfigError, "COHERE_API_KEY"):
            CohereCommandAReasoningStructuredClient.from_env(env={})

    def test_structured_json_uses_v2_schema_and_ignores_thinking_block(self) -> None:
        transport = _FakeTransport(
            {
                "id": "fixture",
                "finish_reason": "COMPLETE",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "thinking", "thinking": "private reasoning fixture"},
                        {
                            "type": "text",
                            "text": '{"status":"resolved","uncertainty_reasons":[],"events":[]}',
                        },
                    ],
                },
            }
        )
        client = CohereCommandAReasoningStructuredClient(api_key="test", transport=transport)
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
        self.assertEqual(url, COHERE_V2_CHAT_URL)
        self.assertEqual(headers, {"Authorization": "Bearer test"})
        self.assertEqual(payload["model"], COHERE_COMMAND_A_REASONING)
        self.assertEqual(
            payload["messages"],
            [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "source-bound prompt"},
            ],
        )
        self.assertEqual(
            payload["response_format"],
            {"type": "json_object", "schema": schema},
        )
        self.assertEqual(payload["temperature"], 0)
        self.assertEqual(payload["max_tokens"], 4096)
        self.assertNotIn("thinking", payload)

    def test_missing_or_ambiguous_final_text_maps_to_bounded_transport_failure(self) -> None:
        for response in (
            {"message": {"content": [{"type": "thinking", "thinking": "x"}]}},
            {
                "message": {
                    "content": [
                        {"type": "text", "text": "{}"},
                        {"type": "text", "text": "{}"},
                    ]
                }
            },
        ):
            with self.subTest(response=response):
                client = CohereCommandAReasoningStructuredClient(
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
                    COHERE_COMMAND_A_REASONING,
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
            self.assertEqual(report["model"], COHERE_COMMAND_A_REASONING)
            self.assertEqual(report["qualification_protocol"], 5)
            self.assertEqual(report["core_contract"], "event_understanding_v2")
            self.assertEqual(report["structured_output_schema"], "event_understanding_schema_v4")
            self.assertEqual(report["evaluated_cases"], 0)
            self.assertEqual(report["passed_cases"], 0)
            self.assertEqual(report["source_mode"], "historical_exact_source_excerpt_only")
            self.assertFalse(report["full_production_correctness_claimed"])


if __name__ == "__main__":
    unittest.main()
