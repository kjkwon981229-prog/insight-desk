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

        for provider_id, record in status["providers"].items():
            if record["status"] != "NOT_QUALIFIED" or record.get("evaluated_cases", 0) == 0:
                continue
            with self.subTest(provider_id=provider_id):
                self.assertIn(record["qualification_protocol"], (1, 2))
                self.assertLess(record["qualification_protocol"], status["active_qualification_protocol"])


if __name__ == "__main__":
    unittest.main()
