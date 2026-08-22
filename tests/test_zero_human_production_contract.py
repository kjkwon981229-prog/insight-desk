from __future__ import annotations

import json
from pathlib import Path
import unittest


class ZeroHumanProductionContractTests(unittest.TestCase):
    def test_runtime_requires_no_human(self) -> None:
        data = json.loads(Path("config/zero_human_production_v1.json").read_text(encoding="utf-8"))
        self.assertFalse(data["routine_user_intervention_allowed"])
        self.assertFalse(data["human_annotation_runtime_dependency_allowed"])
        self.assertFalse(data["human_review_publish_dependency_allowed"])
        self.assertEqual(data["offline_human_gold"], "optional_only")
        self.assertFalse(data["paid_fallback_allowed"])
        self.assertFalse(data["phase7_generation_verification_in_scope"])


if __name__ == "__main__":
    unittest.main()
