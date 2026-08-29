from __future__ import annotations

from pathlib import Path
import unittest


class SingleEvidenceIntegrityOwnerTests(unittest.TestCase):
    def test_daily_production_does_not_prejudge_material_before_phase6(self) -> None:
        source = Path("scripts/phase11_daily_production_core.py").read_text(encoding="utf-8")
        self.assertNotIn("material = assess_material_event(", source)
        self.assertNotIn("assess_material_event\n", source)
        self.assertIn("assessment = phase6.assess_with_auto_material(", source)
        self.assertIn("assessment.material.verdict", source)

    def test_phase6_bridge_remains_the_evidence_integrity_owner(self) -> None:
        source = Path("insight_desk/production_phase6_v2.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("_evidence_integrity_assessment("), 1)
        self.assertIn("material = _evidence_integrity_assessment(", source)


if __name__ == "__main__":
    unittest.main()
