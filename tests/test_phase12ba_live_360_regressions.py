from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact
from insight_desk.generation import (
    GeneratedDraft,
    GenerationContractError,
    GenerationRequest,
    validate_story_admission,
)
from insight_desk.story_admission import (
    StoryAdmissionReason,
    StoryAdmissionStage,
    evaluate_story_admission,
)


NOW = datetime(2026, 8, 26, 5, 20, tzinfo=timezone.utc)


def visible(*, topic: str, headline: str, summary: str):
    return evaluate_story_admission(
        topic=topic,
        headline=headline,
        summary=summary,
        source_text=summary,
        stage=StoryAdmissionStage.VISIBLE,
        now=NOW,
    )


def generation_case(
    *,
    evidence_text: str,
    subject: str,
    action: str,
    headline: str,
    summary: str,
) -> tuple[GenerationRequest, GeneratedDraft]:
    span = EvidenceSpan(
        evidence_id="ev:live360",
        article_id="article:live360",
        field=EvidenceField.BODY,
        start=0,
        end=len(evidence_text),
        text=evidence_text,
    )
    fact = EventFact(
        fact_id="fact:live360",
        subject=subject,
        action=action,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:live360",
        topic_id="ai_tech",
        fact_ids=(fact.fact_id,),
        article_ids=(span.article_id,),
    )
    request = GenerationRequest(
        event=event,
        facts={fact.fact_id: fact},
        evidence={span.evidence_id: span},
    )
    draft = GeneratedDraft(
        event_id=event.event_id,
        headline=headline,
        summary=summary,
        evidence_ids=(span.evidence_id,),
    )
    return request, draft


class Live360AnonymousAbstractStateRegressions(unittest.TestCase):
    def test_live_and_paraphrased_anonymous_generalizations_are_not_events(self) -> None:
        cases = (
            (
                "전력 확보 능력이 국가 AI 경쟁력을 좌우할 가능성이 커지고 있다",
                "그만큼 GPU와 이를 돌릴 데이터센터, 전력 확보 능력이 국가 AI "
                "경쟁력을 좌우할 가능성이 커지고 있다.",
            ),
            (
                "팬 활동은 음원 소비에만 머물지 않는다",
                "K-pop 팬덤의 활동은 더 이상 앨범 구매나 음원 스트리밍에만 "
                "머물지 않는다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(headline=headline):
                decision = visible(
                    topic="AI·테크" if "전력" in headline else "엔터·음악·K-POP",
                    headline=headline,
                    summary=summary,
                )
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_named_current_policy_forum_action_remains_an_event(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="조영임 교수, AI 데이터센터 세제·전력 지원 확대 촉구",
            summary=(
                "조영임 가천대 교수는 26일 국회 토론회에서 AI 데이터센터에 대한 "
                "세제·전력 지원을 확대해야 한다고 촉구했다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live360HeadlineActorPreservationRegressions(unittest.TestCase):
    def test_live_and_generalized_headlines_cannot_drop_the_summary_actor(self) -> None:
        cases = (
            (
                "경제·투자",
                "26일 발표한 '금융기관 가중평균 금리' 통계에 따르면 가계대출 "
                "금리는 연 4.64%로 올랐다",
                "한국은행이 26일 발표한 '금융기관 가중평균 금리' 통계에 따르면 "
                "가계대출 금리는 연 4.64%로 올랐다.",
            ),
            (
                "경제·투자",
                "26일 공개한 조사에서 시민 만족도 80% 기록",
                "서울시가 26일 공개한 조사에서 시민 만족도는 80%를 기록했다.",
            ),
            (
                "KBO·한화 이글스",
                "NC(구창모)-LG(임찬규), 삼성(최원태)-키움(박준현), "
                "한화(류현진)-SSG(최민준)가 나선다",
                "선발 투수는 NC(구창모)-LG(임찬규), 삼성(최원태)-키움(박준현), "
                "한화(류현진)-SSG(최민준)가 나선다.",
            ),
        )
        for topic, headline, summary in cases:
            with self.subTest(headline=headline):
                decision = visible(
                    topic=topic,
                    headline=headline,
                    summary=summary,
                )
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_summary_actor_preserved_in_headline_remains_standalone(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="한국은행, 7월 가계대출 금리 연 4.64%로 상승",
            summary=(
                "한국은행이 26일 발표한 금융기관 가중평균금리에 따르면 7월 "
                "가계대출 금리는 연 4.64%로 상승했다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)

        role_decision = visible(
            topic="KBO·한화 이글스",
            headline="한화 류현진-SSG 최민준 선발 맞대결",
            summary="선발 투수는 한화 류현진과 SSG 최민준으로 예고됐다.",
        )
        self.assertTrue(role_decision.accepted, role_decision.reasons)


class Live360AnalyticalReferentRegressions(unittest.TestCase):
    def test_live_model_and_data_references_require_visible_antecedents(self) -> None:
        cases = (
            (
                "한국은행 25bp 연속 금리 인상 가능성 급등",
                "한국은행의 25bp 연속 금리 인상 가능성이 3분기 74%, 4분기 "
                "93%로 크게 상승했다고 해당 모델이 밝혔다.",
            ),
            (
                "김희재 남자가수 부문 115만 표 돌파",
                "김희재가 남자가수 부문에서 115만3290표를 획득하며 이번 "
                "자료에서 개별 부문 100만 표를 넘긴 세 명 중 한 명으로 기록됐다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(headline=headline):
                decision = visible(
                    topic="경제·투자" if "한국은행" in headline else "엔터·음악·K-POP",
                    headline=headline,
                    summary=summary,
                )
                self.assertFalse(decision.accepted)
                self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_named_analytical_object_resolves_later_reference(self) -> None:
        decision = visible(
            topic="경제·투자",
            headline="노무라증권, 8월 기준금리 인상 확률 최고 수준 평가",
            summary=(
                "노무라증권은 26일 자체 금리 인상 확률 모델을 공개했다. 해당 "
                "모델은 8월 기준금리 인상 확률이 최고 수준이라고 분석했다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live360BackgroundFreshnessRegressions(unittest.TestCase):
    def test_old_month_background_and_month_day_event_are_stale(self) -> None:
        request, draft = generation_case(
            evidence_text=(
                "신동빈 롯데그룹 회장은 지난 6월 CEO AI 아카데미에 참석해 그룹의 "
                "AX 전략을 점검하고 전 임직원의 AI 역량을 지원하겠다고 밝혔다."
            ),
            subject="신동빈 롯데그룹 회장",
            action="전 임직원의 AI 역량을 지원하겠다고 밝혔다",
            headline="신동빈 롯데 회장, 전 임직원 AI 역량 강화 강조",
            summary="신동빈 롯데그룹 회장은 전 임직원의 AI 역량 강화를 지원하겠다고 밝혔다.",
        )
        with self.assertRaisesRegex(GenerationContractError, "FRESHNESS"):
            validate_story_admission(request, draft)

        decision = visible(
            topic="경제·투자",
            headline="한국은행, 기준금리 0.25%p 인상",
            summary=(
                "한국은행 금융통화위원회는 7월 16일 기준금리를 연 2.50%에서 "
                "2.75%로 0.25%포인트 인상했다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.FRESHNESS, decision.reasons)

    def test_current_event_with_past_background_remains_publishable(self) -> None:
        evidence_text = (
            "롯데백화점은 26일 브랜드 AI를 도입해 MD 업무 생산성을 두 배로 높였다고 "
            "발표했다. 신동빈 롯데그룹 회장은 지난 6월 그룹 AX 전략을 강조했다."
        )
        request, draft = generation_case(
            evidence_text=evidence_text,
            subject="롯데백화점",
            action="브랜드 AI를 도입했다고 발표했다",
            headline="롯데백화점, 4000개 브랜드 분석 AI 도입",
            summary="롯데백화점은 26일 브랜드 분석 AI를 도입했다고 발표했다.",
        )
        validate_story_admission(request, draft)


if __name__ == "__main__":
    unittest.main()
