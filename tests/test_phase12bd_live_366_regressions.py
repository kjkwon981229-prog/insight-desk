from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.story_admission import (
    StoryAdmissionReason,
    StoryAdmissionStage,
    evaluate_story_admission,
)


NOW = datetime(2026, 8, 26, 8, 40, tzinfo=timezone.utc)


def visible(*, topic: str, headline: str, summary: str):
    return evaluate_story_admission(
        topic=topic,
        headline=headline,
        summary=summary,
        source_text=summary,
        stage=StoryAdmissionStage.VISIBLE,
        now=NOW,
    )


class Live366ConnectiveLedHeadlineRegressions(unittest.TestCase):
    def test_live_and_generalized_connective_led_headlines_are_not_standalone(self) -> None:
        cases = (
            (
                "빨라지면서 기업의 보안 환경과 인프라를 둘러싼 위협도 급변하고 있다",
                "AI 기술 발전 속도가 빨라지면서 기업의 보안 환경과 인프라를 둘러싼 위협도 급변하고 있다.",
            ),
            (
                "확대되면서 기업의 클라우드 운영 환경도 빠르게 바뀌고 있다",
                "AI 서비스 도입이 확대되면서 기업의 클라우드 운영 환경도 빠르게 바뀌고 있다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(headline=headline):
                decision = visible(topic="AI·테크", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_named_current_report_with_connective_clause_remains_publishable(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="한국인터넷진흥원, AI 보안 위협 변화 보고서 공개",
            summary=(
                "한국인터넷진흥원은 26일 AI 기술 발전 속도가 빨라지면서 기업 보안 위협도 "
                "급변하고 있다고 분석한 보고서를 공개했다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live366AnonymousAbstractChangeRegressions(unittest.TestCase):
    def test_live_and_generalized_anonymous_abstract_changes_are_not_events(self) -> None:
        cases = (
            (
                "기업 보안 환경 위협 급변",
                "AI 기술 발전 속도가 빨라지면서 기업의 보안 환경과 인프라를 둘러싼 위협도 급변하고 있다.",
            ),
            (
                "기업 운영 방식 변화 가속",
                "클라우드 도입이 늘면서 기업의 운영 방식도 빠르게 바뀌고 있다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(summary=summary):
                decision = visible(topic="AI·테크", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_named_current_analysis_release_remains_an_event(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="한국인터넷진흥원, AI 보안 위협 변화 보고서 공개",
            summary=(
                "한국인터넷진흥원은 26일 기업 보안 환경의 위협 변화를 분석한 보고서를 공개했다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live366ReportingActorLossRegressions(unittest.TestCase):
    def test_live_and_generalized_reporting_actor_loss_is_not_standalone(self) -> None:
        cases = (
            (
                "고정형과 변동형의 금리 격차가 차주들의 선택에 영향을 미친 것으로 분석했다",
                "한국은행은 고정형과 변동형의 금리 격차가 차주들의 선택에 영향을 미친 것으로 분석했다.",
            ),
            (
                "환율 변동성이 투자 심리에 영향을 준 것으로 분석했다",
                "한국개발연구원은 환율 변동성이 투자 심리에 영향을 준 것으로 분석했다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(headline=headline):
                decision = visible(topic="경제·투자", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_named_reporting_actor_in_headline_remains_standalone(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="한국은행, 금리 격차가 차주 선택에 영향 분석",
            summary="한국은행은 고정형과 변동형의 금리 격차가 차주들의 선택에 영향을 미친 것으로 분석했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live366OrphanedContrastTimeSourceRegressions(unittest.TestCase):
    def test_live_and_generalized_orphaned_contrast_time_source_leads_are_not_standalone(self) -> None:
        cases = (
            (
                "이날 보고서에서 한은이 기준금리를 0.25%포인트 인상할 것으로 전망했다",
                "반면 노무라증권은 이날 보고서에서 한은이 기준금리를 0.25%포인트 인상할 것으로 전망했다.",
            ),
            (
                "해당 보고서에서 원화 강세가 이어질 것으로 전망했다",
                "그러나 씨티는 해당 보고서에서 원화 강세가 이어질 것으로 전망했다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(headline=headline):
                decision = visible(topic="경제·투자", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_named_dated_forecast_source_remains_standalone(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="노무라증권, 26일 보고서에서 한은 0.25%p 인상 전망",
            summary="노무라증권은 26일 보고서에서 한국은행이 기준금리를 0.25%포인트 인상할 것으로 전망했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


if __name__ == "__main__":
    unittest.main()
