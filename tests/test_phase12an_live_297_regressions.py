from __future__ import annotations

from datetime import datetime, timezone
import unittest

from scripts import phase11_daily_production as production
from insight_desk.story_admission import (
    StoryAdmissionReason,
    StoryAdmissionStage,
    evaluate_story_admission,
)


NOW = datetime(2026, 8, 25, 15, 3, tzinfo=timezone.utc)


class Live297VisibleStoryRegressions(unittest.TestCase):
    def _visible(self, *, topic: str, headline: str, summary: str):
        return evaluate_story_admission(
            topic=topic,
            headline=headline,
            summary=summary,
            source_text=summary,
            stage=StoryAdmissionStage.VISIBLE,
            now=NOW,
        )

    def test_market_attention_to_upcoming_earnings_is_not_daily_event(self) -> None:
        decision = self._visible(
            topic="AI·테크",
            headline="인공지능 반도체 대표주 엔비디아 실적 발표 주목",
            summary="시장의 관심은 인공지능(AI) 반도체 대표주인 엔비디아의 실적 발표에 쏠리고 있다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_actual_named_earnings_release_remains_accepted(self) -> None:
        decision = self._visible(
            topic="AI·테크",
            headline="엔비디아, 25일 분기 실적 발표",
            summary="엔비디아는 25일 분기 실적을 발표했다고 밝혔다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)

    def test_commentary_about_rate_hike_losing_force_is_not_daily_event(self) -> None:
        decision = self._visible(
            topic="경제·금융시장",
            headline="한국은행 금리 인상, 빛을 잃다",
            summary="한국은행이 기준금리를 올려서 ‘돈줄’을 죄겠다는 말은 빛을 잃도록 해주고 있다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_actual_current_rate_change_remains_accepted(self) -> None:
        decision = self._visible(
            topic="경제·금융시장",
            headline="한국은행, 25일 기준금리 인상",
            summary="한국은행은 25일 기준금리를 0.25%포인트 인상했다고 밝혔다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)

    def test_leading_dateline_byline_is_visible_metadata(self) -> None:
        decision = self._visible(
            topic="경제·금융시장",
            headline="원 환율이 1,380원대 중반으로 반등했다",
            summary="(서울=연합인포맥스) 김지연 기자 = 달러-원 환율이 1,380원대 중반으로 반등했다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.METADATA, decision.reasons)

    def test_plain_current_market_move_remains_accepted(self) -> None:
        decision = self._visible(
            topic="경제·금융시장",
            headline="원 환율 1,380원대 중반 반등",
            summary="달러-원 환율이 25일 1,380원대 중반으로 반등했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live297KboSameScoredGameRegressions(unittest.TestCase):
    def _gate(self):
        gate = getattr(production, "kbo_visible_result_redundant", None)
        self.assertTrue(callable(gate))
        return gate

    def test_reciprocal_scored_reports_of_same_game_are_redundant(self) -> None:
        gate = self._gate()
        self.assertTrue(
            gate(
                prior_headline="한화 이글스, SSG전 1-7 패배로 연패 기록",
                prior_summary=(
                    "김경문 감독이 이끄는 한화 이글스가 25일 인천 SSG랜더스필드에서 열린 "
                    "SSG 랜더스와의 시즌 13차전에서 1-7로 패하며 연패에 빠졌다."
                ),
                candidate_headline="SSG 랜더스, 6회 대량 득점으로 한화 제압",
                candidate_summary="인천에서 열린 경기에서 SSG 랜더스가 6회말 6점을 득점하며 한화를 7-1로 완파했다.",
            )
        )

    def test_same_score_with_conflicting_winner_is_not_collapsed(self) -> None:
        gate = self._gate()
        self.assertFalse(
            gate(
                prior_headline="SSG, 한화 7-1 제압",
                prior_summary="25일 인천에서 SSG가 한화를 7-1로 꺾었다.",
                candidate_headline="한화, SSG 7-1 제압",
                candidate_summary="인천에서 한화가 SSG를 7-1로 꺾었다.",
            )
        )

    def test_explicit_different_days_remain_separate_even_with_same_score(self) -> None:
        gate = self._gate()
        self.assertFalse(
            gate(
                prior_headline="SSG, 한화 7-1 제압",
                prior_summary="25일 인천에서 SSG가 한화를 7-1로 꺾었다.",
                candidate_headline="SSG, 한화 7-1 제압",
                candidate_summary="24일 인천에서 SSG가 한화를 7-1로 꺾었다.",
            )
        )


if __name__ == "__main__":
    unittest.main()
