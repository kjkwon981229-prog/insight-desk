from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from insight_desk.core.contracts import ContractError
from insight_desk import event_understanding_adapter_v3 as adapter_v4
from insight_desk.event_understanding_provider_status_v2 import (
    ELIGIBLE_CANDIDATE_AVAILABLE,
    MINIMUM_COMPATIBILITY_PASS,
    QUALIFIED_PROVIDER_SELECTED,
    load_provider_status,
    validate_provider_status,
)
from scripts import qualify_event_understanding_provider as historical_v3_qualification
from scripts import qualify_event_understanding_provider_v4 as qualification


ROOT = Path(__file__).resolve().parents[1]
V3_PATH = ROOT / "tests/fixtures/event_understanding_qualification_v3.json"
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"


class EventUnderstandingQualificationProtocolV4Tests(unittest.TestCase):
    def test_v4_contract_remains_frozen_without_rewriting_v3_semantic_gold(self) -> None:
        self.assertEqual(
            qualification.DEFAULT_QUALIFICATION.name,
            "event_understanding_qualification_v4.json",
        )
        self.assertEqual(
            historical_v3_qualification.DEFAULT_QUALIFICATION.name,
            "event_understanding_qualification_v3.json",
        )
        v4 = json.loads(qualification.DEFAULT_QUALIFICATION.read_text(encoding="utf-8"))
        historical_v3 = json.loads(V3_PATH.read_text(encoding="utf-8"))

        self.assertEqual(v4["schema_version"], 4)
        self.assertEqual(v4["source_fixture"], historical_v3["source_fixture"])
        self.assertEqual(v4["cases"], historical_v3["cases"])
        self.assertEqual(v4["scoring_policy"], historical_v3["scoring_policy"])
        self.assertEqual(v4["acceptance"], historical_v3["acceptance"])
        self.assertEqual(v4["provider_policy"], historical_v3["provider_policy"])
        self.assertEqual(v4["core_contract"], "event_understanding_v2")
        self.assertEqual(v4["structured_output_schema"], "event_understanding_schema_v3")

        evidence = adapter_v4.EVENT_UNDERSTANDING_SCHEMA_V3[
            "properties"
        ]["events"]["items"]["properties"]["evidence"]["items"]
        self.assertEqual(evidence["required"], ["source_id", "field", "text"])
        self.assertNotIn("start", evidence["properties"])
        self.assertNotIn("end", evidence["properties"])

    def test_machine_status_preserves_all_frozen_v4_nonpass_evidence_as_stale(self) -> None:
        status = load_provider_status(STATUS_PATH)
        self.assertGreater(status["active_qualification_protocol"], 4)
        self.assertIsNone(status["selected_event_understanding_provider"])
        self.assertFalse(status["production_wired"])

        frozen_v4: list[str] = []
        for provider_id, record in status["providers"].items():
            protocol = record.get("qualification_protocol")
            if protocol == 4:
                frozen_v4.append(provider_id)
                with self.subTest(provider_id=provider_id):
                    self.assertLess(protocol, status["active_qualification_protocol"])

        self.assertEqual(
            frozen_v4,
            [
                "gemini_35_flash_v4",
                "gemini_36_flash_v4",
                "gemini_25_pro_v4",
                "gemini_35_flash_lite_v4",
                "gemini_25_flash_v4",
                "hf_qwen36_35b_deepinfra_v4",
                "cerebras_gemma4_31b_v4",
            ],
        )
        self.assertEqual(status["providers"]["gemini_35_flash_v4"]["passed_cases"], 3)
        self.assertEqual(status["providers"]["gemini_36_flash_v4"]["passed_cases"], 3)
        self.assertEqual(status["providers"]["gemini_35_flash_lite_v4"]["passed_cases"], 1)
        self.assertEqual(
            status["providers"]["hf_qwen36_35b_deepinfra_v4"]["failure_classification"],
            "MIXED_INVALID_OUTPUT_AND_TRANSIENT_FAILURE",
        )
        self.assertEqual(
            status["providers"]["cerebras_gemma4_31b_v4"]["failure_classification"],
            "ZERO_COST_ACCESS_UNAVAILABLE",
        )

    def test_v4_transient_block_is_historical_and_cannot_block_active_inventory(self) -> None:
        payload = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
        mutated = deepcopy(payload)
        mutated["providers"]["historical_v4_transient"] = {
            "provider": "fixture",
            "model": "fixture-v4-model",
            "status": "QUALIFICATION_BLOCKED_TRANSIENT",
            "qualification_protocol": 4,
            "evaluated_cases": 4,
            "passed_cases": 0,
            "case_failures": {"case-1": ["provider_transport:transient_provider"]},
        }
        validate_provider_status(mutated)

    def test_v4_pass_is_preserved_but_cannot_be_selected_under_newer_protocol(self) -> None:
        payload = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
        mutated = deepcopy(payload)
        mutated["provider_inventory_status"] = ELIGIBLE_CANDIDATE_AVAILABLE
        mutated["qualification_contract_status"] = QUALIFIED_PROVIDER_SELECTED
        mutated["providers"]["v4_pass"] = {
            "provider": "fixture",
            "model": "fixture-v4-model",
            "status": MINIMUM_COMPATIBILITY_PASS,
            "qualification_protocol": 4,
            "evaluated_cases": 4,
            "passed_cases": 4,
        }
        mutated["selected_event_understanding_provider"] = "v4_pass"
        with self.assertRaisesRegex(ContractError, "stale protocol"):
            validate_provider_status(mutated)


if __name__ == "__main__":
    unittest.main()
