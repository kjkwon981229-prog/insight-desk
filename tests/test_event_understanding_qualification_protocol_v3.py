from __future__ import annotations

import json
from pathlib import Path
import unittest

from insight_desk import event_understanding_adapter_v2 as adapter
from insight_desk.event_understanding_provider_status_v2 import (
    NO_ELIGIBLE_EXISTING_PROVIDER,
    load_provider_status,
)
from scripts import qualify_event_understanding_provider as historical_v3_qualification


ROOT = Path(__file__).resolve().parents[1]
V2_PATH = ROOT / "tests/fixtures/event_understanding_qualification_v2.json"
V3_PATH = ROOT / "tests/fixtures/event_understanding_qualification_v3.json"
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"


class EventUnderstandingQualificationProtocolV3Tests(unittest.TestCase):
    def test_v3_runner_and_offset_contract_remain_frozen_historical_evidence(self) -> None:
        self.assertEqual(
            historical_v3_qualification.DEFAULT_QUALIFICATION.name,
            "event_understanding_qualification_v3.json",
        )
        historical_v3 = json.loads(V3_PATH.read_text(encoding="utf-8"))
        historical_v2 = json.loads(V2_PATH.read_text(encoding="utf-8"))

        self.assertEqual(historical_v3["schema_version"], 3)
        self.assertEqual(historical_v3["source_fixture"], historical_v2["source_fixture"])
        self.assertEqual(historical_v3["cases"], historical_v2["cases"])
        self.assertEqual(historical_v3["scoring_policy"], historical_v2["scoring_policy"])
        self.assertEqual(historical_v3["acceptance"], historical_v2["acceptance"])
        self.assertEqual(historical_v3["provider_policy"], historical_v2["provider_policy"])
        self.assertEqual(historical_v3["core_contract"], "event_understanding_v2")
        self.assertEqual(historical_v3["structured_output_schema"], "event_understanding_schema_v2")

        schema = adapter.EVENT_UNDERSTANDING_SCHEMA_V2
        evidence = schema["properties"]["events"]["items"]["properties"]["evidence"]["items"]
        self.assertEqual(evidence["required"], ["source_id", "field", "text", "start", "end"])

    def test_v3_provider_results_are_preserved_but_stale_under_active_v4(self) -> None:
        status = load_provider_status(STATUS_PATH)
        self.assertEqual(status["contract"], "event_understanding_v2")
        self.assertEqual(status["structured_output_schema"], "event_understanding_schema_v3")
        self.assertEqual(status["active_qualification_protocol"], 4)
        self.assertEqual(status["qualification_contract_status"], "AWAITING_PROVIDER_QUALIFICATION")
        self.assertEqual(status["provider_inventory_status"], NO_ELIGIBLE_EXISTING_PROVIDER)
        self.assertIsNone(status["selected_event_understanding_provider"])
        self.assertFalse(status["production_wired"])

        protocol_three = (
            "mistral_large_3",
            "openrouter_nemotron_free",
            "cohere_command_a_plus",
            "cerebras_glm_47",
            "groq_qwen38_27b",
            "gemini_37_flash",
            "openrouter_glm52_free",
            "openrouter_gpt54mini",
            "openrouter_qwen235b2507_free",
            "hf_qwen235b2507_nscale",
        )
        for provider_id in protocol_three:
            with self.subTest(provider_id=provider_id):
                record = status["providers"][provider_id]
                self.assertEqual(record["qualification_protocol"], 3)
                self.assertLess(record["qualification_protocol"], status["active_qualification_protocol"])

        mistral = status["providers"]["mistral_large_3"]
        self.assertEqual(mistral["status"], "QUALIFICATION_BLOCKED_TRANSIENT")
        self.assertEqual(mistral["raw_run_status"], "NOT_QUALIFIED")
        self.assertEqual(mistral["run_id"], 33094503683)
        self.assertEqual(mistral["failure_classification"], "PROVIDER_TRANSIENT_FAILURE")

        openrouter = status["providers"]["openrouter_nemotron_free"]
        self.assertEqual(openrouter["status"], "NOT_QUALIFIED")
        self.assertEqual(openrouter["run_id"], 33093075809)
        self.assertEqual(openrouter["previous_v2_evidence"]["qualification_protocol"], 2)

        hf = status["providers"]["hf_qwen235b2507_nscale"]
        self.assertEqual(hf["status"], "NOT_QUALIFIED")
        self.assertEqual(hf["run_id"], 33136814090)
        self.assertEqual(hf["failure_classification"], "EVIDENCE_CONTRACT")


if __name__ == "__main__":
    unittest.main()
