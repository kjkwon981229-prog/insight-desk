from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from insight_desk.providers.gemini import GEMINI_FLASH_LITE
from insight_desk.providers.gemini25flash import (
    GEMINI_25_FLASH,
    GEMINI_25_GENERATE_CONTENT_URL,
    Gemini25FlashStructuredClient,
)
from insight_desk.providers.transport import ProviderConfigError, ProviderTransportError
from scripts import qualify_event_understanding_provider as v3
from scripts import qualify_event_understanding_provider_v4 as v4
from scripts import qualify_gemini25_flash_v4 as lane


class _FakeTransport:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, object], dict[str, str]]] = []

    def post_json(self, url, payload, headers):
        self.calls.append((url, payload, headers))
        return self.response


class Gemini25FlashV4QualificationTests(unittest.TestCase):
    def test_candidate_is_exact_new_model_and_production_owner_is_unchanged(self) -> None:
        self.assertEqual(GEMINI_25_FLASH, "gemini-2.5-flash")
        self.assertEqual(GEMINI_FLASH_LITE, "gemini-3.1-flash-lite")
        self.assertNotEqual(GEMINI_25_FLASH, GEMINI_FLASH_LITE)
        self.assertEqual(lane.CANDIDATE_PROVIDER, "gemini25_flash")
        self.assertNotIn(lane.CANDIDATE_PROVIDER, v3.PROVIDER_CHOICES)
        self.assertNotIn(lane.CANDIDATE_PROVIDER, v4.PROVIDER_CHOICES)
        with self.assertRaisesRegex(ValueError, "frozen"):
            Gemini25FlashStructuredClient(api_key="test", model_id=GEMINI_FLASH_LITE)

    def test_default_transport_disables_hidden_http_retry(self) -> None:
        client = Gemini25FlashStructuredClient(api_key="test")
        self.assertIsNotNone(client.transport)
        self.assertEqual(client.transport.attempts, 1)

    def test_credential_reuses_gemini_secret_without_fallback(self) -> None:
        self.assertFalse(Gemini25FlashStructuredClient.configured({}))
        self.assertFalse(Gemini25FlashStructuredClient.configured({"GEMINI_API_KEY": "  "}))
        self.assertTrue(Gemini25FlashStructuredClient.configured({"GEMINI_API_KEY": "key"}))
        with self.assertRaisesRegex(ProviderConfigError, "GEMINI_API_KEY"):
            Gemini25FlashStructuredClient.from_env(env={})

    def test_structured_json_uses_generate_content_schema_and_one_transport_call(self) -> None:
        transport = _FakeTransport(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": '{"status":"resolved","uncertainty_reasons":[],"events":[]}'
                                }
                            ]
                        }
                    }
                ]
            }
        )
        client = Gemini25FlashStructuredClient(api_key="test", transport=transport)
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
        self.assertEqual(url, GEMINI_25_GENERATE_CONTENT_URL)
        self.assertEqual(headers, {"x-goog-api-key": "test"})
        self.assertEqual(
            payload["contents"],
            [{"role": "user", "parts": [{"text": "system\n\nsource-bound prompt"}]}],
        )
        self.assertEqual(
            payload["generationConfig"],
            {
                "responseFormat": {
                    "text": {
                        "mimeType": "application/json",
                        "schema": schema,
                    }
                }
            },
        )

    def test_invalid_provider_shape_maps_to_bounded_transport_failure(self) -> None:
        client = Gemini25FlashStructuredClient(api_key="test", transport=_FakeTransport({}))
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
                self.assertEqual(v4._provider_model(lane.CANDIDATE_PROVIDER), GEMINI_25_FLASH)
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
            self.assertEqual(report["model"], GEMINI_25_FLASH)
            self.assertEqual(report["qualification_protocol"], 4)
            self.assertEqual(report["core_contract"], "event_understanding_v2")
            self.assertEqual(report["structured_output_schema"], "event_understanding_schema_v3")
            self.assertEqual(report["evaluated_cases"], 0)
            self.assertEqual(report["source_mode"], "historical_exact_source_excerpt_only")
            self.assertFalse(report["full_production_correctness_claimed"])


if __name__ == "__main__":
    unittest.main()
