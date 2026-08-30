from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from insight_desk.core.contracts import ContractError
from insight_desk.event_understanding_migration_gate_v2 import (
    assert_production_rewire_allowed,
    load_migration_gate,
    validate_migration_gate,
)
from insight_desk.event_understanding_provider_status_v2 import load_provider_status


ROOT = Path(__file__).resolve().parents[1]
GATE_PATH = ROOT / "config/event_understanding_migration_gate_v2.json"
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"


class EventUnderstandingMigrationGateV2Tests(unittest.TestCase):
    def test_current_phase4_gate_is_truthfully_blocked_only_by_unqualified_legacy_handoff(self) -> None:
        gate = load_migration_gate(GATE_PATH, root=ROOT)
        self.assertFalse(gate["production_rewire_allowed"])
        active = {
            blocker_id
            for blocker_id, record in gate["runtime_blockers"].items()
            if record["active"]
        }
        self.assertEqual(active, {"candidate_event_direct_canonical_lift"})
        self.assertFalse(gate["runtime_blockers"]["identity_reads_source_body"]["active"])
        self.assertFalse(gate["runtime_blockers"]["legacy_candidate_identity_authority"]["active"])

    def test_provider_pass_alone_cannot_open_production_rewire(self) -> None:
        provider_status = deepcopy(load_provider_status(STATUS_PATH))
        active_protocol = provider_status["active_qualification_protocol"]
        provider_status["providers"]["qualified_fixture"] = {
            "provider": "fixture",
            "model": "fixture-model",
            "status": "MINIMUM_COMPATIBILITY_PASS",
            "qualification_protocol": active_protocol,
            "evaluated_cases": 4,
            "passed_cases": 4,
        }
        provider_status["qualification_contract_status"] = "QUALIFIED_PROVIDER_SELECTED"
        provider_status["provider_inventory_status"] = "ELIGIBLE_CANDIDATE_AVAILABLE"
        provider_status["selected_event_understanding_provider"] = "qualified_fixture"
        provider_status["production_wired"] = False
        gate = load_migration_gate(GATE_PATH, root=ROOT)
        with self.assertRaisesRegex(ContractError, "runtime bypasses"):
            assert_production_rewire_allowed(provider_status, gate, root=ROOT)

    def test_gate_cannot_claim_ready_while_any_blocker_is_active(self) -> None:
        gate = json.loads(GATE_PATH.read_text(encoding="utf-8"))
        gate["production_rewire_allowed"] = True
        with self.assertRaisesRegex(ContractError, "runtime blockers"):
            validate_migration_gate(gate, root=ROOT)

    def test_active_blocker_must_have_matching_source_evidence(self) -> None:
        gate = json.loads(GATE_PATH.read_text(encoding="utf-8"))
        gate["runtime_blockers"]["candidate_event_direct_canonical_lift"]["evidence"] = "__absent_marker__"
        with self.assertRaisesRegex(ContractError, "source evidence is absent"):
            validate_migration_gate(gate, root=ROOT)


if __name__ == "__main__":
    unittest.main()
