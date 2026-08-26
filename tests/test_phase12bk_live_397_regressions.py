from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.semantic.visible_identity import visible_event_redundant
from insight_desk.story_admission import StoryAdmissionReason, StoryAdmissionStage, evaluate_story_admission


NOW = datetime(2026, 8, 26, 13, 35, tzinfo=timezone.utc)


def visible(*, topic: str, headline: str, summary: str):
    return evaluate_story_admission(
        topic=topic,
        headline=headline,
        summary=summary,
        source_text=summary,
        stage=StoryAdmissionStage.VISIBLE,
        now=NOW,
    )


class Live397LeadingBulletChromeRegressions(unittest.TestCase):
    def test_live_leading_source_bullet_is_metadata(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="- 학부생 연구팀, AI 기반 아동 사회정서학습 개발로 학계 호평",
            summary=(
                "- 글로컬대학 사업 연계 '늘봄프로그램' 결실…대학원생 논문 3편도 우수논문상 "
                "건양대는 학부생 연구팀과 지도교수가 공동 연구한 생성형 AI 기반 맞춤형 사회정서학습 "
                "프로그램 논문이 포스터 논문상을 받았다고 26일 밝혔다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.METADATA, decision.reasons)

    def test_generalized_leading_bullet_is_metadata(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="• 대학 연구팀, AI 교육 프로그램 연구상 수상",
            summary="• 대학은 26일 AI 교육 프로그램 연구가 학술대회 연구상을 받았다고 밝혔다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.METADATA, decision.reasons)

    def test_plain_current_award_story_remains_publishable(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="건양대 연구팀, AI 사회정서학습 연구로 포스터 논문상",
            summary="건양대는 26일 생성형 AI 기반 사회정서학습 프로그램 연구가 포스터 논문상을 받았다고 밝혔다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live397ParentlessSurveyMethodRegressions(unittest.TestCase):
    def test_live_survey_method_child_detail_is_not_a_current_event(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="인텔, 로봇 도입 활발한 국가 중심 조사",
            summary=(
                "존 힐리 인텔 산업·로보틱스 사업부 부사장에 따르면, 인텔은 로봇 소비와 배치 성향이 높은 "
                "국가들을 의도적으로 선정하여 조사를 진행했다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_generalized_survey_sampling_method_is_not_a_current_event(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="인텔, AI 로봇 활용도가 높은 지역 위주 조사 대상 선정",
            summary="인텔은 AI 로봇 활용 성향이 높은 지역을 조사 대상으로 선정해 설문을 진행했다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_current_report_release_with_finding_remains_publishable(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="인텔, 26일 AI 로보틱스 준비도 조사 결과 발표",
            summary="인텔은 26일 AI 로보틱스 준비도 조사 결과를 발표하며 기업들의 로봇 도입 격차가 확인됐다고 밝혔다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live397OngoingStrategyDescriptionRegressions(unittest.TestCase):
    def test_live_ongoing_full_stack_strategy_is_not_a_discrete_event(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="엔비디아의 풀스택 컴퓨팅 체계 제시",
            summary="엔비디아는 학습 인프라와 시뮬레이션, 로봇 컴퓨팅을 아우르는 풀스택 전략을 제시하고 있다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_generalized_ongoing_ai_strategy_is_not_a_discrete_event(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="엔비디아, AI 인프라 전반을 묶는 통합 전략",
            summary="엔비디아는 AI 학습과 추론, 시뮬레이션을 아우르는 통합 컴퓨팅 전략을 추진하고 있다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_current_platform_release_remains_publishable(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="엔비디아, 26일 로봇용 AI 플랫폼 공개",
            summary="엔비디아는 26일 로봇 학습과 시뮬레이션을 지원하는 새 AI 플랫폼을 공개했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live397MarketHeadlineActorLossRegressions(unittest.TestCase):
    def test_live_market_movement_headline_cannot_drop_index_actor(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="전장 대비 0.23% 하락한 6727.25로 출발한 뒤 0.97% 오른 6808.21로 장을 마감했다",
            summary="26일 코스피지수는 전장 대비 0.23% 하락한 6727.25로 출발한 뒤 0.97% 오른 6808.21로 장을 마감했다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_generalized_market_movement_headline_cannot_drop_index_actor(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="전장 대비 0.5% 내린 2500.00으로 출발한 뒤 1.2% 오른 2540.00으로 마감했다",
            summary="26일 코스닥지수는 전장 대비 0.5% 내린 2500.00으로 출발한 뒤 1.2% 오른 2540.00으로 마감했다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_market_movement_with_index_actor_remains_publishable(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="코스피, 26일 6727.25 출발 후 6808.21로 상승 마감",
            summary="26일 코스피지수는 6727.25로 출발한 뒤 0.97% 오른 6808.21로 장을 마감했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live397SameGameDuplicateRegressions(unittest.TestCase):
    def test_live_same_game_loss_wording_is_redundant(self) -> None:
        self.assertTrue(
            visible_event_redundant(
                topic_id="kbo_hanwha",
                prior_headline="한화, SSG전 1대 6 패배",
                prior_summary="26일 인천 SSG랜더스필드에서 열린 KBO리그 경기에서 한화가 SSG에 1대 6으로 승리를 내줬다.",
                candidate_headline="한화, SSG전 패배로 3연패 수렁",
                candidate_summary="한화가 26일 인천 SSG랜더스필드에서 열린 KBO리그 SSG와의 경기에서 1-6으로 패하며 3연패를 기록했다.",
            )
        )

    def test_generalized_same_game_yielded_victory_wording_is_redundant(self) -> None:
        self.assertTrue(
            visible_event_redundant(
                topic_id="kbo_hanwha",
                prior_headline="한화, SSG에 2대 5 패배",
                prior_summary="26일 인천 SSG랜더스필드에서 한화가 SSG에 2대 5로 승리를 내줬다.",
                candidate_headline="한화, SSG전 2-5 패배",
                candidate_summary="26일 인천 SSG랜더스필드에서 한화가 SSG에 2-5로 패했다.",
            )
        )

    def test_different_day_game_remains_distinct(self) -> None:
        self.assertFalse(
            visible_event_redundant(
                topic_id="kbo_hanwha",
                prior_headline="한화, SSG전 1대 6 패배",
                prior_summary="25일 인천 SSG랜더스필드에서 한화가 SSG에 1대 6으로 패했다.",
                candidate_headline="한화, SSG전 1대 6 패배",
                candidate_summary="26일 인천 SSG랜더스필드에서 한화가 SSG에 1대 6으로 패했다.",
            )
        )


class Live397StarterPreviewStandaloneRegressions(unittest.TestCase):
    def test_live_starter_preview_requires_match_identity(self) -> None:
        decision = visible(
            topic="KBO·한화 이글스",
            headline="한화 브루스 짐머맨 선발 등판",
            summary="한화의 선발 투수로 브루스 짐머맨이 등판한다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_generalized_starter_preview_requires_match_identity(self) -> None:
        decision = visible(
            topic="KBO·한화 이글스",
            headline="한화 김민수 선발 등판",
            summary="한화의 선발 투수로 김민수가 등판한다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_starter_preview_with_date_and_opponent_remains_publishable(self) -> None:
        decision = visible(
            topic="KBO·한화 이글스",
            headline="한화 브루스 짐머맨, 27일 SSG전 선발 등판",
            summary="한화는 27일 인천 SSG랜더스필드에서 열리는 SSG전에 브루스 짐머맨을 선발 투수로 예고했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


if __name__ == "__main__":
    unittest.main()
