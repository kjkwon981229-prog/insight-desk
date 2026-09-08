from __future__ import annotations

import unittest

from insight_desk.core import CandidateEvent, EventFact
from insight_desk.semantic import merge_candidate_events, resolve_candidate_pair


def candidate(event_id: str, fact_id: str, article_id: str, topic: str = "sports") -> CandidateEvent:
    return CandidateEvent(event_id, topic, (fact_id,), (article_id,))


class Phase6IdentityResolutionTests(unittest.TestCase):
    def test_explicit_date_conflict_stays_separate_even_if_semantic_says_same(self) -> None:
        left = candidate("e1", "f1", "a1")
        right = candidate("e2", "f2", "a2")
        facts = {
            "f1": EventFact("f1", "한화-두산", "경기 취소", ("x1",), event_date="2026-08-12"),
            "f2": EventFact("f2", "한화-두산", "경기 취소", ("x2",), event_date="2026-08-13"),
        }

        resolution = resolve_candidate_pair(left, right, facts, semantic_same_event=True)
        self.assertFalse(resolution.decision.same_event)
        self.assertTrue(resolution.decision.deterministic_block)
        self.assertEqual(resolution.events, (left, right))

    def test_ambiguity_without_optional_semantic_judgment_is_valid_safe_separate(self) -> None:
        left = candidate("e1", "f1", "a1")
        right = candidate("e2", "f2", "a2")
        facts = {
            "f1": EventFact("f1", "KBO", "경기 재개", ("x1",), event_date="2026-08-11"),
            "f2": EventFact("f2", "KBO", "경기 재개", ("x2",), event_date="2026-08-11"),
        }

        resolution = resolve_candidate_pair(left, right, facts)
        self.assertFalse(resolution.decision.same_event)
        self.assertFalse(resolution.decision.deterministic_block)
        self.assertFalse(resolution.decision.llm_judgment_used)
        self.assertEqual(resolution.events, (left, right))

    def test_optional_positive_semantic_judgment_merges_only_after_no_hard_conflict(self) -> None:
        left = candidate("e1", "f1", "a1")
        right = candidate("e2", "f2", "a2")
        facts = {
            "f1": EventFact("f1", "KBO", "경기 재개 발표", ("x1",), event_date="2026-08-11"),
            "f2": EventFact("f2", "KBO", "경기 재개", ("x2",), event_date="2026-08-11"),
        }

        resolution = resolve_candidate_pair(left, right, facts, semantic_same_event=True)
        self.assertTrue(resolution.decision.same_event)
        self.assertTrue(resolution.decision.llm_judgment_used)
        self.assertEqual(len(resolution.events), 1)
        merged = resolution.events[0]
        self.assertEqual(merged.topic_id, "sports")
        self.assertEqual(merged.fact_ids, ("f1", "f2"))
        self.assertEqual(merged.article_ids, ("a1", "a2"))

    def test_merge_identity_is_order_invariant(self) -> None:
        left = candidate("e-z", "f-z", "a-z")
        right = candidate("e-a", "f-a", "a-a")
        facts = {
            "f-z": EventFact("f-z", "정부", "정책 발표", ("x-z",), event_date="2026-08-23"),
            "f-a": EventFact("f-a", "정부", "정책 시행", ("x-a",), event_date="2026-08-23"),
        }

        forward = resolve_candidate_pair(left, right, facts, semantic_same_event=True).events[0]
        reverse = resolve_candidate_pair(right, left, facts, semantic_same_event=True).events[0]
        self.assertEqual(forward.event_id, reverse.event_id)
        self.assertEqual(forward.fact_ids, reverse.fact_ids)
        self.assertEqual(forward.article_ids, reverse.article_ids)

    def test_negative_semantic_judgment_keeps_candidates_separate(self) -> None:
        left = candidate("e1", "f1", "a1")
        right = candidate("e2", "f2", "a2")
        facts = {
            "f1": EventFact("f1", "KBO", "경기 재개", ("x1",), event_date="2026-08-11"),
            "f2": EventFact("f2", "KBO", "경기 재개", ("x2",), event_date="2026-08-11"),
        }
        resolution = resolve_candidate_pair(left, right, facts, semantic_same_event=False)
        self.assertFalse(resolution.decision.same_event)
        self.assertTrue(resolution.decision.llm_judgment_used)
        self.assertEqual(resolution.events, (left, right))

    def test_merge_function_refuses_non_same_event_decision(self) -> None:
        left = candidate("e1", "f1", "a1")
        right = candidate("e2", "f2", "a2")
        facts = {
            "f1": EventFact("f1", "KBO", "경기 재개", ("x1",), event_date="2026-08-11"),
            "f2": EventFact("f2", "KBO", "경기 재개", ("x2",), event_date="2026-08-11"),
        }
        resolution = resolve_candidate_pair(left, right, facts)
        with self.assertRaisesRegex(ValueError, "explicit same-event"):
            merge_candidate_events(left, right, resolution.decision)

    def test_cross_topic_candidates_never_merge(self) -> None:
        left = candidate("e1", "f1", "a1", topic="economy")
        right = candidate("e2", "f2", "a2", topic="ai_tech")
        facts = {
            "f1": EventFact("f1", "정부", "정책 발표", ("x1",)),
            "f2": EventFact("f2", "정부", "정책 발표", ("x2",)),
        }
        resolution = resolve_candidate_pair(left, right, facts, semantic_same_event=True)
        self.assertFalse(resolution.decision.same_event)
        self.assertTrue(resolution.decision.deterministic_block)
        self.assertEqual(resolution.events, (left, right))


if __name__ == "__main__":
    unittest.main()
