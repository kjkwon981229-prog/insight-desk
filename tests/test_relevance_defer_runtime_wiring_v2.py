from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest

from insight_desk.core import CandidateEvent, EventFact
from insight_desk.production_runtime_v2 import production_v2_runtime
import scripts.phase11_daily_production as production


class RelevanceDeferRuntimeWiringTests(unittest.TestCase):
    def test_legacy_event_relevance_resolution_hook_is_not_reactivated(self) -> None:
        self.assertFalse(hasattr(production._core, "expand_deferred_event_relevance"))

        with production_v2_runtime(production._core):
            self.assertFalse(hasattr(production._core, "expand_deferred_event_relevance"))

        self.assertFalse(hasattr(production._core, "expand_deferred_event_relevance"))

    def test_daily_loop_requeues_only_bounded_expansion_candidates(self) -> None:
        source = Path("scripts/phase11_daily_production_core.py").read_text(encoding="utf-8")
        self.assertIn("expand_deferred_event_relevance(", source)
        self.assertIn("relevance_resolution_expansions", source)
        self.assertIn("queue.append(expanded_candidate)", source)
        self.assertIn("RELEVANCE_RESOLUTION_EXPANSION_LIMIT", source)

    def test_daily_loop_does_not_directly_promote_original_deferred_event(self) -> None:
        source = Path("scripts/phase11_daily_production_core.py").read_text(encoding="utf-8")
        relevance_branch = source.split("event_relevant = event_topic_relevant", 1)[1].split(
            "quality = phase6_engine.evaluate_event", 1
        )[0]
        self.assertIn("continue", relevance_branch)
        self.assertNotIn("event_relevant = True", relevance_branch)
        self.assertNotIn("status=\"published\"", relevance_branch)

    def test_post_understanding_compatibility_gate_does_not_rejudge_flat_fact(self) -> None:
        fact = EventFact(
            fact_id="fact:flat-projection",
            subject="NC",
            action="맞붙는다",
            evidence_ids=("evidence:flat-projection",),
        )
        event = CandidateEvent(
            event_id="event:flat-projection",
            topic_id="kbo_hanwha",
            fact_ids=(fact.fact_id,),
            article_ids=("article:flat-projection",),
        )
        topic = SimpleNamespace(
            topic_id="kbo_hanwha",
            intent_anchors=("KBO",),
            required_intent_terms=("한화",),
            event_terms=("경기",),
        )

        with production_v2_runtime(production._core):
            self.assertTrue(
                production._core.event_topic_relevant(
                    event=event,
                    facts={fact.fact_id: fact},
                    evidence={},
                    topic=topic,
                )
            )


if __name__ == "__main__":
    unittest.main()
