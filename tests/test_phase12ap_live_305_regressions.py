from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import unittest

from insight_desk.core import CandidateEvent, EventFact, VerificationCheck
from insight_desk.semantic.events import compare_candidate_identity
from insight_desk.semantic.identity import (
    has_strong_shared_event_anchor,
    judge_same_event_mutual_entailment,
)
from insight_desk.story_admission import (
    StoryAdmissionReason,
    StoryAdmissionStage,
    evaluate_story_admission,
)


NOW = datetime(2026, 8, 25, 16, 36, tzinfo=timezone.utc)
LEFT_MARKET = (
    "25일 코스피 지수가 전 거래일 대비 45.78포인트(0.68%) 상승한 6742.74로 장을 마쳤다."
)
RIGHT_MARKET = (
    "25일 하락 출발한 국내 증시는 장 초반 4% 넘게 떨어졌으나, 개인과 기관의 매수세에 "
    "힘입어 장중 낙폭을 회복하며 상승세로 장을 마쳤다."
)


@dataclass
class FakeVerifier:
    verifier_id: str
    model_id: str
    answers: list[bool | None] = field(default_factory=list)
    calls: int = 0

    def verify(
        self,
        *,
        check_id: str,
        claim_text: str,
        evidence_text: str,
        evidence_ids: tuple[str, ...],
    ) -> VerificationCheck:
        del claim_text, evidence_text
        self.calls += 1
        answer = self.answers.pop(0) if self.answers else None
        return VerificationCheck(
            check_id=check_id,
            verifier_id=self.verifier_id,
            model_id=self.model_id,
            evidence_ids=evidence_ids,
            entailed=answer,
            error_code=None if answer is not None else "synthetic_unavailable",
            zero_cost=True,
        )


class Live305StandaloneRegressions(unittest.TestCase):
    def _visible(self, *, topic: str, headline: str, summary: str):
        return evaluate_story_admission(
            topic=topic,
            headline=headline,
            summary=summary,
            source_text=summary,
            stage=StoryAdmissionStage.VISIBLE,
            now=NOW,
        )

    def test_generic_labor_management_actor_is_not_standalone(self) -> None:
        decision = self._visible(
            topic="AI·테크",
            headline="노사, 피지컬 AI·로보틱스 대응·기술직 500명 채용",
            summary=(
                "노사가 피지컬 인공지능(AI)과 로보틱스 등 미래 기술 도입에 공동 대응하고, "
                "2028년까지 기술직 500명을 신규 채용하기로 했다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_named_labor_management_actor_remains_accepted(self) -> None:
        decision = self._visible(
            topic="AI·테크",
            headline="현대차 노사, 피지컬 AI·로보틱스 대응·기술직 500명 채용",
            summary=(
                "현대자동차 노사가 피지컬 인공지능(AI)과 로보틱스 등 미래 기술 도입에 공동 대응하고, "
                "2028년까지 기술직 500명을 신규 채용하기로 했다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)

    def test_referential_report_and_company_without_antecedent_are_not_standalone(self) -> None:
        decision = self._visible(
            topic="AI·테크",
            headline=(
                "보도는 회사가 GPU, 컴퓨팅 용량, 모델 학습, 추론, 인력에 큰 비용을 쓰고 있다고 전했다"
            ),
            summary=(
                "같은 보도는 회사가 GPU, 컴퓨팅 용량, 모델 학습, 추론, 인력에 큰 비용을 "
                "쓰고 있다고 전했다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_named_company_cost_report_remains_accepted(self) -> None:
        decision = self._visible(
            topic="AI·테크",
            headline="오픈AI, GPU·컴퓨팅 용량·모델 학습에 대규모 비용 지출",
            summary=(
                "오픈AI는 GPU와 컴퓨팅 용량, 모델 학습, 추론, 인력에 큰 비용을 쓰고 있다고 밝혔다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live305MarketIdentityRegressions(unittest.TestCase):
    def _event_pair(
        self,
        *,
        left_subject: str,
        right_subject: str,
        left_date: str = "2026-08-25",
        right_date: str = "2026-08-25",
    ):
        left_fact = EventFact(
            fact_id="fact-left",
            subject=left_subject,
            action="상승 마감",
            object="6742.74",
            event_date=left_date,
            evidence_ids=("e-left",),
        )
        right_fact = EventFact(
            fact_id="fact-right",
            subject=right_subject,
            action="상승 마감",
            object="장중 낙폭 회복",
            event_date=right_date,
            evidence_ids=("e-right",),
        )
        left = CandidateEvent(
            event_id="event-left",
            topic_id="economy",
            fact_ids=(left_fact.fact_id,),
            article_ids=("article-left",),
        )
        right = CandidateEvent(
            event_id="event-right",
            topic_id="economy",
            fact_ids=(right_fact.fact_id,),
            article_ids=("article-right",),
        )
        return left, right, {left_fact.fact_id: left_fact, right_fact.fact_id: right_fact}

    def test_broad_market_and_named_index_same_session_reach_semantic_identity(self) -> None:
        left, right, facts = self._event_pair(
            left_subject="코스피 지수",
            right_subject="국내 증시",
        )
        decision = compare_candidate_identity(
            left,
            right,
            facts,
            semantic_same_event=True,
        )
        self.assertTrue(decision.same_event, decision.reason)
        self.assertFalse(decision.deterministic_block)
        self.assertTrue(decision.llm_judgment_used)

    def test_two_different_named_indexes_are_not_collapsed(self) -> None:
        left, right, facts = self._event_pair(
            left_subject="코스피 지수",
            right_subject="코스닥 지수",
        )
        decision = compare_candidate_identity(
            left,
            right,
            facts,
            semantic_same_event=True,
        )
        self.assertFalse(decision.same_event)
        self.assertTrue(decision.deterministic_block)

    def test_market_subject_perspective_does_not_override_date_conflict(self) -> None:
        left, right, facts = self._event_pair(
            left_subject="코스피 지수",
            right_subject="국내 증시",
            left_date="2026-08-25",
            right_date="2026-08-24",
        )
        decision = compare_candidate_identity(
            left,
            right,
            facts,
            semantic_same_event=True,
        )
        self.assertFalse(decision.same_event)
        self.assertTrue(decision.deterministic_block)

    def test_live_market_close_pair_has_strong_shared_event_anchor(self) -> None:
        self.assertTrue(has_strong_shared_event_anchor(LEFT_MARKET, RIGHT_MARKET))

    def test_live_market_detail_asymmetry_still_requires_both_independent_slots(self) -> None:
        local = FakeVerifier("local-nli", "mdeberta", [False, True])
        primary = FakeVerifier("cloudflare", "failover", [True, False])
        result = judge_same_event_mutual_entailment(
            LEFT_MARKET,
            RIGHT_MARKET,
            primary=primary,
            secondary=local,
        )
        self.assertIs(result.same_event, True)
        self.assertEqual(
            result.reason,
            "strong_shared_event_anchor_with_independent_asymmetric_support",
        )
        self.assertEqual(local.calls, 2)
        self.assertEqual(primary.calls, 2)


if __name__ == "__main__":
    unittest.main()
