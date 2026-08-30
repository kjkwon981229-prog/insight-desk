from __future__ import annotations

from pathlib import Path
import unittest


class NoVisibleReadmissionInDailyLoopTests(unittest.TestCase):
    def test_generated_surfaces_are_not_reclassified_after_verification(self) -> None:
        source = Path("scripts/phase11_daily_production_core.py").read_text(encoding="utf-8")
        self.assertNotIn("if not _visible_topic_headline_bound(", source)
        self.assertNotIn("visible_issues = visible_story_issues(", source)
        self.assertNotIn('stage="visible_topic_binding"', source)
        self.assertNotIn('stage="visible_quality"', source)


if __name__ == "__main__":
    unittest.main()
