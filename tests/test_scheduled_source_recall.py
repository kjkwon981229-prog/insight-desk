from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_source_grounded_production_stability_v2 import _ArticleCase, _run_cases
from dataclasses import asdict
from insight_desk.semantic.tooling import KiwiMorphologyHelper
from insight_desk.semantic.kiwi_extractor import _predicate_fact_parts


@unittest.skipUnless(importlib.util.find_spec("kiwipiepy"), "semantic-local required")
class ScheduledSourceRecallTests(unittest.TestCase):
    def test_title_frame_cannot_promote_a_different_object_or_another_actor(self):
        cases = (
            _ArticleCase("different-object", "kpop", "튜넥스, 새 앨범 공개",
                         "튜넥스는 공연 영상을 공개했다. 튜넥스는 새 앨범을 공개했다.", "튜넥스는 새 앨범을 공개했다."),
            _ArticleCase("different-actor", "kpop", "아이브, 새 앨범 공개",
                         "튜넥스는 새 앨범을 공개했다. 아이브는 새 앨범을 공개했다.", "아이브는 새 앨범을 공개했다."),
        )
        outcomes = _run_cases(cases)
        for case in cases:
            with self.subTest(case=case.case_id):
                self.assertEqual(outcomes[case.case_id].proposition, case.expected_proposition)

    def test_second_sentence_bridge_cannot_switch_to_another_named_actor(self):
        case = _ArticleCase(
            "second-sentence-different-actor",
            "kpop",
            "임영웅 '또또' 멜론 1위…새 앨범 전곡 차트인",
            (
                "임영웅이 '또또'를 비롯해 새 앨범 전곡이 차트에 입성했다.\n"
                "아이브가 새 앨범 전곡을 멜론 차트에 진입시켰다."
            ),
            None,
        )
        outcome = _run_cases((case,))[case.case_id]
        self.assertIsNone(outcome.proposition)

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
                details = {"decisions": row["decisions"], "facts": row["semantic_result"]["facts"][:3]}
                if outcome.proposition != case.expected_proposition and case.expected_proposition:
                    morphology = KiwiMorphologyHelper()
                    tokens = morphology.analyze(case.expected_proposition)
                    parts = _predicate_fact_parts(case.expected_proposition, tokens)
                    details["expected_tokens"] = [asdict(t) for t in tokens]
                    details["title_tokens"] = [asdict(t) for t in morphology.analyze(case.title)]
                    details["actor_tokens"] = [asdict(t) for t in morphology.analyze(parts.subject)] if parts else []
                self.assertEqual(outcome.proposition, case.expected_proposition,
                                 json.dumps(details, ensure_ascii=False))
                if case.expected_proposition is not None:
                    self.assertTrue(outcome.exact_provenance)


if __name__ == "__main__":
    unittest.main()
