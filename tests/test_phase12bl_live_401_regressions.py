from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.semantic.visible_identity import visible_event_redundant
from insight_desk.story_admission import StoryAdmissionReason, StoryAdmissionStage, evaluate_story_admission


NOW = datetime(2026, 8, 26, 14, 15, tzinfo=timezone.utc)


def visible(*, topic: str, headline: str, summary: str):
    return evaluate_story_admission(
        topic=topic,
        headline=headline,
        summary=summary,
        source_text=summary,
        stage=StoryAdmissionStage.VISIBLE,
        now=NOW,
    )


class Live401SurnameOnlyCorporateRoleRegressions(unittest.TestCase):
    def test_live_surname_only_chairman_is_not_standalone_identity(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="박 회장, 반도체 세수 100조원 추가 세금 논의",
            summary='박 회장은 "(1년에) 100조원 세금을 더 걷을 수 있으면 한국이 더 좋아질 것이다"라고 밝혔다.',
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_generalized_surname_only_chairman_is_not_standalone_identity(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="김 회장, AI 반도체 투자 확대 계획 발표",
            summary="김 회장은 26일 AI 반도체 투자 확대 계획을 발표했다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_full_corporate_leader_name_remains_publishable(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="김철수 회장, AI 반도체 투자 확대 계획 발표",
            summary="김철수 회장은 26일 AI 반도체 투자 확대 계획을 발표했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live401StatisticalMetricActorLossRegressions(unittest.TestCase):
    def test_live_pce_movement_headline_cannot_drop_metric_actor(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="0.2% 올라 6월 0.1% 하락에서 상승으로 전환했다",
            summary="전월 대비 PCE 물가는 0.2% 올라 6월 0.1% 하락에서 상승으로 전환했다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_generalized_statistical_movement_headline_cannot_drop_metric_actor(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="0.3% 올라 전월 0.1% 하락에서 상승으로 전환했다",
            summary="전월 대비 CPI 물가는 0.3% 올라 전월 0.1% 하락에서 상승으로 전환했다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_statistical_movement_with_metric_actor_remains_publishable(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="PCE 물가, 0.2% 올라 전월 하락에서 상승 전환",
            summary="전월 대비 PCE 물가는 0.2% 올라 6월 0.1% 하락에서 상승으로 전환했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live401StaticFanclubHistoryRegressions(unittest.TestCase):
    def test_live_fanclub_identity_and_support_history_is_not_a_current_event(self) -> None:
        decision = visible(
            topic="엔터·음악·K-POP",
            headline="'ABNEW'로, 팬들은 음반 활동과 콘서트, 단독 공연 현장에서 응원봉과 응원법으로 팀의 행보를 함께해 왔다",
            summary="공식 팬클럽명은 'ABNEW'로, 팬들은 음반 활동과 콘서트, 단독 공연 현장에서 응원봉과 응원법으로 팀의 행보를 함께해 왔다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_generalized_fanclub_identity_and_support_history_is_not_a_current_event(self) -> None:
        decision = visible(
            topic="엔터·음악·K-POP",
            headline="K-POP 그룹 공식 팬클럽 'STAR', 팬들과 공연 응원 문화 이어와",
            summary="공식 팬클럽명은 'STAR'로, K-POP 팬들은 음반 활동과 콘서트 현장에서 응원봉과 응원법으로 팀을 응원해 왔다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_current_fan_event_remains_publishable(self) -> None:
        decision = visible(
            topic="엔터·음악·K-POP",
            headline="AB6IX, 26일 팬 콘서트 일정 공개",
            summary="AB6IX는 26일 공식 팬 콘서트 일정과 공연 장소를 공개했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live401SourceBackedSameGameDuplicateRegressions(unittest.TestCase):
    def test_live_same_game_duplicate_survives_visible_detail_erasure(self) -> None:
        self.assertTrue(
            visible_event_redundant(
                topic_id="kbo_hanwha",
                prior_headline="SSG 랜더스, 한화 이글스 상대로 이틀 연속 승리",
                prior_summary="SSG 랜더스가 마운드 호투와 경기 중반 타선의 집중력을 앞세워 한화 이글스를 상대로 이틀 연속 승리를 거뒀다.",
                candidate_headline="SSG 랜더스, 한화 상대로 2연승 및 위닝시리즈 확보",
                candidate_summary="SSG 랜더스가 인천에서 한화 이글스를 6-1로 제압하며 2연승을 거두고 위닝시리즈를 확정했다.",
                prior_source_text="SSG 랜더스는 26일 인천 SSG랜더스필드에서 열린 KBO리그 경기에서 한화 이글스를 6-1로 제압해 이틀 연속 승리했다.",
                candidate_source_text="SSG 랜더스는 26일 인천 SSG랜더스필드에서 한화 이글스를 6-1로 제압하며 2연승과 위닝시리즈를 확정했다.",
            )
        )

    def test_generalized_source_backed_same_game_duplicate_is_suppressed(self) -> None:
        self.assertTrue(
            visible_event_redundant(
                topic_id="kbo_hanwha",
                prior_headline="SSG, 한화 상대로 연승",
                prior_summary="SSG가 한화를 꺾고 연승을 이어갔다.",
                candidate_headline="SSG, 한화전 위닝시리즈 확보",
                candidate_summary="SSG가 한화를 제압해 위닝시리즈를 확정했다.",
                prior_source_text="26일 인천 SSG랜더스필드에서 SSG가 한화를 5-2로 꺾고 승리했다.",
                candidate_source_text="26일 인천 SSG랜더스필드에서 SSG가 한화를 5-2로 제압해 승리했다.",
            )
        )

    def test_different_source_day_game_remains_distinct(self) -> None:
        self.assertFalse(
            visible_event_redundant(
                topic_id="kbo_hanwha",
                prior_headline="SSG, 한화 상대로 연승",
                prior_summary="SSG가 한화를 꺾고 연승을 이어갔다.",
                candidate_headline="SSG, 한화전 위닝시리즈 확보",
                candidate_summary="SSG가 한화를 제압해 위닝시리즈를 확정했다.",
                prior_source_text="25일 인천 SSG랜더스필드에서 SSG가 한화를 5-2로 꺾고 승리했다.",
                candidate_source_text="26일 인천 SSG랜더스필드에서 SSG가 한화를 5-2로 제압해 승리했다.",
            )
        )


if __name__ == "__main__":
    unittest.main()
