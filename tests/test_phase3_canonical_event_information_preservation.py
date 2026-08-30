from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import unittest

from insight_desk.core import Certainty, OutcomePolarity, TemporalState
from insight_desk.core.canonical_v2 import SourceDocument
from insight_desk.core.event_understanding_v2 import (
    ArticleEventRole,
    CanonicalEventDraft,
    TopicRelation,
    UnderstandingEvidenceField,
    UnderstandingEvidenceRef,
    UnderstandingStatus,
    canonical_event_from_draft,
)


class CanonicalEventInformationPreservationTests(unittest.TestCase):
    def test_canonical_event_preserves_resolved_understanding_semantics_and_evidence_identity(self) -> None:
        body = "한국은행이 다음 달 회의를 재개할 가능성이 있다고 밝혔다."
        source = SourceDocument(
            source_id="source-document:article-1",
            candidate_ids=("article-1",),
            publisher="Example News",
            url="https://example.com/article-1",
            title="테스트 기사",
            body=body,
            fetched_at=datetime(2026, 8, 29, 6, 0, tzinfo=timezone.utc),
            publication_time=datetime(2026, 8, 29, 5, 0, tzinfo=timezone.utc),
            retrieved_via="test",
            content_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
        )
        evidence_ref = UnderstandingEvidenceRef.from_source(
            source,
            field=UnderstandingEvidenceField.BODY,
            start=0,
            end=len(body),
        )
        draft = CanonicalEventDraft(
            draft_id="draft-1",
            topic="economy",
            actor="한국은행",
            action="회의를 재개할 가능성이 있다고 밝혔다",
            object="회의",
            event_type="news_event",
            source_ids=(source.source_id,),
            evidence_refs=(evidence_ref,),
            article_role=ArticleEventRole.PRIMARY,
            topic_relation=TopicRelation.DIRECT,
            understanding_status=UnderstandingStatus.RESOLVED,
            temporal_state=TemporalState.RESUMING,
            certainty=Certainty.POSSIBLE,
            polarity=OutcomePolarity.NEUTRAL,
            event_time="2026-09-15",
            location="서울",
            cause="정책 일정",
            participants=("금융통화위원회",),
        )

        canonical = canonical_event_from_draft(
            draft,
            event_id="event-1",
            publication_time=source.publication_time,
        )

        self.assertEqual(len(canonical.evidence_refs), 1)
        canonical_ref = canonical.evidence_refs[0]
        self.assertEqual(canonical_ref.source_id, evidence_ref.source_id)
        self.assertEqual(canonical_ref.field, evidence_ref.field.value)
        self.assertEqual(canonical_ref.start, evidence_ref.start)
        self.assertEqual(canonical_ref.end, evidence_ref.end)
        self.assertEqual(canonical_ref.text_sha256, evidence_ref.text_sha256)
        self.assertIs(canonical.temporal_state, TemporalState.RESUMING)
        self.assertIs(canonical.certainty, Certainty.POSSIBLE)
        self.assertIs(canonical.polarity, OutcomePolarity.NEUTRAL)
        self.assertEqual(canonical.location, "서울")
        self.assertEqual(canonical.cause, "정책 일정")

        self.assertEqual(canonical.actor, draft.actor)
        self.assertEqual(canonical.action, draft.action)
        self.assertEqual(canonical.object, draft.object)
        self.assertEqual(canonical.event_time, draft.event_time)
        self.assertEqual(canonical.participants, draft.participants)
        self.assertEqual(canonical.source_ids, (source.source_id,))


if __name__ == "__main__":
    unittest.main()
