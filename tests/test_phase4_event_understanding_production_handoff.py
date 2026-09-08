from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import unittest

from insight_desk.core import ContractError, SourceDocument
from insight_desk.core.event_understanding_port_v2 import EventUnderstandingRequest
from insight_desk.core.event_understanding_v2 import (
    ArticleEventRole,
    ArticleUnderstanding,
    CanonicalEventDraft,
    TopicRelation,
    UnderstandingEvidenceField,
    UnderstandingEvidenceRef,
    UnderstandingStatus,
)
from insight_desk.production_event_understanding_handoff_v2 import ProductionEventUnderstandingHandoff
from insight_desk.production_orchestrator_v2 import ProductionV2Registry


NOW = datetime(2026, 8, 29, 0, 0, tzinfo=timezone.utc)


def _source() -> SourceDocument:
    body = "한국은행은 기준금리를 2.50%로 동결했다. 향후 물가와 성장 흐름을 점검할 계획이다."
    return SourceDocument(
        source_id="source:bok",
        candidate_ids=("candidate:bok",),
        publisher="example.com",
        url="https://example.com/bok",
        title="한국은행 기준금리 동결",
        body=body,
        fetched_at=NOW,
        publication_time=NOW,
        retrieved_via="fixture",
        content_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
    )


def _resolved(source: SourceDocument) -> ArticleUnderstanding:
    text = "한국은행은 기준금리를 2.50%로 동결했다."
    start = source.body.index(text)
    ref = UnderstandingEvidenceRef.from_source(
        source,
        field=UnderstandingEvidenceField.BODY,
        start=start,
        end=start + len(text),
    )
    draft = CanonicalEventDraft(
        draft_id="draft:bok-rate",
        topic="economy",
        actor="한국은행",
        action="기준금리를 동결했다",
        event_type="policy_rate_decision",
        source_ids=(source.source_id,),
        evidence_refs=(ref,),
        article_role=ArticleEventRole.PRIMARY,
        topic_relation=TopicRelation.DIRECT,
        understanding_status=UnderstandingStatus.RESOLVED,
        object="2.50%",
    )
    return ArticleUnderstanding(
        understanding_id="understanding:bok",
        topic="economy",
        source_ids=(source.source_id,),
        event_drafts=(draft,),
        status=UnderstandingStatus.RESOLVED,
    )


class EventUnderstandingProductionHandoffTests(unittest.TestCase):
    def test_resolved_understanding_is_registered_without_semantic_reinterpretation(self) -> None:
        source = _source()
        request = EventUnderstandingRequest(
            topic="economy",
            semantic_scope="monetary policy",
            sources=(source,),
        )
        result = _resolved(source)
        registry = ProductionV2Registry()
        handoff = ProductionEventUnderstandingHandoff(registry)

        events = handoff.register(
            request,
            result,
            event_ids={"draft:bok-rate": "canonical:bok-rate-20260829"},
        )

        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.event_id, "canonical:bok-rate-20260829")
        self.assertEqual(event.actor, "한국은행")
        self.assertEqual(event.action, "기준금리를 동결했다")
        self.assertEqual(event.object, "2.50%")
        self.assertEqual(event.source_ids, (source.source_id,))
        self.assertEqual(len(event.evidence_refs), 1)
        event.evidence_refs[0].validate_against(source)
        self.assertIs(registry.canonical_event(event.event_id), event)

    def test_handoff_rejects_unresolved_understanding_instead_of_silently_promoting(self) -> None:
        source = _source()
        request = EventUnderstandingRequest(
            topic="economy",
            semantic_scope="monetary policy",
            sources=(source,),
        )
        resolved = _resolved(source)
        unresolved_draft = CanonicalEventDraft(
            draft_id="draft:uncertain",
            topic="economy",
            actor="한국은행",
            action="정책 방향을 검토한다",
            event_type="policy_outlook",
            source_ids=(source.source_id,),
            evidence_refs=resolved.event_drafts[0].evidence_refs,
            article_role=ArticleEventRole.SUPPORTING,
            topic_relation=TopicRelation.DIRECT,
            understanding_status=UnderstandingStatus.UNRESOLVED,
            uncertainty_reasons=("future policy direction not resolved",),
        )
        result = ArticleUnderstanding(
            understanding_id="understanding:uncertain",
            topic="economy",
            source_ids=(source.source_id,),
            event_drafts=(unresolved_draft,),
            status=UnderstandingStatus.UNRESOLVED,
            uncertainty_reasons=("future policy direction not resolved",),
        )
        registry = ProductionV2Registry()
        handoff = ProductionEventUnderstandingHandoff(registry)

        with self.assertRaisesRegex(ContractError, "unresolved"):
            handoff.register(
                request,
                result,
                event_ids={"draft:uncertain": "canonical:must-not-exist"},
            )
        self.assertNotIn("canonical:must-not-exist", registry.events_by_id)

    def test_handoff_validates_exact_request_source_lineage_before_registration(self) -> None:
        source = _source()
        result = _resolved(source)
        mutated_body = source.body.replace("2.50%", "2.75%")
        foreign_source = SourceDocument(
            source_id=source.source_id,
            candidate_ids=source.candidate_ids,
            publisher=source.publisher,
            url=source.url,
            title=source.title,
            body=mutated_body,
            fetched_at=source.fetched_at,
            publication_time=source.publication_time,
            retrieved_via=source.retrieved_via,
            content_sha256=hashlib.sha256(mutated_body.encode("utf-8")).hexdigest(),
        )
        bad_request = EventUnderstandingRequest(
            topic="economy",
            semantic_scope="monetary policy",
            sources=(foreign_source,),
        )
        registry = ProductionV2Registry()
        handoff = ProductionEventUnderstandingHandoff(registry)

        with self.assertRaises(ContractError):
            handoff.register(
                bad_request,
                result,
                event_ids={"draft:bok-rate": "canonical:bad-lineage"},
            )
        self.assertNotIn("canonical:bad-lineage", registry.events_by_id)

    def test_handoff_has_no_provider_selection_or_provider_call_authority(self) -> None:
        source = _source()
        result = _resolved(source)
        request = EventUnderstandingRequest(
            topic="economy",
            semantic_scope="monetary policy",
            sources=(source,),
        )
        registry = ProductionV2Registry()
        handoff = ProductionEventUnderstandingHandoff(registry)

        self.assertFalse(hasattr(handoff, "provider"))
        self.assertFalse(hasattr(handoff, "understand"))
        events = handoff.register(
            request,
            result,
            event_ids={"draft:bok-rate": "canonical:bok-rate-20260829"},
        )
        self.assertEqual(len(events), 1)


if __name__ == "__main__":
    unittest.main()
