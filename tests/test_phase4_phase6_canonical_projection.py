from __future__ import annotations

from datetime import UTC, datetime
import hashlib
from pathlib import Path

from insight_desk.core import (
    CandidateEvent,
    CanonicalEvidenceRef,
    CanonicalEvent,
    EvidenceField,
    EvidenceSpan,
    EventFact,
    SelectionVerdict,
    SourceDocument,
    TemporalState,
)
from insight_desk.production_orchestrator_v2 import ProductionV2Registry
from insight_desk.production_phase6_v2 import EvidenceIntegrityPhase6EventEngine
from insight_desk.semantic import events as semantic_events
from insight_desk.semantic.events import Phase6SelectionContext, TemporalResolutionSource


def _fixture():
    article_id = "article:phase6-canonical"
    evidence_id = "evidence:phase6-canonical"
    fact_id = "fact:phase6-canonical"
    event_id = "event:phase6-canonical"
    text = "한국은행은 기준금리를 동결했다."
    now = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)
    span = EvidenceSpan(
        evidence_id=evidence_id,
        article_id=article_id,
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    # Legacy fact remains provenance/material-integrity input only. Its temporal state intentionally
    # differs from the CanonicalEvent so this test proves Phase6 does not re-own temporal meaning.
    fact = EventFact(
        fact_id=fact_id,
        subject="축약 주체",
        action="축약 동작",
        evidence_ids=(evidence_id,),
        temporal_state=TemporalState.PLANNED,
    )
    event = CandidateEvent(
        event_id=event_id,
        topic_id="economy",
        fact_ids=(fact_id,),
        article_ids=(article_id,),
    )
    canonical = CanonicalEvent(
        event_id=event_id,
        topic="economy",
        actor="한국은행",
        action="기준금리를 동결했다",
        object="기준금리",
        event_type="news_event",
        source_ids=("source:phase6-canonical",),
        event_time="2026-08-27",
        fact_ids=(fact_id,),
        evidence_ids=(evidence_id,),
        evidence_refs=(
            CanonicalEvidenceRef(
                source_id="source:phase6-canonical",
                field="body",
                start=0,
                end=len(text),
                text_sha256=hashlib.sha256(text.encode()).hexdigest(),
            ),
        ),
        temporal_state=TemporalState.COMPLETED,
    )
    source = SourceDocument(
        source_id="source:phase6-canonical",
        candidate_ids=(article_id,),
        publisher="fixture",
        url="https://example.com/phase6-canonical",
        title="기준금리 동결",
        body=text,
        fetched_at=now,
        publication_time=now,
        retrieved_via="fixture",
        content_sha256=hashlib.sha256(text.encode()).hexdigest(),
    )
    registry = ProductionV2Registry(
        events_by_id={event_id: canonical},
        sources_by_article={article_id: source},
    )
    return event, fact, span, registry


def test_production_phase6_projects_identity_and_temporal_from_canonical_event() -> None:
    event, fact, span, registry = _fixture()

    original_assess = semantic_events.Phase6EventEngine.assess
    semantic_events.Phase6EventEngine.assess = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("production Phase6 must not call legacy identity/temporal assessment")
    )
    try:
        result = EvidenceIntegrityPhase6EventEngine(registry).assess_with_auto_material(
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
    finally:
        semantic_events.Phase6EventEngine.assess = original_assess

    identity = result.event_assessment.identity_keys[0]
    temporal = result.event_assessment.temporal[0]
    assert identity.subject_key == "한국은행"
    assert identity.object_key == "기준금리"
    assert identity.event_date_key == "2026-08-27"
    assert temporal.state is TemporalState.COMPLETED
    # CanonicalEvent currently preserves the extractor-origin temporal state at promotion, so the
    # original provenance remains EXTRACTED even though Phase6 itself performs no extraction.
    assert temporal.source is TemporalResolutionSource.EXTRACTED
    assert result.event_assessment.selection.verdict is SelectionVerdict.INCLUDE


def test_production_phase6_source_has_no_legacy_identity_or_temporal_rejudgment() -> None:
    source = Path("insight_desk/production_phase6_v2.py").read_text(encoding="utf-8")
    assert "self.assess(" not in source
    assert "identity_key_from_fact" not in source
    assert "resolve_temporal_state" not in source
