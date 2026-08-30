from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.story_admission import (
    StoryAdmissionReason,
    StoryAdmissionStage,
    evaluate_story_admission,
)


NOW = datetime(2026, 8, 26, 9, 45, tzinfo=timezone.utc)


def visible(*, topic: str, headline: str, summary: str):
    return evaluate_story_admission(
        topic=topic,
        headline=headline,
        summary=summary,
        source_text=summary,
        stage=StoryAdmissionStage.VISIBLE,
        now=NOW,
    )


class Live372RationalePromotionRegressions(unittest.TestCase):
    def test_rationale_only_surface_is_not_the_current_event(self) -> None:
        cases = (
            (
                "삼성전자가 포터블 SSD 성능 강화",
                "삼성전자가 포터블 SSD 성능 강화에 나선 것은 생성형 AI 확산과 초고해상도 콘텐츠 증가 등으로 개인이 다루는 데이터의 용량이 빠르게 커지고 있기 때문이다.",
            ),
            (
                "에이테크가 신제품 경쟁력 강화",
                "에이테크가 신제품 경쟁력 강화에 나선 것은 시장 수요가 빠르게 늘고 있기 때문이다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(summary=summary):
                decision = visible(topic="AI·테크", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_current_product_release_can_include_rationale_as_background(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="삼성전자, 차세대 포터블 SSD P9·P7 공개",
            summary=(
                "삼성전자는 26일 게임스컴 2026에서 차세대 포터블 SSD P9과 P7을 공개했다. "
                "제품 성능을 강화한 것은 생성형 AI 콘텐츠와 고해상도 영상 수요가 늘고 있기 때문이다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live372OrphanedReporterRegressions(unittest.TestCase):
    def test_reporting_predicate_requires_a_visible_reporting_actor(self) -> None:
        cases = (
            (
                "데이터센터 증가에 따른 전력 인프라 수요 급증",
                "인공지능(AI) 데이터센터가 늘어남에 따라 전력 인프라에 대한 수요 또한 급격히 증가하고 있다고 전했다.",
            ),
            (
                "클라우드 확산에 따른 서버 수요 증가",
                "클라우드 사용량이 늘어남에 따라 서버 수요도 빠르게 증가하고 있다고 전했다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(summary=summary):
                decision = visible(topic="AI·테크", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_named_current_reporter_remains_standalone(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="LS일렉트릭, AI 데이터센터 전력 인프라 수요 증가 설명",
            summary="LS일렉트릭은 26일 AI 데이터센터 확대로 전력 인프라 수요가 빠르게 증가하고 있다고 전했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live372OngoingStrategyStateRegressions(unittest.TestCase):
    def test_generic_ongoing_business_expansion_is_not_a_current_event(self) -> None:
        cases = (
            (
                "현대차그룹, 자율주행 및 로보틱스 등 사업 다각화",
                "현대차그룹이 자율주행, 소프트웨어, 물류, 로보틱스 분야로 사업 영역을 확장하고 있다.",
            ),
            (
                "A기업, AI와 클라우드 사업 다각화",
                "A기업이 AI, 클라우드, 데이터센터 분야로 사업 영역을 확장하고 있다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(summary=summary):
                decision = visible(topic="AI·테크", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_current_named_expansion_announcement_remains_an_event(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="현대차그룹, 로보틱스 사업 확대 계획 발표",
            summary="현대차그룹은 26일 로보틱스와 자율주행 사업 확대 계획을 발표했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live372BareMetricHeadlineRegressions(unittest.TestCase):
    def test_bare_numeric_headline_cannot_drop_the_summary_metric_identity(self) -> None:
        cases = (
            (
                "1,383.0원으로 출발한 뒤 오후 12시21분께 1,388.30원까지 오르기도 했다",
                "환율은 1,383.0원으로 출발한 뒤 오후 12시21분께 1,388.30원까지 오르기도 했다.",
            ),
            (
                "1,250.0원으로 출발한 뒤 장중 1,260.0원까지 상승했다",
                "원·달러 환율은 1,250.0원으로 출발한 뒤 장중 1,260.0원까지 상승했다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(headline=headline):
                decision = visible(topic="경제·투자", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_metric_preserving_headline_remains_publishable(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="원·달러 환율, 1,383.0원 출발 후 장중 1,388.30원 상승",
            summary="원·달러 환율은 1,383.0원으로 출발한 뒤 장중 1,388.30원까지 상승했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live372OrdinaryActorLossRegressions(unittest.TestCase):
    def test_headless_ongoing_action_headline_cannot_drop_the_summary_actor(self) -> None:
        cases = (
            (
                "이제는 금리를 내리고 있습니다",
                "증시로 돈이 빠져나가는 것을 막기 위해 경쟁적으로 예금금리를 올렸던 저축은행들이 이제는 금리를 내리고 있습니다.",
            ),
            (
                "이제는 대출을 줄이고 있습니다",
                "시중은행들이 건전성 관리를 강화하면서 이제는 고위험 대출을 줄이고 있습니다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(headline=headline):
                decision = visible(topic="경제·투자", headline=headline, summary=summary)
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_actor_preserving_action_headline_remains_publishable(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="저축은행, 예금금리 인하 전환",
            summary="저축은행들이 26일 예금금리를 내리기 시작했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


if __name__ == "__main__":
    unittest.main()
