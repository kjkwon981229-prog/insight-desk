from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact
from insight_desk.core.event_understanding_v2 import (
    ArticleEventRole,
    TopicRelation,
    UnderstandingStatus,
)
from insight_desk.production_event_understanding_compat_v2 import (
    assess_compatibility_event_understanding,
)


NOW = datetime(2026, 8, 29, 10, 0, tzinfo=timezone.utc)


class _VerbMorphology:
    def analyze(self, _text: str):
        return (SimpleNamespace(tag="VV"),)


def _assess(*, subject: str, action: str, evidence_text: str):
    event = CandidateEvent(
        event_id="event-1",
        topic_id="psat_recruitment",
        fact_ids=("fact-1",),
        article_ids=("article-1",),
    )
    fact = EventFact(
        fact_id="fact-1",
        subject=subject,
        action=action,
        evidence_ids=("evidence-1",),
    )
    evidence = EvidenceSpan(
        evidence_id="evidence-1",
        article_id="article-1",
        field=EvidenceField.BODY,
        start=0,
        end=len(evidence_text),
        text=evidence_text,
    )
    return assess_compatibility_event_understanding(
        event,
        facts={fact.fact_id: fact},
        evidence={evidence.evidence_id: evidence},
        morphology=_VerbMorphology(),
        now=NOW,
    )


class EventUnderstandingCompatibilityOwnerTests(unittest.TestCase):
    def test_fresh_psat_analytical_judgment_is_resolved_context_not_primary_event(self) -> None:
        decision = _assess(
            subject="취득한 성적을 여러 시험에 공통으로 활용하는 방향",
            action="수험생 부담을 경감하고 PSAT 효용성을 높일 것으로 평가된다",
            evidence_text=(
                "취득한 성적을 여러 시험에 공통으로 활용하는 방향은 수험생의 부담을 "
                "경감하고 PSAT의 효용성을 높일 것으로 평가된다."
            ),
        )
        self.assertEqual(decision.status, UnderstandingStatus.RESOLVED)
        self.assertEqual(decision.article_role, ArticleEventRole.CONTEXT)
        self.assertEqual(decision.topic_relation, TopicRelation.BACKGROUND)
        self.assertFalse(decision.publishable_event)

    def test_real_psat_schedule_announcement_is_resolved_primary_event(self) -> None:
        decision = _assess(
            subject="인사혁신처",
            action="7급 공채 PSAT 시행 일정을 발표했다",
            evidence_text="인사혁신처는 7급 공채 PSAT 시행 일정을 발표했다.",
        )
        self.assertEqual(decision.status, UnderstandingStatus.RESOLVED)
        self.assertEqual(decision.article_role, ArticleEventRole.PRIMARY)
        self.assertEqual(decision.topic_relation, TopicRelation.DIRECT)
        self.assertTrue(decision.publishable_event)

    def test_context_dependent_fact_is_unresolved_and_must_be_deferred(self) -> None:
        decision = _assess(
            subject="그는",
            action="일정을 발표했다",
            evidence_text="그는 일정을 발표했다.",
        )
        self.assertEqual(decision.status, UnderstandingStatus.UNRESOLVED)
        self.assertEqual(decision.topic_relation, TopicRelation.UNRESOLVED)
        self.assertFalse(decision.publishable_event)
        self.assertTrue(decision.reasons)

    def test_daily_core_consumes_understanding_decision_before_phase6_selection(self) -> None:
        source = Path("scripts/phase11_daily_production_core.py").read_text(encoding="utf-8")
        semantic_index = source.index("semantic_result = semantic.extract_article(")
        phase6_index = source.index("assessment = phase6.assess_with_auto_material(")
        owner_index = source.index("understanding = event_understanding_decision(", semantic_index)
        self.assertLess(owner_index, phase6_index)
        self.assertIn("UnderstandingStatus.UNRESOLVED", source[owner_index:phase6_index])
        self.assertIn("ArticleEventRole.PRIMARY", source[owner_index:phase6_index])
        self.assertIn('stage="event_understanding"', source[owner_index:phase6_index])
        self.assertIn('status="defer"', source[owner_index:phase6_index])


if __name__ == "__main__":
    unittest.main()
