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
from insight_desk.feed_quality import VisibleStoryIssue, visible_story_issues
from insight_desk.semantic.tooling import KiwiMorphologyHelper
from insight_desk.semantic.kiwi_extractor import _predicate_fact_parts


@unittest.skipUnless(importlib.util.find_spec("kiwipiepy"), "semantic-local required")
class ScheduledSourceRecallTests(unittest.TestCase):
    def test_routine_presence_needs_a_same_proposition_outcome(self):
        routine = (
            "중소기업기술정보진흥원은 김영신 원장이 지난 8일 반도체 공정용 소재·부품 "
            "전문기업 ‘씨엠티엑스(CMTX)’를 방문했다고 9일 밝혔다."
        )
        consequential = (
            "새빛연구소 대표는 오늘 AI 반도체 공장을 방문해 엔비디아와 HBM 공급계약을 "
            "체결했다고 밝혔다."
        )
        cases = (
            _ArticleCase(
                "routine-presence",
                "ai_tech",
                "김영신 기정원장, 씨엠티엑스 찾아 글로벌 진출방안 모색",
                routine,
                None,
            ),
            _ArticleCase(
                "presence-with-outcome",
                "ai_tech",
                "새빛연구소·엔비디아, AI 반도체 HBM 공급계약 체결",
                consequential,
                consequential,
            ),
        )
        outcomes = _run_cases(cases)
        self.assertIsNone(outcomes["routine-presence"].proposition)
        self.assertEqual(outcomes["presence-with-outcome"].proposition, consequential)
        self.assertIn(
            VisibleStoryIssue.NON_EVENT_ANALYTICAL_SUMMARY,
            visible_story_issues(topic="AI·테크", headline=routine, summary=routine),
        )

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
                    case.case_id: datetime(
                        2026,
                        9,
                        9 if "20260909" in case.case_id else 8 if "20260908" in case.case_id else 7,
                        8,
                        tzinfo=timezone.utc,
                    )
                    for case in cases
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
