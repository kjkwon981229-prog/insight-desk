from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from insight_desk.core import CandidateEvent, EvidenceSpan, EventFact, TemporalState


def _require_text(name: str, value: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{name} must be non-empty")


def _require_aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _require_unique_nonempty(name: str, values: tuple[str, ...]) -> None:
    if not values:
        raise ValueError(f"{name} must contain at least one id")
    if any(not value or not value.strip() for value in values):
        raise ValueError(f"{name} must contain only non-empty ids")
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must not contain duplicate ids")


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}-{digest}"


@dataclass(frozen=True, slots=True)
class EventSnapshot:
    """One observed, evidence-bound state of an already identity-resolved event.

    A snapshot is not a reconstructed past state. Every fact/article/evidence id must come from the
    candidate event observed at this point in time. `canonical_event_id` is supplied by the explicit
    identity layer; this module never creates continuity from similarity alone.
    """

    snapshot_id: str
    canonical_event_id: str
    topic_id: str
    observed_at: datetime
    candidate_event_ids: tuple[str, ...]
    fact_ids: tuple[str, ...]
    article_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    temporal_state: TemporalState | None = None

    def __post_init__(self) -> None:
        _require_text("snapshot_id", self.snapshot_id)
        _require_text("canonical_event_id", self.canonical_event_id)
        _require_text("topic_id", self.topic_id)
        _require_aware("observed_at", self.observed_at)
        _require_unique_nonempty("candidate_event_ids", self.candidate_event_ids)
        _require_unique_nonempty("fact_ids", self.fact_ids)
        _require_unique_nonempty("article_ids", self.article_ids)
        _require_unique_nonempty("evidence_ids", self.evidence_ids)


@dataclass(frozen=True, slots=True)
class StateTransition:
    """A deterministic change between two adjacent, explicitly observed temporal states."""

    transition_id: str
    canonical_event_id: str
    from_snapshot_id: str
    to_snapshot_id: str
    from_state: TemporalState
    to_state: TemporalState
    observed_at: datetime
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_text("transition_id", self.transition_id)
        _require_text("canonical_event_id", self.canonical_event_id)
        _require_text("from_snapshot_id", self.from_snapshot_id)
        _require_text("to_snapshot_id", self.to_snapshot_id)
        if self.from_snapshot_id == self.to_snapshot_id:
            raise ValueError("state transition requires two different snapshots")
        if self.from_state is self.to_state:
            raise ValueError("state transition requires an actual state change")
        _require_aware("observed_at", self.observed_at)
        _require_unique_nonempty("evidence_ids", self.evidence_ids)


@dataclass(frozen=True, slots=True)
class EventHistory:
    """Persistent observations for one explicit canonical event identity.

    The contract intentionally does not impose a guessed lifecycle state machine. It records only
    chronological observations and lets `derive_state_transitions` emit changes that are actually
    present. Unknown temporal states stay unknown instead of being interpolated.
    """

    history_id: str
    canonical_event_id: str
    topic_id: str
    snapshots: tuple[EventSnapshot, ...]

    def __post_init__(self) -> None:
        _require_text("history_id", self.history_id)
        _require_text("canonical_event_id", self.canonical_event_id)
        _require_text("topic_id", self.topic_id)
        if not self.snapshots:
            raise ValueError("event history must contain at least one snapshot")
        snapshot_ids = tuple(snapshot.snapshot_id for snapshot in self.snapshots)
        _require_unique_nonempty("snapshot ids", snapshot_ids)

        previous_at: datetime | None = None
        for snapshot in self.snapshots:
            if snapshot.canonical_event_id != self.canonical_event_id:
                raise ValueError("history cannot mix canonical event identities")
            if snapshot.topic_id != self.topic_id:
                raise ValueError("history cannot mix topics")
            if previous_at is not None and snapshot.observed_at <= previous_at:
                raise ValueError("history snapshots must be strictly chronological")
            previous_at = snapshot.observed_at


def build_event_snapshot(
    *,
    canonical_event_id: str,
    event: CandidateEvent,
    facts: Mapping[str, EventFact],
    evidence: Mapping[str, EvidenceSpan],
    observed_at: datetime,
    identity_resolved: bool,
    temporal_state: TemporalState | None = None,
) -> EventSnapshot:
    """Create one history observation only after the caller proves identity is resolved."""

    _require_text("canonical_event_id", canonical_event_id)
    _require_aware("observed_at", observed_at)
    if not identity_resolved:
        raise ValueError("unresolved identity cannot create event history")

    event_facts: list[EventFact] = []
    evidence_ids: list[str] = []
    for fact_id in event.fact_ids:
        try:
            fact = facts[fact_id]
        except KeyError as exc:
            raise ValueError(f"event references missing fact: {fact_id}") from exc
        if fact.fact_id != fact_id:
            raise ValueError(f"fact index key mismatch: {fact_id}")
        event_facts.append(fact)
        for evidence_id in fact.evidence_ids:
            if evidence_id not in evidence_ids:
                evidence_ids.append(evidence_id)
            try:
                span = evidence[evidence_id]
            except KeyError as exc:
                raise ValueError(f"fact references missing evidence: {evidence_id}") from exc
            if span.evidence_id != evidence_id:
                raise ValueError(f"evidence index key mismatch: {evidence_id}")
            if span.article_id not in event.article_ids:
                raise ValueError(
                    f"event history evidence is outside candidate provenance: {evidence_id}"
                )

    if not event_facts:
        raise ValueError("candidate event must contain at least one fact")
    snapshot_id = _stable_id(
        "snapshot",
        canonical_event_id,
        event.event_id,
        observed_at.isoformat(),
        *(fact.fact_id for fact in event_facts),
    )
    return EventSnapshot(
        snapshot_id=snapshot_id,
        canonical_event_id=canonical_event_id,
        topic_id=event.topic_id,
        observed_at=observed_at,
        candidate_event_ids=(event.event_id,),
        fact_ids=tuple(fact.fact_id for fact in event_facts),
        article_ids=event.article_ids,
        evidence_ids=tuple(evidence_ids),
        temporal_state=temporal_state,
    )


def start_event_history(snapshot: EventSnapshot) -> EventHistory:
    """Start history from a real observation; no synthetic pre-history is manufactured."""

    history_id = _stable_id("history", snapshot.canonical_event_id, snapshot.topic_id)
    return EventHistory(
        history_id=history_id,
        canonical_event_id=snapshot.canonical_event_id,
        topic_id=snapshot.topic_id,
        snapshots=(snapshot,),
    )


def append_event_snapshot(
    history: EventHistory,
    snapshot: EventSnapshot,
    *,
    identity_resolved: bool,
) -> EventHistory:
    """Append a later observation without inferring continuity from text similarity."""

    if not identity_resolved:
        raise ValueError("unresolved identity cannot extend event history")
    if snapshot.canonical_event_id != history.canonical_event_id:
        raise ValueError("snapshot belongs to a different canonical event")
    if snapshot.topic_id != history.topic_id:
        raise ValueError("snapshot belongs to a different topic")
    if snapshot.observed_at <= history.snapshots[-1].observed_at:
        raise ValueError("new snapshot must be later than the current history tail")
    return EventHistory(
        history_id=history.history_id,
        canonical_event_id=history.canonical_event_id,
        topic_id=history.topic_id,
        snapshots=history.snapshots + (snapshot,),
    )


def derive_state_transitions(history: EventHistory) -> tuple[StateTransition, ...]:
    """Derive only explicit adjacent lifecycle changes; never bridge unknown states."""

    transitions: list[StateTransition] = []
    for previous, current in zip(history.snapshots, history.snapshots[1:]):
        if previous.temporal_state is None or current.temporal_state is None:
            continue
        if previous.temporal_state is current.temporal_state:
            continue
        transitions.append(
            StateTransition(
                transition_id=_stable_id(
                    "transition",
                    history.canonical_event_id,
                    previous.snapshot_id,
                    current.snapshot_id,
                    previous.temporal_state.value,
                    current.temporal_state.value,
                ),
                canonical_event_id=history.canonical_event_id,
                from_snapshot_id=previous.snapshot_id,
                to_snapshot_id=current.snapshot_id,
                from_state=previous.temporal_state,
                to_state=current.temporal_state,
                observed_at=current.observed_at,
                evidence_ids=current.evidence_ids,
            )
        )
    return tuple(transitions)
