from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_source_grounded_production_stability_v2 import _ArticleCase, _run_cases


@unittest.skipUnless(importlib.util.find_spec("kiwipiepy"), "semantic-local required")
class ScheduledSourceRecallTests(unittest.TestCase):
    def test_title_frame_cannot_promote_a_different_object_or_another_actor(self):
        cases = (
            _ArticleCase("different-object", "kpop", "튜넥스, 새 앨범 공개",
                         "튜넥스는 공연 영상을 공개했다. 튜넥스는 새 앨범을 공개했다.", None),
            _ArticleCase("different-actor", "kpop", "아이브, 새 앨범 공개",
                         "튜넥스는 새 앨범을 공개했다. 아이브는 새 앨범을 공개했다.", None),
        )
        outcomes = _run_cases(cases)
        for case in cases:
            with self.subTest(case=case.case_id):
                self.assertFalse(outcomes[case.case_id].published)

    def test_captured_fresh_sources_preserve_includes_and_reject_incidental_hanwha(self):
        cases = tuple(_ArticleCase(**row) for row in json.loads(
            Path("tests/fixtures/scheduled_recall_20260907.json").read_text()))
        with tempfile.TemporaryDirectory() as temp:
            diagnostic = Path(temp) / "understanding.jsonl"
            with patch.dict(os.environ, {"INSIGHT_DESK_UNDERSTANDING_DIAGNOSTICS": str(diagnostic)}):
                outcomes = _run_cases(cases, clocks={
                    case.case_id: datetime(2026, 9, 7, 8, tzinfo=timezone.utc) for case in cases
                })
            recorded = {row["source"]["url"]: row for row in
                        map(json.loads, diagnostic.read_text().splitlines())}
        for case in cases:
            with self.subTest(case=case.case_id):
                outcome = outcomes[case.case_id]
                row = recorded[case.source_url]
                details = {"decisions": row["decisions"], "facts": row["semantic_result"]["facts"]}
                self.assertEqual(outcome.proposition, case.expected_proposition,
                                 json.dumps(details, ensure_ascii=False))
                if case.expected_proposition is not None:
                    self.assertTrue(outcome.exact_provenance)


if __name__ == "__main__":
    unittest.main()
