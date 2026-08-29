from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import unittest

from insight_desk.semantic.baseball_identity import kbo_visible_result_redundant
from insight_desk.semantic.market_identity import same_market_session_close_fingerprint
from insight_desk.story_admission import (
    StoryAdmissionReason,
    StoryAdmissionStage,
    evaluate_story_admission,
)


NOW = datetime(2026, 8, 25, 17, 40, tzinfo=timezone.utc)


class Live320VisibleStoryRegressions(unittest.TestCase):
    def _visible(self, *, topic: str, headline: str, summary: str):
        return evaluate_story_admission(
            topic=topic,
            headline=headline,
            summary=summary,
            source_text=summary,
            stage=StoryAdmissionStage.VISIBLE,
            now=NOW,
        )

    def test_anonymous_company_after_subjectless_stock_clause_is_not_standalone(self) -> None:
        decision = self._visible(
            topic="AI·테크",
            headline="순환 거래 논란 부추기며 AI 재투자",
            summary=(
                "주가가 압박을 받고 있는 가운데, 회사가 수십억 달러를 AI 생태계에 "
                "재투자해 이른바 '순환 거래' 논란을 부추기고 있다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_named_nvidia_actor_remains_standalone(self) -> None:
        decision = self._visible(
            topic="AI·테크",
            headline="엔비디아, AI 생태계 재투자에 순환 거래 우려",
            summary=(
                "엔비디아 주가가 압박을 받는 가운데 엔비디아가 수십억 달러를 AI 생태계에 "
                "재투자하면서 순환 거래 우려가 커지고 있다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live320VisibleIdentityRegressions(unittest.TestCase):
    KBO_PRIOR_HEADLINE = "SSG, 한화전 7-1 승리 기록"
    KBO_PRIOR_SUMMARY = (
        "지난 25일 인천 SSG랜더스필드에서 열린 2026 신한 SOL Bank KBO리그 "
        "한화 이글스와의 경기에서 SSG가 7-1로 승리했다."
    )
    KBO_CANDIDATE_HEADLINE = "한화, SSG전 1-7 패배로 2연패"
    KBO_CANDIDATE_SUMMARY = (
        "25일 인천 SSG랜더스필드에서 열린 2026 신한은행 SOL Bank KBO리그 "
        "SSG 랜더스와의 경기에서 한화가 1-7로 패하며 2연패를 기록했다."
    )

    MARKET_PRIOR = (
        "25일 코스피 6742.74로 마감. 25일 코스피는 전 거래일 대비 "
        "45.78포인트(0.68%) 상승한 6742.74에 장을 마쳤다."
    )
    MARKET_CANDIDATE = (
        "개인·기관 매수세 속 국내 증시 상승 마감. 25일 하락 출발했던 국내 증시가 "
        "장 초반 4% 넘게 떨어졌으나 개인과 기관의 매수세가 유입되면서 "
        "장중 낙폭을 회복하고 상승세로 마감했다."
    )

    def test_live_kbo_reciprocal_result_is_visible_redundancy(self) -> None:
        self.assertTrue(
            kbo_visible_result_redundant(
                prior_headline=self.KBO_PRIOR_HEADLINE,
                prior_summary=self.KBO_PRIOR_SUMMARY,
                candidate_headline=self.KBO_CANDIDATE_HEADLINE,
                candidate_summary=self.KBO_CANDIDATE_SUMMARY,
            )
        )

    def test_kbo_different_day_is_not_visible_redundancy(self) -> None:
        self.assertFalse(
            kbo_visible_result_redundant(
                prior_headline=self.KBO_PRIOR_HEADLINE,
                prior_summary=self.KBO_PRIOR_SUMMARY,
                candidate_headline=self.KBO_CANDIDATE_HEADLINE,
                candidate_summary=self.KBO_CANDIDATE_SUMMARY.replace("25일", "24일", 1),
            )
        )

    def test_live_market_pair_is_same_session_close_fingerprint(self) -> None:
        self.assertTrue(
            same_market_session_close_fingerprint(self.MARKET_PRIOR, self.MARKET_CANDIDATE)
        )

    def test_market_different_day_is_not_same_session_close_fingerprint(self) -> None:
        self.assertFalse(
            same_market_session_close_fingerprint(
                self.MARKET_PRIOR,
                self.MARKET_CANDIDATE.replace("25일", "24일", 1),
            )
        )

    def test_daily_production_no_longer_dispatches_generated_text_as_event_identity(self) -> None:
        source = Path("scripts/phase11_daily_production_core.py").read_text(encoding="utf-8")
        self.assertNotIn("if visible_event_redundant(", source)
        self.assertNotIn('reason="visible_event_fingerprint_already_published"', source)
        self.assertIn("precheck = compare_candidate_identity(", source)
        self.assertIn("disposition = identity_disposition(", source)


if __name__ == "__main__":
    unittest.main()
