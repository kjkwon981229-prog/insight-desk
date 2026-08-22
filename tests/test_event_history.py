from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact, TemporalState
from insight_desk.semantic import (
    EventSnapshot,
    append_event_snapshot,
    build_event_snapshot,
    derive_state_transitions,
    start_event_history,
)

BASE = datetime(2026, 8, 23, 0, 0, tzinfo=timezone.utc)


def evidence(evidence_id: str, article_id: str, text: str) -> EvidenceSpan:
    return EvidenceSpan(
        evidence_id=evidence_id,
        article_id=article_id,
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )


def candidate(event_id: str, fact_id: str, article_id: str, topic_id: str = "sports") -> CandidateEvent:
    return CandidateEvent(
        event_id=event_id,
        topic_id=topic_id,
        fact_ids=(fact_id,),
        article_ids=(article_id,),
    )


class EventHistoryTests(unittest.TestCase):
    def test_history_cannot_start_from_unresolved_identity(self) -> None:
        fact = EventFact("f1", "KBO", "경기 재개 예정", ("ev1",))
        event = candidate("e1", "f1", "a1")
        span = evidence("ev1", "a1", "KBO는 경기를 재개할 예정이라고 밝혔다.")

        with self.assertRaisesRegex(ValueError, "unresolved identity"):
            build_event_snapshot(
                canonical_event_id="canonical-kbo-1",
                event=event,
                facts={"f1": fact},
                evidence={"ev1": span},
                observed_at=BASE,
                identity_resolved=False,
                temporal_state=TemporalState.RESUMING,
            )

    def test_snapshot_preserves_exact_candidate_fact_article_and_evidence_ids(self) -> None:
        fact = EventFact("f1", "KBO", "경기 재개 예정", ("ev1",))
        event = candidate("e1", "f1", "a1")
        span = evidence("ev1", "a1", "KBO는 경기를 재개할 예정이라고 밝혔다.")

        snapshot = build_event_snapshot(
            canonical_event_id="canonical-kbo-1",
            event=event,
            facts={"f1": fact},
            evidence={"ev1": span},
            observed_at=BASE,
            identity_resolved=True,
            temporal_state=TemporalState.RESUMING,
        )
        self.assertEqual(snapshot.candidate_event_ids, ("e1",))
        self.assertEqual(snapshot.fact_ids, ("f1",))
        self.assertEqual(snapshot.article_ids, ("a1",))
        self.assertEqual(snapshot.evidence_ids, ("ev1",))
        self.assertIs(snapshot.temporal_state, TemporalState.RESUMING)

    def test_snapshot_rejects_foreign_evidence(self) -> None:
        fact = EventFact("f1", "KBO", "경기 재개", ("ev1",))
        event = candidate("e1", "f1", "a1")
        foreign = evidence("ev1", "a2", "다른 기사 본문")

        with self.assertRaisesRegex(ValueError, "outside candidate provenance"):
            build_event_snapshot(
                canonical_event_id="canonical-kbo-1",
                event=event,
                facts={"f1": fact},
                evidence={"ev1": foreign},
                observed_at=BASE,
                identity_resolved=True,
            )

    def test_history_starts_at_first_observation_without_synthetic_past(self) -> None:
        snapshot = EventSnapshot(
            snapshot_id="s1",
            canonical_event_id="canonical-1",
            topic_id="economy",
            observed_at=BASE,
            candidate_event_ids=("e1",),
            fact_ids=("f1",),
            article_ids=("a1",),
            evidence_ids=("ev1",),
            temporal_state=TemporalState.PLANNED,
        )
        history = start_event_history(snapshot)
        self.assertEqual(history.snapshots, (snapshot,))
        self.assertEqual(derive_state_transitions(history), ())

    def test_append_requires_same_canonical_identity_and_later_observation(self) -> None:
        first = EventSnapshot(
            "s1",
            "canonical-1",
            "economy",
            BASE,
            ("e1",),
            ("f1",),
            ("a1",),
            ("ev1",),
            TemporalState.PLANNED,
        )
        history = start_event_history(first)
        wrong_identity = EventSnapshot(
            "s2",
            "canonical-2",
            "economy",
            BASE + timedelta(hours=1),
            ("e2",),
            ("f2",),
            ("a2",),
            ("ev2",),
            TemporalState.ONGOING,
        )
        with self.assertRaisesRegex(ValueError, "different canonical event"):
            append_event_snapshot(history, wrong_identity, identity_resolved=True)

        same_time = EventSnapshot(
            "s3",
            "canonical-1",
            "economy",
            BASE,
            ("e3",),
            ("f3",),
            ("a3",),
            ("ev3",),
            TemporalState.ONGOING,
        )
        with self.assertRaisesRegex(ValueError, "must be later"):
            append_event_snapshot(history, same_time, identity_resolved=True)

    def test_append_refuses_unresolved_continuity_even_when_ids_match(self) -> None:
        first = EventSnapshot(
            "s1",
            "canonical-1",
            "sports",
            BASE,
            ("e1",),
            ("f1",),
            ("a1",),
            ("ev1",),
            TemporalState.RESUMING,
        )
        second = EventSnapshot(
            "s2",
            "canonical-1",
            "sports",
            BASE + timedelta(hours=1),
            ("e2",),
            ("f2",),
            ("a2",),
            ("ev2",),
            TemporalState.RESUMED,
        )
        with self.assertRaisesRegex(ValueError, "unresolved identity"):
            append_event_snapshot(start_event_history(first), second, identity_resolved=False)

    def test_transition_is_derived_only_from_two_explicit_different_states(self) -> None:
        first = EventSnapshot(
            "s1",
            "canonical-1",
            "sports",
            BASE,
            ("e1",),
            ("f1",),
            ("a1",),
            ("ev1",),
            TemporalState.RESUMING,
        )
        second = EventSnapshot(
            "s2",
            "canonical-1",
            "sports",
            BASE + timedelta(hours=1),
            ("e2",),
            ("f2",),
            ("a2",),
            ("ev2",),
            TemporalState.RESUMED,
        )
        history = append_event_snapshot(
            start_event_history(first), second, identity_resolved=True
        )
        transitions = derive_state_transitions(history)
        self.assertEqual(len(transitions), 1)
        transition = transitions[0]
        self.assertIs(transition.from_state, TemporalState.RESUMING)
        self.assertIs(transition.to_state, TemporalState.RESUMED)
        self.assertEqual(transition.evidence_ids, second.evidence_ids)
        self.assertEqual(transition.observed_at, second.observed_at)

    def test_unknown_state_is_not_interpolated_into_a_transition(self) -> None:
        first = EventSnapshot(
            "s1",
            "canonical-1",
            "sports",
            BASE,
            ("e1",),
            ("f1",),
            ("a1",),
            ("ev1",),
            TemporalState.RESUMING,
        )
        unknown = EventSnapshot(
            "s2",
            "canonical-1",
            "sports",
            BASE + timedelta(hours=1),
            ("e2",),
            ("f2",),
            ("a2",),
            ("ev2",),
            None,
        )
        completed = EventSnapshot(
            "s3",
            "canonical-1",
            "sports",
            BASE + timedelta(hours=2),
            ("e3",),
            ("f3",),
            ("a3",),
            ("ev3",),
            TemporalState.COMPLETED,
        )
        history = start_event_history(first)
        history = append_event_snapshot(history, unknown, identity_resolved=True)
        history = append_event_snapshot(history, completed, identity_resolved=True)
        self.assertEqual(derive_state_transitions(history), ())

    def test_same_state_new_evidence_does_not_manufacture_transition(self) -> None:
        first = EventSnapshot(
            "s1",
            "canonical-1",
            "economy",
            BASE,
            ("e1",),
            ("f1",),
            ("a1",),
            ("ev1",),
            TemporalState.ONGOING,
        )
        second = EventSnapshot(
            "s2",
            "canonical-1",
            "economy",
            BASE + timedelta(hours=1),
            ("e2",),
            ("f2",),
            ("a2",),
            ("ev2",),
            TemporalState.ONGOING,
        )
        history = append_event_snapshot(
            start_event_history(first), second, identity_resolved=True
        )
        self.assertEqual(derive_state_transitions(history), ())

    def test_snapshot_ids_are_stable_for_same_explicit_observation(self) -> None:
        fact = EventFact("f1", "정부", "정책 발표", ("ev1",))
        event = candidate("e1", "f1", "a1", topic_id="economy")
        span = evidence("ev1", "a1", "정부는 정책을 발표했다.")
        kwargs = dict(
            canonical_event_id="canonical-policy-1",
            event=event,
            facts={"f1": fact},
            evidence={"ev1": span},
            observed_at=BASE,
            identity_resolved=True,
            temporal_state=TemporalState.COMPLETED,
        )
        self.assertEqual(
            build_event_snapshot(**kwargs).snapshot_id,
            build_event_snapshot(**kwargs).snapshot_id,
        )


if __name__ == "__main__":
    unittest.main()
