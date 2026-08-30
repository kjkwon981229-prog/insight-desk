from __future__ import annotations

from datetime import datetime, timezone
import unittest

from scripts import phase11_daily_production as production
from insight_desk.story_admission import (
    StoryAdmissionReason,
    StoryAdmissionStage,
    evaluate_story_admission,
)


NOW = datetime(2026, 8, 25, 14, 25, tzinfo=timezone.utc)


class Live292VisibleStoryRegressions(unittest.TestCase):
    def _visible(self, *, topic: str, headline: str, summary: str):
        return evaluate_story_admission(
            topic=topic,
            headline=headline,
            summary=summary,
            source_text=summary,
            stage=StoryAdmissionStage.VISIBLE,
            now=NOW,
        )

    def test_editorial_admonition_is_not_a_daily_event(self) -> None:
        decision = self._visible(
            topic="AI·테크",
            headline="반도체 특수 영원 착각 곤란",
            summary="하지만 반도체 특수가 영원할 것이라고 착각해서는 곤란하다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_named_current_semiconductor_announcement_remains_accepted(self) -> None:
        decision = self._visible(
            topic="AI·테크",
            headline="삼성전자, 25일 AI 반도체 투자 계획 발표",
            summary="삼성전자는 25일 AI 반도체 생산설비 투자 계획을 발표했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)

    def test_promotional_training_benefit_copy_is_not_daily_news(self) -> None:
        decision = self._visible(
            topic="엔터·음악·K-POP",
            headline="SM Universe 강사진, K-pop 댄스 전문 안무 교육 제공",
            summary=(
                "SM Universe 강사진이 직접 K-pop 댄스 안무교육을 진행해 전문성을 더했다. "
                "청소년들은 팀별 공연을 준비하며 협동심과 자신감을 쌓았다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_named_current_kpop_training_launch_remains_accepted(self) -> None:
        decision = self._visible(
            topic="엔터·음악·K-POP",
            headline="SM Universe, 25일 청소년 K-pop 교육 프로그램 시작",
            summary="SM Universe는 25일 청소년 대상 K-pop 교육 프로그램을 시작했다고 밝혔다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)

    def test_generic_team_participation_sentence_is_not_a_kbo_event(self) -> None:
        decision = self._visible(
            topic="KBO·한화 이글스",
            headline="25일 기아챔피언스필드에서 한화 이글스와 KIA 타이거즈 대결",
            summary=(
                "KIA는 25일 전남광주 기아챔피언스필드에서 열린 2026 신한 SOL KBO리그 "
                "한화 이글스와 KIA 타이거즈의 경기에서 출전했다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_concrete_kia_hanwha_result_remains_accepted(self) -> None:
        decision = self._visible(
            topic="KBO·한화 이글스",
            headline="KIA, 광주에서 한화 5-3 제압",
            summary="KIA는 25일 광주에서 한화 이글스를 5-3으로 꺾었다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live292KboVisibleRedundancyRegressions(unittest.TestCase):
    def _gate(self):
        gate = getattr(production, "kbo_visible_result_redundant", None)
        self.assertTrue(callable(gate), "production requires a conservative KBO result-subset gate")
        return gate

    def test_score_specific_result_suppresses_same_winner_generic_result(self) -> None:
        gate = self._gate()
        self.assertTrue(
            gate(
                prior_headline="SSG 랜더스가 6회에만 대거 점수를 뽑아 한화 이글스를 7-1로 제압",
                prior_summary="인천에서 SSG 랜더스가 6회에만 대거 점수를 뽑아 한화 이글스를 7-1로 제압했다.",
                candidate_headline="SSG 랜더스가 한화 이글스를 완파",
                candidate_summary="인천에서는 SSG 랜더스가 한화 이글스를 완파했다.",
            )
        )

    def test_two_distinct_scored_results_are_not_collapsed(self) -> None:
        gate = self._gate()
        self.assertFalse(
            gate(
                prior_headline="SSG, 한화 7-1 제압",
                prior_summary="인천에서 SSG가 한화를 7-1로 꺾었다.",
                candidate_headline="SSG, 한화 3-2 제압",
                candidate_summary="인천에서 SSG가 한화를 3-2로 꺾었다.",
            )
        )

    def test_opposite_winner_is_not_collapsed(self) -> None:
        gate = self._gate()
        self.assertFalse(
            gate(
                prior_headline="SSG, 한화 7-1 제압",
                prior_summary="인천에서 SSG가 한화를 7-1로 꺾었다.",
                candidate_headline="한화, SSG 완파",
                candidate_summary="인천에서 한화가 SSG를 완파했다.",
            )
        )

    def test_different_opponent_or_venue_is_not_collapsed(self) -> None:
        gate = self._gate()
        self.assertFalse(
            gate(
                prior_headline="SSG, 한화 7-1 제압",
                prior_summary="인천에서 SSG가 한화를 7-1로 꺾었다.",
                candidate_headline="SSG, 한화 완파",
                candidate_summary="대전에서 SSG가 한화를 완파했다.",
            )
        )
        self.assertFalse(
            gate(
                prior_headline="SSG, 한화 7-1 제압",
                prior_summary="인천에서 SSG가 한화를 7-1로 꺾었다.",
                candidate_headline="SSG, KIA 완파",
                candidate_summary="인천에서 SSG가 KIA를 완파했다.",
            )
        )


if __name__ == "__main__":
    unittest.main()
