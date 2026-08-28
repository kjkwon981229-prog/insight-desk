from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from insight_desk.core.contracts import ContractError
from insight_desk import event_understanding_adapter_v3 as adapter_v4
from insight_desk.event_understanding_provider_status_v2 import (
    CANDIDATE_QUALIFICATION_BLOCKED,
    ELIGIBLE_CANDIDATE_AVAILABLE,
    MINIMUM_COMPATIBILITY_PASS,
    NO_ELIGIBLE_EXISTING_PROVIDER,
    QUALIFICATION_BLOCKED_TRANSIENT,
    QUALIFIED_PROVIDER_SELECTED,
    load_provider_status,
    selected_provider,
    validate_provider_status,
)
from scripts import qualify_event_understanding_provider as historical_v3_qualification
from scripts import qualify_event_understanding_provider_v4 as qualification


ROOT = Path(__file__).resolve().parents[1]
V3_PATH = ROOT / "tests/fixtures/event_understanding_qualification_v3.json"
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"


class EventUnderstandingQualificationProtocolV4Tests(unittest.TestCase):
    def test_v4_is_active_without_rewriting_v3_semantic_gold(self) -> None:
        self.assertEqual(
            qualification.DEFAULT_QUALIFICATION.name,
            "event_understanding_qualification_v4.json",
        )
        self.assertEqual(
            historical_v3_qualification.DEFAULT_QUALIFICATION.name,
            "event_understanding_qualification_v3.json",
        )
        active = json.loads(qualification.DEFAULT_QUALIFICATION.read_text(encoding="utf-8"))
        historical_v3 = json.loads(V3_PATH.read_text(encoding="utf-8"))

        self.assertEqual(active["schema_version"], 4)
        self.assertEqual(active["source_fixture"], historical_v3["source_fixture"])
        self.assertEqual(active["cases"], historical_v3["cases"])
        self.assertEqual(active["scoring_policy"], historical_v3["scoring_policy"])
        self.assertEqual(active["acceptance"], historical_v3["acceptance"])
        self.assertEqual(active["provider_policy"], historical_v3["provider_policy"])
        self.assertEqual(active["core_contract"], "event_understanding_v2")
        self.assertEqual(active["structured_output_schema"], "event_understanding_schema_v3")

        evidence = adapter_v4.EVENT_UNDERSTANDING_SCHEMA_V3[
            "properties"
        ]["events"]["items"]["properties"]["evidence"]["items"]
        self.assertEqual(evidence["required"], ["source_id", "field", "text"])
        self.assertNotIn("start", evidence["properties"])
        self.assertNotIn("end", evidence["properties"])

    def test_machine_status_moves_to_v4_and_v3_results_become_stale_evidence(self) -> None:
        status = load_provider_status(STATUS_PATH)
        self.assertEqual(status["structured_output_schema"], "event_understanding_schema_v3")
        self.assertEqual(status["active_qualification_protocol"], 4)
        self.assertEqual(status["provider_inventory_status"], NO_ELIGIBLE_EXISTING_PROVIDER)
        self.assertIsNone(status["selected_event_understanding_provider"])
        self.assertFalse(status["production_wired"])

        for provider_id, record in status["providers"].items():
            if record.get("qualification_protocol") is None:
                continue
            with self.subTest(provider_id=provider_id):
                self.assertLess(record["qualification_protocol"], 4)

    def test_stale_v3_block_does_not_count_as_current_protocol_block(self) -> None:
        payload = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
        self.assertEqual(payload["provider_inventory_status"], NO_ELIGIBLE_EXISTING_PROVIDER)
        validate_provider_status(payload)

    def test_current_v4_transient_block_requires_blocked_inventory(self) -> None:
        payload = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
        mutated = deepcopy(payload)
        mutated["providers"]["v4_transient"] = {
            "provider": "fixture",
            "model": "fixture-v4-model",
            "status": QUALIFICATION_BLOCKED_TRANSIENT,
            "qualification_protocol": 4,
            "evaluated_cases": 4,
            "passed_cases": 0,
            "case_failures": {
                "case-1": ["provider_transport:transient_provider"],
            },
        }
        with self.assertRaisesRegex(ContractError, "CANDIDATE_QUALIFICATION_BLOCKED"):
            validate_provider_status(mutated)

        mutated["provider_inventory_status"] = CANDIDATE_QUALIFICATION_BLOCKED
        validate_provider_status(mutated)

    def test_only_current_v4_pass_can_be_selected(self) -> None:
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
        validate_provider_status(mutated)
        self.assertEqual(selected_provider(mutated), "v4_pass")

        stale = deepcopy(mutated)
        stale["providers"]["v4_pass"]["qualification_protocol"] = 3
        with self.assertRaisesRegex(ContractError, "stale protocol"):
            validate_provider_status(stale)


if __name__ == "__main__":
    unittest.main()
