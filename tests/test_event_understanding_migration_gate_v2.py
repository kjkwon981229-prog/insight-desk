from __future__ import annotations

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
    def test_current_phase4_gate_has_no_active_runtime_semantic_bypass(self) -> None:
        gate = load_migration_gate(GATE_PATH, root=ROOT)
        self.assertTrue(gate["production_rewire_allowed"])
        active = {
            blocker_id
            for blocker_id, record in gate["runtime_blockers"].items()
            if record["active"]
        }
        self.assertEqual(active, set())
        self.assertFalse(gate["runtime_blockers"]["identity_reads_source_body"]["active"])
        self.assertFalse(gate["runtime_blockers"]["legacy_candidate_identity_authority"]["active"])

    def test_open_structural_gate_does_not_bypass_unqualified_provider_status(self) -> None:
        provider_status = load_provider_status(STATUS_PATH)
        gate = load_migration_gate(GATE_PATH, root=ROOT)
        with self.assertRaisesRegex(ContractError, "inventory is not eligible"):
            assert_production_rewire_allowed(provider_status, gate, root=ROOT)

    def test_gate_cannot_claim_ready_while_any_blocker_is_active(self) -> None:
        gate = json.loads(GATE_PATH.read_text(encoding="utf-8"))
        blocker = gate["runtime_blockers"]["candidate_event_direct_canonical_lift"]
        blocker["active"] = True
        blocker["evidence"] = "class ProductionV2Registry"
        gate["production_rewire_allowed"] = True
        with self.assertRaisesRegex(ContractError, "runtime blockers"):
            validate_migration_gate(gate, root=ROOT)

    def test_active_blocker_must_have_matching_source_evidence(self) -> None:
        gate = json.loads(GATE_PATH.read_text(encoding="utf-8"))
        gate["production_rewire_allowed"] = False
        blocker = gate["runtime_blockers"]["candidate_event_direct_canonical_lift"]
        blocker["active"] = True
        blocker["evidence"] = "__absent_marker__"
        with self.assertRaisesRegex(ContractError, "source evidence is absent"):
            validate_migration_gate(gate, root=ROOT)


if __name__ == "__main__":
    unittest.main()
