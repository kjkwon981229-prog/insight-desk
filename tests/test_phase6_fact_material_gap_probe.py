from __future__ import annotations

import json
from pathlib import Path
import unittest


class Phase6GapProbeTests(unittest.TestCase):
    def test_run96_selection_negatives_are_not_material_gold(self) -> None:
        data = json.loads(Path("benchmarks/run96_recall_precision.json").read_text(encoding="utf-8"))
        self.assertGreater(len(data["true_negative_titles"]), 0)
        self.assertNotIn("material_event_gold", data)

    def test_audit_requires_zero_user_intervention(self) -> None:
        data = json.loads(
            Path("config/phase6_fact_material_tool_candidates_v1.json").read_text(encoding="utf-8")
        )
        self.assertEqual(data["hard_constraints"]["operating_cost_krw"], 0)
        self.assertEqual(data["hard_constraints"]["user_intervention_required"], 0)
        self.assertFalse(data["hard_constraints"]["paid_fallback"])


if __name__ == "__main__":
    unittest.main()
