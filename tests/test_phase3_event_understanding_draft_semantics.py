from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.core import (
    ArticleEventRole,
    CanonicalEventDraft,
    Certainty,
    OutcomePolarity,
    SourceDocument,
    TemporalState,
    TopicRelation,
    UnderstandingEvidenceField,
    UnderstandingEvidenceRef,
    UnderstandingStatus,
)


class EventUnderstandingDraftSemanticContractTests(unittest.TestCase):
    def test_event_draft_can_preserve_extended_event_semantics(self) -> None:
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
            content_sha256="0" * 64,
        )
        evidence = UnderstandingEvidenceRef.from_source(
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
            event_type="policy_meeting",
            source_ids=(source.source_id,),
            evidence_refs=(evidence,),
            article_role=ArticleEventRole.PRIMARY,
            topic_relation=TopicRelation.DIRECT,
            understanding_status=UnderstandingStatus.RESOLVED,
            event_time="2026-09-15",
            temporal_state=TemporalState.RESUMING,
            certainty=Certainty.POSSIBLE,
            polarity=OutcomePolarity.NEUTRAL,
            location="서울",
            cause="정책 일정",
        )

        self.assertIs(draft.temporal_state, TemporalState.RESUMING)
        self.assertIs(draft.certainty, Certainty.POSSIBLE)
        self.assertIs(draft.polarity, OutcomePolarity.NEUTRAL)
        self.assertEqual(draft.location, "서울")
        self.assertEqual(draft.cause, "정책 일정")


if __name__ == "__main__":
    unittest.main()
