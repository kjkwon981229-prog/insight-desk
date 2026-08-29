from __future__ import annotations

import json
from pathlib import Path
import unittest

from insight_desk.event_understanding_provider_status_v2 import (
    load_provider_status,
    validate_provider_status,
)


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"
MIGRATION_GATE_PATH = ROOT / "config/event_understanding_migration_gate_v2.json"


class EventUnderstandingQualificationProtocolV5Tests(unittest.TestCase):
    def test_v5_is_the_active_qualification_protocol(self) -> None:
        status = load_provider_status(STATUS_PATH)
        self.assertEqual(status["active_qualification_protocol"], 5)

    def test_v5_requires_schema_v4(self) -> None:
        status = load_provider_status(STATUS_PATH)
        self.assertEqual(status["structured_output_schema"], "event_understanding_schema_v4")

    def test_non_pass_provider_inventory_remains_blocked(self) -> None:
        status = load_provider_status(STATUS_PATH)
        self.assertEqual(status["provider_inventory_status"], "CANDIDATE_QUALIFICATION_BLOCKED")
        self.assertEqual(status["qualification_contract_status"], "AWAITING_PROVIDER_QUALIFICATION")
        self.assertIsNone(status["selected_event_understanding_provider"])
        self.assertFalse(status["production_wired"])
        self.assertFalse(status["full_production_correctness_claimed"])

    def test_provider_records_use_current_protocol_or_frozen_historical_protocol(self) -> None:
        status = load_provider_status(STATUS_PATH)
        providers = status["providers"]
        self.assertIsInstance(providers, dict)
        self.assertTrue(providers)
        for provider_id, record in providers.items():
            self.assertIn("qualification_protocol", record, provider_id)
            protocol = record["qualification_protocol"]
            self.assertIn(protocol, {3, 4, 5}, provider_id)

    def test_v5_candidate_records_are_not_silently_promoted(self) -> None:
        status = load_provider_status(STATUS_PATH)
        v5_records = [
            record
            for record in status["providers"].values()
            if record.get("qualification_protocol") == 5
        ]
        self.assertTrue(v5_records)
        self.assertTrue(
            all(record.get("status") != "MINIMUM_COMPATIBILITY_PASS" for record in v5_records)
        )

    def test_v4_pass_cannot_be_reused_as_current_selection(self) -> None:
        status = load_provider_status(STATUS_PATH)
        mutated = json.loads(json.dumps(status))
        mutated["providers"]["synthetic_v4_pass"] = {
            "provider": "fixture",
            "model": "fixture-model",
            "status": "MINIMUM_COMPATIBILITY_PASS",
            "qualification_protocol": 4,
            "evaluated_cases": 4,
            "passed_cases": 4,
        }
        mutated["qualification_contract_status"] = "QUALIFIED_PROVIDER_SELECTED"
        mutated["provider_inventory_status"] = "ELIGIBLE_CANDIDATE_AVAILABLE"
        mutated["selected_event_understanding_provider"] = "synthetic_v4_pass"
        with self.assertRaisesRegex(Exception, "stale protocol"):
            validate_provider_status(mutated)

    def test_v5_does_not_open_migration_gate(self) -> None:
        gate = json.loads(MIGRATION_GATE_PATH.read_text(encoding="utf-8"))
        self.assertFalse(gate["production_rewire_allowed"])
        self.assertEqual(len(gate["runtime_blockers"]), 3)
        active = {
            blocker_id
            for blocker_id, item in gate["runtime_blockers"].items()
            if item["active"]
        }
        self.assertEqual(active, {"candidate_event_direct_canonical_lift"})
        self.assertFalse(gate["runtime_blockers"]["identity_reads_source_body"]["active"])
        self.assertFalse(gate["runtime_blockers"]["legacy_candidate_identity_authority"]["active"])


if __name__ == "__main__":
    unittest.main()
