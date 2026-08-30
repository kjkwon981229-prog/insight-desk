from __future__ import annotations

from pathlib import Path
import unittest

from insight_desk.core import (
    CandidateEvent,
    CanonicalEvent,
    EvidenceField,
    EvidenceSpan,
    EventFact,
    RenderMode,
)
from insight_desk.generation import GenerationRequest
import insight_desk.production_phase7_v2 as production_phase7_v2


PROPOSITION = "서울경기춤연구회가 9월 11일 전통무용 공연 명가월륜: 만월을 선보인다."


class _Registry:
    def __init__(self, event: CanonicalEvent) -> None:
        self.event = event

    def canonical_event(self, event_id: str) -> CanonicalEvent:
        if event_id != self.event.event_id:
            raise KeyError(event_id)
        return self.event


def _canonical() -> CanonicalEvent:
    return CanonicalEvent(
        event_id="event:graz",
        topic="kpop",
        actor="서울경기춤연구회",
        action="9월 11일 전통무용 공연을 선보인다",
        object="명가월륜: 만월",
        event_type="news_event",
        source_ids=("source:graz",),
        fact_ids=("fact:graz",),
        evidence_ids=("evidence:graz",),
    )


def _request() -> GenerationRequest:
    article_id = "article:graz"
    evidence_id = "evidence:graz"
    fact_id = "fact:graz"
    evidence = EvidenceSpan(
        evidence_id=evidence_id,
        article_id=article_id,
        field=EvidenceField.BODY,
        start=0,
        end=len(PROPOSITION),
        text=PROPOSITION,
    )
    fact = EventFact(
        fact_id=fact_id,
        subject="서울경기춤연구회",
        action="9월 11일 전통무용 공연을 선보인다",
        object="명가월륜: 만월",
        evidence_ids=(evidence_id,),
    )
    candidate = CandidateEvent(
        event_id="event:graz",
        topic_id="kpop",
        fact_ids=(fact_id,),
        article_ids=(article_id,),
    )
    return GenerationRequest(
        event=candidate,
        facts={fact_id: fact},
        evidence={evidence_id: evidence},
    )


class CanonicalRecoveryContractTests(unittest.TestCase):
    def test_recovery_uses_exact_primary_source_proposition(self) -> None:
        generator = production_phase7_v2.CanonicalEventRecoveryGenerator(_Registry(_canonical()))
        draft = generator.generate(_request())

        self.assertEqual(draft.headline, PROPOSITION)
        self.assertEqual(draft.summary, PROPOSITION)
        self.assertIn("명가월륜: 만월", draft.combined_text)
        self.assertEqual(draft.evidence_ids, ("evidence:graz",))

    def test_exact_proposition_passes_normal_preservation_contract(self) -> None:
        generator = production_phase7_v2.CanonicalEventRecoveryGenerator(_Registry(_canonical()))
        result = production_phase7_v2._canonical_recovery_result(
            _request(),
            generator=generator,
            prior=None,
        )
        self.assertEqual(result.render_mode, RenderMode.CANONICAL_RECOVERY)
        self.assertTrue(result.preservation.accepted)
        self.assertEqual(result.draft.summary, PROPOSITION)

    def test_render_contract_has_canonical_recovery_mode(self) -> None:
        self.assertEqual(RenderMode.CANONICAL_RECOVERY.value, "canonical_recovery")

    def test_production_phase7_uses_exact_source_proof_not_semantic_verifiers(self) -> None:
        source = Path("insight_desk/production_phase7_v2.py").read_text(encoding="utf-8")
        self.assertIn("CanonicalEventRecoveryGenerator", source)
        self.assertIn('kwargs.setdefault("recovery_generator"', source)
        self.assertIn("verify_exact_source_draft(", source)
        self.assertNotIn("verify_generated_draft(", source)


if __name__ == "__main__":
    unittest.main()
