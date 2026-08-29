from __future__ import annotations

import unittest
from types import SimpleNamespace

from insight_desk.core import CandidateEvent, EventFact, RelevanceVerdict
from insight_desk.production_relevance_v2 import event_relevance_decision


class RequiredIntentEventRelevanceTests(unittest.TestCase):
    def _topic(self):
        return SimpleNamespace(
            topic_id="team_topic",
            intent_anchors=("league", "game", "win"),
            required_intent_terms=("Alpha Team", "Alpha"),
            event_terms=("game", "win", "loss"),
        )

    def test_broad_topic_anchor_cannot_replace_required_event_binding(self) -> None:
        fact = EventFact(
            fact_id="fact-other-team",
            subject="Beta Team",
            action="won the league game",
            evidence_ids=("ev-other-team",),
        )
        event = CandidateEvent(
            event_id="event-other-team",
            topic_id="team_topic",
            fact_ids=(fact.fact_id,),
            article_ids=("article-other-team",),
        )

        decision = event_relevance_decision(
            event=event,
            facts={fact.fact_id: fact},
            topic=self._topic(),
            morphology=None,
        )

        self.assertEqual(decision.verdict, RelevanceVerdict.DEFER)

    def test_required_event_binding_with_event_term_remains_relevant(self) -> None:
        fact = EventFact(
            fact_id="fact-alpha-team",
            subject="Alpha Team",
            action="won the league game",
            evidence_ids=("ev-alpha-team",),
        )
        event = CandidateEvent(
            event_id="event-alpha-team",
            topic_id="team_topic",
            fact_ids=(fact.fact_id,),
            article_ids=("article-alpha-team",),
        )

        decision = event_relevance_decision(
            event=event,
            facts={fact.fact_id: fact},
            topic=self._topic(),
            morphology=None,
        )

        self.assertEqual(decision.verdict, RelevanceVerdict.RELEVANT)


if __name__ == "__main__":
    unittest.main()
