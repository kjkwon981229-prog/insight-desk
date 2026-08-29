from __future__ import annotations

from pathlib import Path
import unittest

from insight_desk.production_runtime_v2 import production_v2_runtime
import scripts.phase11_daily_production as production


class RelevanceDeferRuntimeWiringTests(unittest.TestCase):
    def test_resolution_hook_exists_only_inside_v2_runtime_scope(self) -> None:
        self.assertFalse(hasattr(production._core, "expand_deferred_event_relevance"))

        with production_v2_runtime(production._core):
            self.assertTrue(hasattr(production._core, "expand_deferred_event_relevance"))
            self.assertTrue(callable(production._core.expand_deferred_event_relevance))

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


if __name__ == "__main__":
    unittest.main()
