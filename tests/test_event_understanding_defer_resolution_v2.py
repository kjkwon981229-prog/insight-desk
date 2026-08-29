from __future__ import annotations

import unittest
from types import SimpleNamespace

from insight_desk.core import CandidateEvent, EventFact
from insight_desk.core.event_understanding_v2 import ArticleEventRole, TopicRelation, UnderstandingStatus
from insight_desk.production_event_understanding_compat_v2 import CompatibilityEventUnderstandingDecision
from insight_desk.production_event_understanding_resolution_v2 import (
    BoundedEventUnderstandingSourceExpansionLane,
)
from scripts.phase11_daily_production_core import (
    EVENT_UNDERSTANDING_RESOLUTION_ACQUISITION_LIMIT,
    _candidate_budget_allows,
)


class _Discovery:
    def __init__(self) -> None:
        self.queries: list[tuple[str, str, int]] = []

    def search(self, query: str, *, topic_id: str, limit: int):
        self.queries.append((query, topic_id, limit))
        return (
            SimpleNamespace(url="https://example.com/a"),
            SimpleNamespace(url="https://example.com/a"),
            SimpleNamespace(url="https://example.com/b"),
        )


class EventUnderstandingDeferResolutionTests(unittest.TestCase):
    def test_unresolved_understanding_can_expand_source_evidence_without_reclassifying(self) -> None:
        decision = CompatibilityEventUnderstandingDecision(
            status=UnderstandingStatus.UNRESOLVED,
            article_role=ArticleEventRole.CONTEXT,
            topic_relation=TopicRelation.UNRESOLVED,
            publishable_event=False,
            reasons=("context_dependent_actor",),
        )
        event = CandidateEvent(event_id="evt", topic_id="ai_tech", article_ids=("article",), fact_ids=("fact",))
        fact = EventFact(
            fact_id="fact",
            article_id="article",
            subject="그는",
            action="발표했다",
            object="신제품",
            evidence_ids=("evidence",),
        )
        topic = SimpleNamespace(topic_id="ai_tech", required_intent_terms=("AI",))
        article = SimpleNamespace(title="오픈AI가 신제품을 발표했다")
        discovery = _Discovery()

        expansion = BoundedEventUnderstandingSourceExpansionLane().expand(
            decision=decision,
            article=article,
            event=event,
            facts={"fact": fact},
            topic=topic,
            discovery=discovery,
        )

        self.assertTrue(expansion.attempted)
        self.assertIs(expansion.decision, decision)
        self.assertEqual([item.url for item in expansion.candidates], ["https://example.com/a", "https://example.com/b"])
        self.assertEqual(len(discovery.queries), 1)
        query, topic_id, limit = discovery.queries[0]
        self.assertIn("오픈AI가 신제품을 발표했다", query)
        self.assertIn("신제품", query)
        self.assertEqual(topic_id, "ai_tech")
        self.assertGreaterEqual(limit, 2)

    def test_resolved_understanding_does_not_expand(self) -> None:
        decision = CompatibilityEventUnderstandingDecision(
            status=UnderstandingStatus.RESOLVED,
            article_role=ArticleEventRole.PRIMARY,
            topic_relation=TopicRelation.DIRECT,
            publishable_event=True,
        )
        event = CandidateEvent(event_id="evt", topic_id="ai_tech", article_ids=("article",), fact_ids=("fact",))
        fact = EventFact(
            fact_id="fact",
            article_id="article",
            subject="OpenAI",
            action="발표했다",
            object="신제품",
            evidence_ids=("evidence",),
        )
        discovery = _Discovery()
        expansion = BoundedEventUnderstandingSourceExpansionLane().expand(
            decision=decision,
            article=SimpleNamespace(title="OpenAI 신제품 발표"),
            event=event,
            facts={"fact": fact},
            topic=SimpleNamespace(topic_id="ai_tech", required_intent_terms=("AI",)),
            discovery=discovery,
        )
        self.assertFalse(expansion.attempted)
        self.assertEqual(expansion.candidates, ())
        self.assertEqual(discovery.queries, [])

    def test_event_understanding_resolution_has_independent_acquisition_budget(self) -> None:
        resolution_url = "https://example.com/resolution"
        self.assertGreater(EVENT_UNDERSTANDING_RESOLUTION_ACQUISITION_LIMIT, 0)
        self.assertTrue(
            _candidate_budget_allows(
                candidate_url=resolution_url,
                relevance_resolution_candidate_urls=set(),
                event_understanding_resolution_candidate_urls={resolution_url},
                acquisition_attempts=8,
                max_acquisitions=8,
                relevance_resolution_acquisitions=2,
                event_understanding_resolution_acquisitions=0,
            )
        )


if __name__ == "__main__":
    unittest.main()
