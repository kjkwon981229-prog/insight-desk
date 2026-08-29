from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.core import (
    CandidateEvent,
    Certainty,
    EventFact,
    OutcomePolarity,
    TemporalState,
)
from insight_desk.core.canonical_v2 import SourceDocument
from insight_desk.production_orchestrator_v2 import canonical_event_from_candidate


class CanonicalEventInformationPreservationTests(unittest.TestCase):
    def test_canonical_event_preserves_eventfact_semantics_and_evidence_identity(self) -> None:
        source = SourceDocument(
            source_id="source-document:article-1",
            candidate_ids=("article-1",),
            publisher="Example News",
            url="https://example.com/article-1",
            title="테스트 기사",
            body="한국은행이 다음 달 회의를 재개할 가능성이 있다고 밝혔다.",
            fetched_at=datetime(2026, 8, 29, 6, 0, tzinfo=timezone.utc),
            publication_time=datetime(2026, 8, 29, 5, 0, tzinfo=timezone.utc),
            retrieved_via="test",
            content_sha256="0" * 64,
        )
        fact = EventFact(
            fact_id="fact-1",
            subject="한국은행",
            action="회의를 재개할 가능성이 있다고 밝혔다",
            object="회의",
            evidence_ids=("evidence-1", "evidence-2"),
            temporal_state=TemporalState.RESUMING,
            certainty=Certainty.POSSIBLE,
            polarity=OutcomePolarity.NEUTRAL,
            event_date="2026-09-15",
            location="서울",
            cause="정책 일정",
            participants=("금융통화위원회",),
        )
        candidate = CandidateEvent(
            event_id="event-1",
            topic_id="economy",
            fact_ids=(fact.fact_id,),
            article_ids=("article-1",),
        )

        canonical = canonical_event_from_candidate(
            candidate,
            facts={fact.fact_id: fact},
            source=source,
        )

        self.assertEqual(canonical.fact_ids, (fact.fact_id,))
        self.assertEqual(canonical.evidence_ids, fact.evidence_ids)
        self.assertIs(canonical.temporal_state, TemporalState.RESUMING)
        self.assertIs(canonical.certainty, Certainty.POSSIBLE)
        self.assertIs(canonical.polarity, OutcomePolarity.NEUTRAL)
        self.assertEqual(canonical.location, "서울")
        self.assertEqual(canonical.cause, "정책 일정")

        # Existing canonical slots must remain preserved at the same boundary.
        self.assertEqual(canonical.actor, fact.subject)
        self.assertEqual(canonical.action, fact.action)
        self.assertEqual(canonical.object, fact.object)
        self.assertEqual(canonical.event_time, fact.event_date)
        self.assertEqual(canonical.participants, fact.participants)
        self.assertEqual(canonical.source_ids, (source.source_id,))


if __name__ == "__main__":
    unittest.main()
