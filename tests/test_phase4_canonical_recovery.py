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


class _Registry:
    def __init__(self, event: CanonicalEvent) -> None:
        self.event = event

    def canonical_event(self, event_id: str) -> CanonicalEvent:
        if event_id != self.event.event_id:
            raise KeyError(event_id)
        return self.event


def _request() -> GenerationRequest:
    article_id = "article:graz"
    evidence_id = "evidence:graz"
    fact_id = "fact:graz"
    body = (
        "서울경기춤연구회가 9월 11일 전통무용 공연 명가월륜: 만월을 선보인다. "
        "축제는 한국 전통무용을 비롯해 영화, K팝, 한식, 한복, 전통놀이 등 "
        "한국문화의 다양한 면모를 현지 관객에게 소개한다. "
        "작품의 예술적 성과와 참여 예술가들의 이력에 대한 긴 배경 설명이 이어진다."
    )
    evidence = EvidenceSpan(
        evidence_id=evidence_id,
        article_id=article_id,
        field=EvidenceField.BODY,
        start=0,
        end=len(body),
        text=body,
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
    def test_recovery_projects_canonical_event_fields_not_article_prose(self) -> None:
        canonical = CanonicalEvent(
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
        generator = production_phase7_v2.CanonicalEventRecoveryGenerator(_Registry(canonical))
        draft = generator.generate(_request())

        self.assertEqual(draft.headline, "서울경기춤연구회, 9월 11일 전통무용 공연을 선보인다")
        self.assertEqual(
            draft.summary,
            "주체: 서울경기춤연구회 · 사건: 9월 11일 전통무용 공연을 선보인다 · 대상: 명가월륜: 만월",
        )
        self.assertNotIn("축제는 한국 전통무용", draft.combined_text)
        self.assertNotIn("참여 예술가들의 이력", draft.combined_text)
        self.assertEqual(draft.evidence_ids, ("evidence:graz",))

    def test_render_contract_has_canonical_recovery_mode(self) -> None:
        self.assertEqual(RenderMode.CANONICAL_RECOVERY.value, "canonical_recovery")

    def test_production_phase7_injects_recovery_owner_instead_of_raw_source_fallback(self) -> None:
        source = Path("insight_desk/production_phase7_v2.py").read_text(encoding="utf-8")
        self.assertIn("CanonicalEventRecoveryGenerator", source)
        self.assertIn('kwargs.setdefault("recovery_generator"', source)


if __name__ == "__main__":
    unittest.main()
