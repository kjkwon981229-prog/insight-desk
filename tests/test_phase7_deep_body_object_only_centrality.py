from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import unittest

from insight_desk.core import (
    CandidateEvent,
    EvidenceField,
    EvidenceSpan,
    EventFact,
    RawArticle,
    SourceProvenance,
)
from insight_desk.core.event_understanding_v2 import ArticleEventRole, UnderstandingStatus
from insight_desk.production_event_understanding_compat_v2 import (
    assess_compatibility_article_understanding,
)


NOW = datetime(2026, 8, 29, 0, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class _Token:
    surface: str
    tag: str
    start: int = 0
    end: int = 1


class _Morphology:
    def analyze(self, text: str):
        if text == "Central Bank":
            return (_Token(text, "NNP", 0, len(text)),)
        return (_Token(text, "VV", 0, max(1, len(text))),)


class DeepBodyObjectOnlyCentralityTests(unittest.TestCase):
    def test_object_only_title_overlap_cannot_promote_deep_body_background_event(self) -> None:
        body = (
            "Mortgage borrowing costs rose after lenders repriced household loans.\n"
            "Central Bank raised the policy rate to 3 percent."
        )
        article = RawArticle(
            article_id="article-object-only",
            provenance=SourceProvenance(
                source_id="web:fixture",
                source_name="fixture",
                url="https://example.com/object-only",
                retrieved_via="fixture",
                fetched_at=NOW,
                published_at=NOW,
            ),
            title="Policy rate change pushes mortgage borrowing costs higher",
            body=body,
            topic_ids=("economy",),
            query="economy",
        )
        sentence = "Central Bank raised the policy rate to 3 percent."
        start = body.index(sentence)
        span = EvidenceSpan.from_article(
            evidence_id="ev:background-rate",
            article=article,
            field=EvidenceField.BODY,
            start=start,
            end=start + len(sentence),
        )
        fact = EventFact(
            fact_id="fact:background-rate",
            subject="Central Bank",
            action="raised",
            object="policy rate",
            evidence_ids=(span.evidence_id,),
        )
        event = CandidateEvent(
            event_id="event:background-rate",
            topic_id="economy",
            fact_ids=(fact.fact_id,),
            article_ids=(article.article_id,),
        )

        decisions = assess_compatibility_article_understanding(
            article,
            events=(event,),
            facts={fact.fact_id: fact},
            evidence={span.evidence_id: span},
            morphology=_Morphology(),
            now=NOW,
        )
        decision = decisions[event.event_id]

        self.assertEqual(decision.status, UnderstandingStatus.UNRESOLVED)
        self.assertEqual(decision.article_role, ArticleEventRole.CONTEXT)
        self.assertFalse(decision.publishable_event)
        self.assertIn("article_centrality_unresolved", decision.reasons)


if __name__ == "__main__":
    unittest.main()
