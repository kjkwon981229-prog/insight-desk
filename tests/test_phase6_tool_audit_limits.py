from __future__ import annotations

import json
from pathlib import Path
import unittest


class Phase6ToolAuditLimitsTests(unittest.TestCase):
    def test_audit_is_bounded(self) -> None:
        data = json.loads(Path("config/phase6_tool_audit_limits_v1.json").read_text(encoding="utf-8"))
        self.assertLessEqual(data["max_new_runtime_tool_candidates"], 3)
        self.assertLessEqual(data["max_canary_rounds_per_candidate"], 2)
        self.assertEqual(data["new_general_llm_candidates_allowed"], 0)
        self.assertEqual(data["paid_candidates_allowed"], 0)
        self.assertEqual(data["routine_human_steps_allowed"], 0)
        self.assertEqual(data["benchmark_specific_exception_rules_allowed"], 0)


if __name__ == "__main__":
    unittest.main()
