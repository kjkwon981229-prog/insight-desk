from __future__ import annotations

import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact
from insight_desk.generation import GenerationRequest
from insight_desk.phase7 import produce_phase7_entry_candidate


class FailingGenerator:
    def generate(self, request: GenerationRequest):
        del request
        raise RuntimeError("synthetic provider failure")


class Phase12JItemLocalFallbackContractTests(unittest.TestCase):
    def test_fallback_visible_contract_rejection_is_item_local(self) -> None:
        body = "일물 일물\n네오팩토리가 AI 공장 구축 사업을 15억달러에 수주했다."
        span = EvidenceSpan(
            evidence_id="ev:fallback-contract",
            article_id="article:fallback-contract",
            field=EvidenceField.BODY,
            start=0,
            end=len(body),
            text=body,
        )
        fact = EventFact(
            fact_id="fact:fallback-contract",
            subject="네오팩토리",
            action="AI 공장 구축 사업을 15억달러에 수주했다",
            object="AI 공장 구축 사업",
            evidence_ids=(span.evidence_id,),
        )
        event = CandidateEvent(
            event_id="event:fallback-contract",
            topic_id="ai_tech",
            fact_ids=(fact.fact_id,),
            article_ids=(span.article_id,),
        )
        request = GenerationRequest(
            event=event,
            facts={fact.fact_id: fact},
            evidence={span.evidence_id: span},
        )

        candidate = produce_phase7_entry_candidate(
            request,
            primary_generator=None,
            alternate_generator=FailingGenerator(),
            primary_verifier=object(),
            secondary_verifier=object(),
        )

        self.assertIsNone(candidate)

    def test_fallback_identity_preservation_rejection_is_item_local(self) -> None:
        body = "박 회장은 26일 AI 반도체 투자 확대 계획을 발표했다."
        span = EvidenceSpan(
            evidence_id="ev:fallback-identity-contract",
            article_id="article:fallback-identity-contract",
            field=EvidenceField.BODY,
            start=0,
            end=len(body),
            text=body,
        )
        fact = EventFact(
            fact_id="fact:fallback-identity-contract",
            subject="박 회장",
            action="26일 AI 반도체 투자 확대 계획을 발표했다",
            evidence_ids=(span.evidence_id,),
        )
        event = CandidateEvent(
            event_id="event:fallback-identity-contract",
            topic_id="ai_tech",
            fact_ids=(fact.fact_id,),
            article_ids=(span.article_id,),
        )
        request = GenerationRequest(
            event=event,
            facts={fact.fact_id: fact},
            evidence={span.evidence_id: span},
        )

        candidate = produce_phase7_entry_candidate(
            request,
            primary_generator=None,
            alternate_generator=FailingGenerator(),
            primary_verifier=object(),
            secondary_verifier=object(),
        )

        self.assertIsNone(candidate)


if __name__ == "__main__":
    unittest.main()
