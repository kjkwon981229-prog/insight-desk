from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact
from insight_desk.core.event_understanding_v2 import UnderstandingStatus
from insight_desk.event_predicate_v2 import PredicateCompleteness, assess_event_predicate
from insight_desk.production_event_understanding_compat_v2 import (
    assess_compatibility_event_understanding,
)
from insight_desk.semantic.material import (
    MaterialEventReason,
    MaterialEventVerdict,
    assess_material_event,
)


class _Morphology:
    def __init__(self, tags: tuple[str, ...]) -> None:
        self.tags = tags

    def analyze(self, _text: str):
        return tuple(SimpleNamespace(tag=tag) for tag in self.tags)


class EventPredicateCompletenessTests(unittest.TestCase):
    def test_attributive_verb_followed_by_nominal_head_is_not_clause_complete(self) -> None:
        morphology = _Morphology(("VV", "ETM", "NNG"))
        result = assess_event_predicate("가중되는 상황", morphology=morphology)
        self.assertIs(result.completeness, PredicateCompleteness.INCOMPLETE)
        self.assertEqual(result.reason, "attributive_nominal_description")

    def test_finite_event_clause_is_complete(self) -> None:
        morphology = _Morphology(("VV", "EP", "EF"))
        result = assess_event_predicate("기준금리를 올렸다", morphology=morphology)
        self.assertIs(result.completeness, PredicateCompleteness.COMPLETE)

    def test_progressive_finite_clause_is_complete(self) -> None:
        morphology = _Morphology(("VV", "EC", "VX", "EF"))
        result = assess_event_predicate("영향을 미치고 있다", morphology=morphology)
        self.assertIs(result.completeness, PredicateCompleteness.COMPLETE)

    def test_missing_morphology_is_unresolved_not_fabricated(self) -> None:
        result = assess_event_predicate("발표했다", morphology=None)
        self.assertIs(result.completeness, PredicateCompleteness.UNRESOLVED)

    def test_event_understanding_holds_attributive_nominal_description(self) -> None:
        event = CandidateEvent(
            event_id="evt",
            topic_id="economy",
            fact_ids=("fact",),
            article_ids=("article",),
        )
        fact = EventFact(
            fact_id="fact",
            subject="투자자",
            action="부담이 가중되는 상황",
            evidence_ids=("evidence",),
        )
        text = "투자자 부담이 가중되는 상황"
        evidence = EvidenceSpan(
            evidence_id="evidence",
            article_id="article",
            field=EvidenceField.BODY,
            start=0,
            end=len(text),
            text=text,
        )
        decision = assess_compatibility_event_understanding(
            event,
            facts={"fact": fact},
            evidence={"evidence": evidence},
            morphology=_Morphology(("VV", "ETM", "NNG")),
            now=datetime.now(timezone.utc),
        )
        self.assertIs(decision.status, UnderstandingStatus.UNRESOLVED)
        self.assertIn("predicate_unresolved", decision.reasons)

    def test_material_owner_defers_same_incomplete_predicate(self) -> None:
        event = CandidateEvent(
            event_id="evt",
            topic_id="economy",
            fact_ids=("fact",),
            article_ids=("article",),
        )
        fact = EventFact(
            fact_id="fact",
            subject="투자자",
            action="부담이 가중되는 상황",
            evidence_ids=("evidence",),
        )
        text = "투자자 부담이 가중되는 상황"
        evidence = EvidenceSpan(
            evidence_id="evidence",
            article_id="article",
            field=EvidenceField.BODY,
            start=0,
            end=len(text),
            text=text,
        )
        assessment = assess_material_event(
            event,
            facts={"fact": fact},
            evidence={"evidence": evidence},
            morphology=_Morphology(("VV", "ETM", "NNG")),
            now=datetime.now(timezone.utc),
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(assessment.reasons, (MaterialEventReason.PREDICATE_SIGNAL_MISSING,))


if __name__ == "__main__":
    unittest.main()
