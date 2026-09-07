from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import unittest

from test_source_grounded_production_stability_v2 import _ArticleCase, _run_cases


@unittest.skipUnless(importlib.util.find_spec("kiwipiepy"), "semantic-local required")
class ScheduledSourceRecallTests(unittest.TestCase):
    def test_captured_fresh_sources_preserve_includes_and_reject_incidental_hanwha(self):
        cases = tuple(_ArticleCase(**row) for row in json.loads(
            Path("tests/fixtures/scheduled_recall_20260907.json").read_text()))
        outcomes = _run_cases(cases, clocks={
            case.case_id: datetime(2026, 9, 7, 8, tzinfo=timezone.utc) for case in cases
        })
        for case in cases:
            with self.subTest(case=case.case_id):
                outcome = outcomes[case.case_id]
                self.assertEqual(outcome.proposition, case.expected_proposition)
                if case.expected_proposition is not None:
                    self.assertTrue(outcome.exact_provenance)


if __name__ == "__main__":
    unittest.main()
