from __future__ import annotations

import unittest
from types import SimpleNamespace

from insight_desk.core import (
    CandidateEvent,
    EventFact,
    RelevanceDecision,
    RelevanceReason,
    RelevanceVerdict,
)
from insight_desk.production_relevance_resolution_v2 import (
    BoundedRelevanceSourceExpansionLane,
)


class _Discovery:
    def __init__(self, candidates=(), *, error: Exception | None = None) -> None:
        self.candidates = tuple(candidates)
        self.error = error
        self.calls: list[tuple[str, str, int]] = []

    def search(self, query: str, *, topic_id: str, limit: int = 10):
        self.calls.append((query, topic_id, limit))
        if self.error is not None:
            raise self.error
        return self.candidates


def _event_and_facts() -> tuple[CandidateEvent, dict[str, EventFact]]:
    fact = EventFact(
        fact_id="fact-1",
        subject="Home Club",
        action="won the scheduled game",
        object="Away Club",
        evidence_ids=("evidence-1",),
    )
    event = CandidateEvent(
        event_id="event-1",
        topic_id="topic-1",
        fact_ids=(fact.fact_id,),
        article_ids=("article-1",),
    )
    return event, {fact.fact_id: fact}


def _topic():
    return SimpleNamespace(
        topic_id="topic-1",
        required_intent_terms=("Target Club",),
        intent_anchors=("League",),
    )


def _decision(verdict: RelevanceVerdict) -> RelevanceDecision:
    reasons = (
        (RelevanceReason.RESOLUTION_REQUIRED,)
        if verdict is RelevanceVerdict.DEFER
        else (RelevanceReason.CONFIGURED_LITERAL_MATCH,)
    )
    return RelevanceDecision(
        topic_id="topic-1",
        verdict=verdict,
        evidence_refs=("evidence-1",),
        reasons=reasons,
    )


class BoundedRelevanceSourceExpansionTests(unittest.TestCase):
    def test_defer_requests_bounded_additional_sources_without_mutating_verdict(self) -> None:
        event, facts = _event_and_facts()
        discovery = _Discovery(
            [
                SimpleNamespace(url="https://example.test/1"),
                SimpleNamespace(url="https://example.test/2"),
                SimpleNamespace(url="https://example.test/3"),
                SimpleNamespace(url="https://example.test/4"),
            ]
        )
        decision = _decision(RelevanceVerdict.DEFER)

        expansion = BoundedRelevanceSourceExpansionLane().expand(
            decision=decision,
            event=event,
            facts=facts,
            topic=_topic(),
            discovery=discovery,
        )

        self.assertTrue(expansion.attempted)
        self.assertEqual(expansion.reason, "relevance_defer:source_expansion")
        self.assertEqual(len(expansion.candidates), 3)
        self.assertIs(expansion.decision, decision)
        self.assertEqual(expansion.decision.verdict, RelevanceVerdict.DEFER)
        self.assertEqual(len(discovery.calls), 1)
        query, topic_id, limit = discovery.calls[0]
        self.assertEqual(topic_id, "topic-1")
        self.assertEqual(limit, 3)
        self.assertIn("Target Club", query)
        self.assertIn("Home Club", query)
        self.assertIn("Away Club", query)

    def test_non_deferred_decision_does_not_expand_sources(self) -> None:
        event, facts = _event_and_facts()
        discovery = _Discovery([SimpleNamespace(url="https://example.test/1")])
        decision = _decision(RelevanceVerdict.RELEVANT)

        expansion = BoundedRelevanceSourceExpansionLane().expand(
            decision=decision,
            event=event,
            facts=facts,
            topic=_topic(),
            discovery=discovery,
        )

        self.assertFalse(expansion.attempted)
        self.assertEqual(expansion.candidates, ())
        self.assertIs(expansion.decision, decision)
        self.assertEqual(discovery.calls, [])

    def test_discovery_failure_holds_defer_instead_of_reclassifying_it(self) -> None:
        event, facts = _event_and_facts()
        discovery = _Discovery(error=RuntimeError("offline"))
        decision = _decision(RelevanceVerdict.DEFER)

        expansion = BoundedRelevanceSourceExpansionLane().expand(
            decision=decision,
            event=event,
            facts=facts,
            topic=_topic(),
            discovery=discovery,
        )

        self.assertTrue(expansion.attempted)
        self.assertEqual(expansion.candidates, ())
        self.assertEqual(expansion.reason, "relevance_defer:resolution_discovery_unavailable")
        self.assertEqual(expansion.decision.verdict, RelevanceVerdict.DEFER)

    def test_missing_structured_fact_does_not_invent_a_resolution_query(self) -> None:
        event, _facts = _event_and_facts()
        discovery = _Discovery()
        decision = _decision(RelevanceVerdict.DEFER)

        expansion = BoundedRelevanceSourceExpansionLane().expand(
            decision=decision,
            event=event,
            facts={},
            topic=_topic(),
            discovery=discovery,
        )

        self.assertFalse(expansion.attempted)
        self.assertEqual(expansion.candidates, ())
        self.assertEqual(expansion.reason, "relevance_defer:resolution_query_unavailable")
        self.assertEqual(expansion.decision.verdict, RelevanceVerdict.DEFER)
        self.assertEqual(discovery.calls, [])

    def test_duplicate_discovery_urls_do_not_consume_the_expansion_budget_twice(self) -> None:
        event, facts = _event_and_facts()
        discovery = _Discovery(
            [
                SimpleNamespace(url="https://example.test/1"),
                SimpleNamespace(url="https://example.test/1"),
                SimpleNamespace(url="https://example.test/2"),
                SimpleNamespace(url="https://example.test/3"),
            ]
        )

        expansion = BoundedRelevanceSourceExpansionLane().expand(
            decision=_decision(RelevanceVerdict.DEFER),
            event=event,
            facts=facts,
            topic=_topic(),
            discovery=discovery,
        )

        self.assertEqual(
            tuple(candidate.url for candidate in expansion.candidates),
            (
                "https://example.test/1",
                "https://example.test/2",
                "https://example.test/3",
            ),
        )


if __name__ == "__main__":
    unittest.main()
