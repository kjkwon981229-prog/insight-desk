from __future__ import annotations

import json
from pathlib import Path
import unittest

from insight_desk import event_understanding_adapter_v2 as adapter
from insight_desk.event_understanding_provider_status_v2 import load_provider_status
from scripts import qualify_event_understanding_provider as qualification


ROOT = Path(__file__).resolve().parents[1]
V2_PATH = ROOT / "tests/fixtures/event_understanding_qualification_v2.json"
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"


class EventUnderstandingQualificationProtocolV3Tests(unittest.TestCase):
    def test_corrected_adapter_contract_is_a_new_protocol_without_rewriting_v2_gold(self) -> None:
        self.assertEqual(
            qualification.DEFAULT_QUALIFICATION.name,
            "event_understanding_qualification_v3.json",
        )
        active = json.loads(qualification.DEFAULT_QUALIFICATION.read_text(encoding="utf-8"))
        historical_v2 = json.loads(V2_PATH.read_text(encoding="utf-8"))

        self.assertEqual(active["schema_version"], 3)
        self.assertEqual(active["source_fixture"], historical_v2["source_fixture"])
        self.assertEqual(active["cases"], historical_v2["cases"])
        self.assertEqual(active["scoring_policy"], historical_v2["scoring_policy"])
        self.assertEqual(active["acceptance"], historical_v2["acceptance"])
        self.assertEqual(active["provider_policy"], historical_v2["provider_policy"])
        self.assertEqual(active["core_contract"], "event_understanding_v2")
        self.assertEqual(active["structured_output_schema"], "event_understanding_schema_v2")

        schema = getattr(adapter, "EVENT_UNDERSTANDING_SCHEMA_V2", None)
        self.assertIsInstance(schema, dict)
        evidence = schema["properties"]["events"]["items"]["properties"]["evidence"]["items"]
        self.assertEqual(
            evidence["required"],
            ["source_id", "field", "text", "start", "end"],
        )

        status = load_provider_status(STATUS_PATH)
        self.assertEqual(status["contract"], "event_understanding_v2")
        self.assertEqual(status["structured_output_schema"], "event_understanding_schema_v2")
        self.assertEqual(status["active_qualification_protocol"], 3)
        self.assertEqual(status["qualification_contract_status"], "AWAITING_PROVIDER_QUALIFICATION")
        self.assertIsNone(status["selected_event_understanding_provider"])
        self.assertFalse(status["production_wired"])

        historical_protocols = {
            "groq_20b": 1,
            "gemini_flash_lite": 1,
        }
        for provider_id, expected_protocol in historical_protocols.items():
            with self.subTest(provider_id=provider_id):
                record = status["providers"][provider_id]
                self.assertEqual(record["status"], "NOT_QUALIFIED")
                self.assertEqual(record["qualification_protocol"], expected_protocol)
                self.assertLess(
                    record["qualification_protocol"],
                    status["active_qualification_protocol"],
                )

        mistral = status["providers"]["mistral_large_3"]
        self.assertEqual(mistral["status"], "NOT_QUALIFIED")
        self.assertEqual(
            mistral["qualification_protocol"],
            status["active_qualification_protocol"],
        )
        self.assertEqual(mistral["evaluated_cases"], 4)
        self.assertEqual(mistral["passed_cases"], 0)
        self.assertEqual(mistral["failure_classification"], "PROVIDER_TRANSIENT_FAILURE")
        self.assertEqual(mistral["previous_v1_evidence"]["qualification_protocol"], 1)

        openrouter = status["providers"]["openrouter_nemotron_free"]
        self.assertEqual(openrouter["status"], "NOT_QUALIFIED")
        self.assertEqual(
            openrouter["qualification_protocol"],
            status["active_qualification_protocol"],
        )
        self.assertEqual(openrouter["evaluated_cases"], 4)
        self.assertEqual(openrouter["passed_cases"], 0)
        self.assertEqual(openrouter["previous_v2_evidence"]["qualification_protocol"], 2)
        self.assertEqual(openrouter["previous_v1_evidence"]["qualification_protocol"], 1)


if __name__ == "__main__":
    unittest.main()
