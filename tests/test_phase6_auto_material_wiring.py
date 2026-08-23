from __future__ import annotations

import importlib.util
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact, SelectionSignals
from insight_desk.semantic import Phase6EventEngine, Phase6SelectionContext


HAS_KIWI = importlib.util.find_spec("kiwipiepy") is not None
TEXT = "네오팩토리가 AI 공장 구축 사업을 15억달러에 수주했다."


def evidence() -> EvidenceSpan:
    return EvidenceSpan(
        evidence_id="ev:auto-material",
        article_id="article:auto-material",
        field=EvidenceField.BODY,
        start=0,
        end=len(TEXT),
        text=TEXT,
    )


def event_and_fact(*, action: str = "AI 공장 구축 사업을 15억달러에 수주했다"):
    fact = EventFact(
        fact_id="fact:auto-material",
        subject="네오팩토리",
        action=action,
        object="AI 공장 구축 사업",
        evidence_ids=("ev:auto-material",),
    )
    event = CandidateEvent(
        event_id="event:auto-material",
        topic_id="ai_tech",
        fact_ids=(fact.fact_id,),
        article_ids=("article:auto-material",),
    )
    return event, fact


@unittest.skipUnless(HAS_KIWI, "semantic-local optional dependency not installed")
class Phase6AutoMaterialWiringTests(unittest.TestCase):
    def test_auto_material_true_flows_into_existing_selection_contract(self) -> None:
        event, fact = event_and_fact()
        span = evidence()
        result = Phase6EventEngine().assess_with_auto_material(
            event,
            facts={fact.fact_id: fact},
            evidence={span.evidence_id: span},
            selection_context=Phase6SelectionContext(
                topic_relevant=True,
                fresh=True,
                source_usable=True,
                identity_resolved=True,
            ),
        )
        self.assertEqual(result.material.verdict.value, "material")
        self.assertEqual(result.event_assessment.selection.verdict.value, "include")

    def test_ambiguous_material_truth_defers_without_human_input(self) -> None:
        event, fact = event_and_fact(action="수주")
        span = evidence()
        result = Phase6EventEngine().assess_with_auto_material(
            event,
            facts={fact.fact_id: fact},
            evidence={span.evidence_id: span},
            selection_context=Phase6SelectionContext(
                topic_relevant=True,
                fresh=True,
                source_usable=True,
                identity_resolved=True,
            ),
        )
        self.assertEqual(result.material.verdict.value, "defer")
        self.assertEqual(result.event_assessment.selection.verdict.value, "defer")

    def test_existing_explicit_assess_contract_is_unchanged(self) -> None:
        event, fact = event_and_fact()
        span = evidence()
        result = Phase6EventEngine().assess(
            event,
            facts={fact.fact_id: fact},
            evidence={span.evidence_id: span},
            selection_signals=SelectionSignals(
                topic_relevant=True,
                material_event=False,
                fresh=True,
                source_usable=True,
                identity_resolved=True,
            ),
        )
        self.assertEqual(result.selection.verdict.value, "exclude")
        self.assertEqual([reason.value for reason in result.selection.reasons], ["not_material"])


if __name__ == "__main__":
    unittest.main()
