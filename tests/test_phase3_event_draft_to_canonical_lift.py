from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import unittest

from insight_desk.core import (
    ArticleEventRole,
    CanonicalEventDraft,
    Certainty,
    ContractError,
    OutcomePolarity,
    SourceDocument,
    TemporalState,
    TopicRelation,
    UnderstandingEvidenceField,
    UnderstandingEvidenceRef,
    UnderstandingStatus,
)
from insight_desk.core.event_understanding_v2 import canonical_event_from_draft


class EventDraftToCanonicalLiftTests(unittest.TestCase):
    def _source_and_evidence(self) -> tuple[SourceDocument, UnderstandingEvidenceRef]:
        body = "한국은행은 정책 일정 때문에 서울에서 다음 달 회의를 재개할 가능성이 있다고 밝혔다."
        source = SourceDocument(
            source_id="source-1",
            candidate_ids=("candidate-1",),
            publisher="Example News",
            url="https://example.com/source-1",
            title="한국은행 회의 재개 가능성",
            body=body,
            fetched_at=datetime(2026, 8, 29, 7, 0, tzinfo=timezone.utc),
            publication_time=datetime(2026, 8, 29, 6, 0, tzinfo=timezone.utc),
            retrieved_via="test",
            content_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
        )
        evidence = UnderstandingEvidenceRef.from_source(
            source,
            field=UnderstandingEvidenceField.BODY,
            start=0,
            end=len(body),
        )
        return source, evidence

    def test_resolved_draft_lifts_without_semantic_or_evidence_loss(self) -> None:
        source, evidence = self._source_and_evidence()
        draft = CanonicalEventDraft(
            draft_id="draft-1",
            topic="economy",
            actor="한국은행",
            action="회의를 재개할 가능성이 있다고 밝혔다",
            object="회의",
            event_type="policy_meeting",
            source_ids=(source.source_id,),
            evidence_refs=(evidence,),
            article_role=ArticleEventRole.PRIMARY,
            topic_relation=TopicRelation.DIRECT,
            understanding_status=UnderstandingStatus.RESOLVED,
            event_time="2026-09-15",
            participants=("금융통화위원회",),
            temporal_state=TemporalState.RESUMING,
            certainty=Certainty.POSSIBLE,
            polarity=OutcomePolarity.NEUTRAL,
            location="서울",
            cause="정책 일정",
        )

        event = canonical_event_from_draft(
            draft,
            event_id="canonical-event-1",
            publication_time=source.publication_time,
        )

        self.assertEqual(event.event_id, "canonical-event-1")
        self.assertEqual(event.topic, draft.topic)
        self.assertEqual(event.actor, draft.actor)
        self.assertEqual(event.action, draft.action)
        self.assertEqual(event.object, draft.object)
        self.assertEqual(event.event_type, draft.event_type)
        self.assertEqual(event.source_ids, draft.source_ids)
        self.assertEqual(event.event_time, draft.event_time)
        self.assertEqual(event.participants, draft.participants)
        self.assertIs(event.temporal_state, draft.temporal_state)
        self.assertIs(event.certainty, draft.certainty)
        self.assertIs(event.polarity, draft.polarity)
        self.assertEqual(event.location, draft.location)
        self.assertEqual(event.cause, draft.cause)
        self.assertEqual(len(event.evidence_refs), 1)
        event.evidence_refs[0].validate_against(source)

    def test_unresolved_draft_cannot_be_promoted_to_canonical_event(self) -> None:
        source, evidence = self._source_and_evidence()
        draft = CanonicalEventDraft(
            draft_id="draft-unresolved",
            topic="economy",
            actor="한국은행",
            action="회의 관련 입장을 밝혔다",
            event_type="policy_meeting",
            source_ids=(source.source_id,),
            evidence_refs=(evidence,),
            article_role=ArticleEventRole.PRIMARY,
            topic_relation=TopicRelation.UNRESOLVED,
            understanding_status=UnderstandingStatus.UNRESOLVED,
            uncertainty_reasons=("event_time_unresolved",),
        )

        with self.assertRaises(ContractError):
            canonical_event_from_draft(
                draft,
                event_id="canonical-event-unresolved",
                publication_time=source.publication_time,
            )


if __name__ == "__main__":
    unittest.main()
