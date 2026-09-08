from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.story_admission import (
    StoryAdmissionReason,
    StoryAdmissionStage,
    evaluate_story_admission,
)


NOW = datetime(2026, 8, 26, 4, 0, tzinfo=timezone.utc)


def visible(*, topic: str, headline: str, summary: str):
    return evaluate_story_admission(
        topic=topic,
        headline=headline,
        summary=summary,
        source_text=summary,
        stage=StoryAdmissionStage.VISIBLE,
        now=NOW,
    )


class Live340UnattributedMarketInterpretationRegressions(unittest.TestCase):
    def test_live_generic_market_cognition_is_not_a_material_event(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="엔비디아 실적이 AI 투자 사이클 시험대",
            summary=(
                "시장은 이번 엔비디아 실적을 개별 기업의 성적표를 넘어 "
                "AI 투자 사이클의 지속 가능성을 가늠할 시험대로 보고 있다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_named_analyst_evaluation_remains_attributed(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="엔비디아 실적, AI 투자 사이클 시험대",
            summary=(
                "이경민 대신증권 연구원은 26일 엔비디아 실적이 "
                "AI 투자 사이클의 지속 가능성을 가늠할 시험대라고 평가했다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live340BareRoleActorRegressions(unittest.TestCase):
    def test_live_bare_responsible_role_is_not_standalone(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="금리 동결은 긴축 종료가 아니다",
            summary=(
                "책임자는 금리 동결이 긴축 종료가 아니며, 이전 금리 인상의 효과와 "
                "연준의 기대치 변화, 대외 환경을 평가해 점진적 금리 인상 신호로 "
                "해석돼야 한다고 말했다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_named_institutional_role_remains_standalone(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="한국은행, 금리 동결 의미 설명",
            summary=(
                "한국은행 책임자는 26일 금리 동결이 긴축 종료를 뜻하지 않는다고 말했다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live340AbstractEmergenceRegressions(unittest.TestCase):
    def test_live_actorless_abstract_recruitment_model_rollup_is_not_an_event(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="생성형 AI 활용 채용 모델 등장",
            summary=(
                "프로그래머 채용에서 전통적인 ‘코딩테스트’를 폐지하고, "
                "생성형 AI 도구 활용을 검증하는 새로운 채용 모델이 등장해 "
                "취업 시장의 이목을 모으고 있다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_named_company_concrete_recruitment_change_remains_an_event(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="넥슨컴퍼니, 코딩테스트 폐지하고 AI 역량평가 도입",
            summary=(
                "넥슨컴퍼니는 26일 신입 개발자 채용에서 코딩테스트를 폐지하고 "
                "생성형 AI 활용 역량평가를 도입한다고 밝혔다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


if __name__ == "__main__":
    unittest.main()
