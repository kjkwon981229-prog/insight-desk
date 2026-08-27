from __future__ import annotations

import hashlib
import unittest
from datetime import datetime, timezone

from insight_desk.core import (
    ArticleEventRole,
    ArticleUnderstanding,
    CanonicalEventDraft,
    ContractError,
    EventUnderstandingRequest,
    SourceDocument,
    TopicRelation,
    UnderstandingEvidenceField,
    UnderstandingEvidenceRef,
    UnderstandingStatus,
    validate_understanding_result,
)


NOW = datetime(2026, 8, 27, 1, 0, tzinfo=timezone.utc)
BODY = "한국은행 금융통화위원회는 기준금리를 유지했다."


def source(source_id: str = "source:1", body: str = BODY) -> SourceDocument:
    return SourceDocument(
        source_id=source_id,
        candidate_ids=(f"candidate:{source_id}",),
        publisher="example",
        url=f"https://example.com/{source_id}",
        title="기준금리 결정",
        body=body,
        fetched_at=NOW,
        publication_time=NOW,
        retrieved_via="fixture",
        content_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
    )


def resolved_result(src: SourceDocument) -> ArticleUnderstanding:
    ref = UnderstandingEvidenceRef.from_source(
        src,
        field=UnderstandingEvidenceField.BODY,
        start=0,
        end=len(src.body),
    )
    draft = CanonicalEventDraft(
        draft_id="draft:1",
        topic="economy",
        actor="한국은행 금융통화위원회",
        action="기준금리를 유지했다",
        object="기준금리",
        event_type="rate_decision",
        source_ids=(src.source_id,),
        evidence_refs=(ref,),
        article_role=ArticleEventRole.PRIMARY,
        topic_relation=TopicRelation.DIRECT,
        understanding_status=UnderstandingStatus.RESOLVED,
    )
    return ArticleUnderstanding(
        understanding_id="understanding:1",
        topic="economy",
        source_ids=(src.source_id,),
        event_drafts=(draft,),
        status=UnderstandingStatus.RESOLVED,
    )


class _FakeUnderstandingEngine:
    engine_id = "fake-semantic-engine"

    def __init__(self, result: ArticleUnderstanding) -> None:
        self.result = result
        self.calls = 0

    def understand(self, request: EventUnderstandingRequest) -> ArticleUnderstanding:
        self.calls += 1
        return self.result


class EventUnderstandingPortV2Tests(unittest.TestCase):
    def test_fake_engine_result_is_mechanically_bound_to_request_sources(self) -> None:
        src = source()
        request = EventUnderstandingRequest(topic="economy", sources=(src,))
        engine = _FakeUnderstandingEngine(resolved_result(src))
        result = engine.understand(request)
        validate_understanding_result(request, result)
        self.assertEqual(engine.calls, 1)
        self.assertEqual(engine.engine_id, "fake-semantic-engine")

    def test_result_cannot_reference_source_outside_request(self) -> None:
        requested = source("source:requested")
        outsider = source("source:outsider")
        request = EventUnderstandingRequest(topic="economy", sources=(requested,))
        with self.assertRaisesRegex(ContractError, "outside the request"):
            validate_understanding_result(request, resolved_result(outsider))

    def test_result_cannot_change_request_topic(self) -> None:
        src = source()
        request = EventUnderstandingRequest(topic="ai_tech", sources=(src,))
        with self.assertRaisesRegex(ContractError, "topic differs"):
            validate_understanding_result(request, resolved_result(src))

    def test_tampered_range_digest_fails_mechanically(self) -> None:
        src = source()
        result = resolved_result(src)
        original = result.event_drafts[0]
        ref = original.evidence_refs[0]
        bad_ref = UnderstandingEvidenceRef(
            source_id=ref.source_id,
            field=ref.field,
            start=ref.start,
            end=ref.end,
            text_sha256="0" * 64,
        )
        bad_draft = CanonicalEventDraft(
            draft_id=original.draft_id,
            topic=original.topic,
            actor=original.actor,
            action=original.action,
            object=original.object,
            event_type=original.event_type,
            source_ids=original.source_ids,
            evidence_refs=(bad_ref,),
            article_role=original.article_role,
            topic_relation=original.topic_relation,
            understanding_status=original.understanding_status,
        )
        bad_result = ArticleUnderstanding(
            understanding_id=result.understanding_id,
            topic=result.topic,
            source_ids=result.source_ids,
            event_drafts=(bad_draft,),
            status=result.status,
        )
        request = EventUnderstandingRequest(topic="economy", sources=(src,))
        with self.assertRaisesRegex(ContractError, "digest differs"):
            validate_understanding_result(request, bad_result)

    def test_unresolved_result_is_valid_port_output_and_not_boolean_drop(self) -> None:
        src = source()
        request = EventUnderstandingRequest(topic="economy", sources=(src,))
        result = ArticleUnderstanding(
            understanding_id="understanding:unresolved",
            topic="economy",
            source_ids=(src.source_id,),
            event_drafts=(),
            status=UnderstandingStatus.UNRESOLVED,
            uncertainty_reasons=("insufficient_semantic_evidence",),
        )
        validate_understanding_result(request, result)
        self.assertIs(result.status, UnderstandingStatus.UNRESOLVED)


if __name__ == "__main__":
    unittest.main()
