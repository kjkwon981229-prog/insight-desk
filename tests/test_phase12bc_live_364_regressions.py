from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.story_admission import (
    StoryAdmissionReason,
    StoryAdmissionStage,
    evaluate_story_admission,
)


NOW = datetime(2026, 8, 26, 8, 30, tzinfo=timezone.utc)


def visible(*, topic: str, headline: str, summary: str):
    return evaluate_story_admission(
        topic=topic,
        headline=headline,
        summary=summary,
        source_text=summary,
        stage=StoryAdmissionStage.VISIBLE,
        now=NOW,
    )


class Live364MissingFacilityOwnerRegressions(unittest.TestCase):
    def test_live_and_generalized_generic_facilities_require_an_owner(self) -> None:
        cases = (
            (
                "울산공장 인공지능 기반 소프트웨어중심공장 전환",
                "국내 울산공장이 인공지능 기반 소프트웨어중심공장으로 전환해 글로벌 제조혁신 거점으로 삼는다.",
            ),
            (
                "부산공장 친환경 생산 거점 전환",
                "현지 부산공장이 친환경 생산 거점으로 전환해 수출 기반을 강화한다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(summary=summary):
                decision = visible(topic="AI·테크", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_named_company_facility_plan_remains_standalone(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="현대차, 울산공장 AI 기반 SDF 전환 계획 발표",
            summary=(
                "현대차는 26일 울산공장을 AI 기반 소프트웨어중심공장으로 "
                "전환하겠다고 발표했다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live364AnonymousSectorStateRegressions(unittest.TestCase):
    def test_live_and_generalized_anonymous_sector_responses_are_not_events(self) -> None:
        cases = (
            (
                "반도체 후공정 분야 칩렛 기술 대응 구체화",
                "반도체 제조 경쟁이 후공정으로 확대됨에 따라, 산업계가 패키징 및 칩렛 기술 대응을 구체화하고 있다.",
            ),
            (
                "AI 규제 대응 전략 강화",
                "새 규제 논의가 이어지는 가운데, 관련 업계가 AI 규제 대응 전략을 강화하고 있다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(summary=summary):
                decision = visible(topic="AI·테크", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_named_current_investment_action_remains_an_event(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="삼성전자, 첨단 패키징 투자 계획 발표",
            summary="삼성전자는 26일 첨단 패키징과 칩렛 기술 투자 계획을 발표했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live364StaticProductDefinitionRegressions(unittest.TestCase):
    def test_live_and_generalized_multiword_product_definitions_are_not_events(self) -> None:
        cases = (
            (
                "다수 AI 에이전트 통합 관리 플랫폼 에이전틱 OS",
                "에이전틱 OS는 여러 AI 에이전트를 하나의 환경으로 연결해 관리하고 통제하는 기능을 갖춘 AI 플랫폼이다.",
            ),
            (
                "업무 데이터 통합 서비스 데이터 허브 프로",
                "데이터 허브 프로는 여러 업무 데이터를 연결해 관리하는 기업용 서비스이다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(summary=summary):
                decision = visible(topic="AI·테크", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_named_current_product_pilot_remains_an_event(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="남양유업, 한컴 에이전틱 OS 시범 도입 발표",
            summary="남양유업은 26일 한컴의 에이전틱 OS를 시범 도입한다고 발표했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live364PastStatementFreshnessRegressions(unittest.TestCase):
    def test_live_and_generalized_prior_month_statements_are_stale(self) -> None:
        cases = (
            (
                "신현송 한은 총재, 기준금리 결정 지표 제시",
                "신현송 한은 총재는 지난달 간담회에서 2분기 성장률과 7월 물가를 추가 기준금리 인상의 판단 기준으로 제시했다.",
            ),
            (
                "박지훈 연구원, 환율 위험 강조",
                "박지훈 연구원은 지난달 세미나에서 환율을 핵심 위험 지표로 강조했다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(summary=summary):
                decision = visible(topic="경제·투자", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.FRESHNESS, decision.reasons)

    def test_current_decision_with_prior_month_background_remains_publishable(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="한국은행, 8월 기준금리 동결 발표",
            summary=(
                "한국은행은 26일 기준금리를 동결했다고 발표했으며, 신현송 총재는 "
                "지난달 간담회에서 물가를 핵심 판단 지표로 제시했다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


if __name__ == "__main__":
    unittest.main()
