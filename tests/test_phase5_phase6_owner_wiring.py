from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import unittest

from insight_desk.core import (
    CandidateEvent,
    CanonicalEvidenceRef,
    CanonicalEvent,
    EvidenceField,
    EvidenceSpan,
    EventFact,
    SelectionVerdict,
    SourceDocument,
)
from insight_desk.production_orchestrator_v2 import ProductionV2Registry
from insight_desk.production_phase6_v2 import EvidenceIntegrityPhase6EventEngine
from insight_desk.production_runtime_v2 import production_v2_runtime
from insight_desk.semantic import events as semantic_events
from insight_desk.semantic.events import Phase6SelectionContext
from scripts import phase11_daily_production as production


class Phase5Phase6OwnerWiringTests(unittest.TestCase):
    def test_production_runtime_scopes_phase6_to_registry_bound_v2_owner_and_restores_it(self) -> None:
        original = production._core.Phase6EventEngine
        with production_v2_runtime(production._core) as registry:
            bound = production._core.Phase6EventEngine
            self.assertIs(bound.func, EvidenceIntegrityPhase6EventEngine)
            self.assertEqual(bound.args, (registry,))
            self.assertIs(bound().registry, registry)
        self.assertIs(production._core.Phase6EventEngine, original)

    def test_v2_phase6_does_not_call_legacy_semantic_material_classifier(self) -> None:
        article_id = "article:phase5-owner"
        evidence_id = "evidence:phase5-owner"
        fact_id = "fact:phase5-owner"
        event_id = "event:phase5-owner"
        source = "한국은행은 27일 기준금리를 결정한다."
        now = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)
        evidence = EvidenceSpan(
            evidence_id=evidence_id,
            article_id=article_id,
            field=EvidenceField.BODY,
            start=0,
            end=len(source),
            text=source,
        )
        fact = EventFact(
            fact_id=fact_id,
            subject="한국은행",
            action="27일 기준금리를 결정한다",
            evidence_ids=(evidence_id,),
        )
        event = CandidateEvent(
            event_id=event_id,
            topic_id="economy",
            fact_ids=(fact_id,),
            article_ids=(article_id,),
        )
        canonical_source = SourceDocument(
            source_id="source:phase5-owner",
            candidate_ids=(article_id,),
            publisher="fixture",
            url="https://example.com/phase5-owner",
            title="기준금리 결정",
            body=source,
            fetched_at=now,
            publication_time=now,
            retrieved_via="fixture",
            content_sha256=hashlib.sha256(source.encode()).hexdigest(),
        )
        registry = ProductionV2Registry(
            sources_by_article={article_id: canonical_source},
            events_by_id={
                event_id: CanonicalEvent(
                    event_id=event_id,
                    topic="economy",
                    actor="한국은행",
                    action="27일 기준금리를 결정한다",
                    event_type="news_event",
                    source_ids=("source:phase5-owner",),
                    evidence_refs=(
                        CanonicalEvidenceRef(
                            source_id="source:phase5-owner",
                            field="body",
                            start=0,
                            end=len(source),
                            text_sha256=hashlib.sha256(source.encode()).hexdigest(),
                        ),
                    ),
                )
            }
        )

        original = semantic_events.assess_material_event
        semantic_events.assess_material_event = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("legacy semantic material classifier must not run in V2 Phase6")
        )
        try:
            result = EvidenceIntegrityPhase6EventEngine(registry).assess_with_auto_material(
                event,
                facts={fact_id: fact},
                evidence={evidence_id: evidence},
                selection_context=Phase6SelectionContext(
                    topic_relevant=True,
                    fresh=True,
                    source_usable=True,
                    identity_resolved=True,
                ),
            )
        finally:
            semantic_events.assess_material_event = original

        self.assertTrue(result.material.selection_signal)
        self.assertIs(
            result.event_assessment.selection.verdict,
            SelectionVerdict.INCLUDE,
        )


if __name__ == "__main__":
    unittest.main()
