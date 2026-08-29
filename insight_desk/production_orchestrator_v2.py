from __future__ import annotations

"""Active Canonical V2 production orchestrator facade.

The historical mechanical installer is preserved in ``production_orchestrator_compat_v2`` while
this module replaces its identity owner with the canonical-only implementation. CandidateEvent and
EventFact remain compatibility provenance containers until Event Understanding is qualified; they
are not identity semantics here.
"""

from typing import Mapping

from insight_desk.core import CandidateEvent, EventFact
from insight_desk.production_identity_core_v2 import CanonicalIdentityCore
from insight_desk.semantic.identity import (
    IdentityResolution,
    SemanticIdentityJudgment,
    merge_candidate_events,
)

from . import production_orchestrator_compat_v2 as _compat
from .production_orchestrator_compat_v2 import *  # noqa: F401,F403


class CanonicalIdentityEngine:
    """Single canonical-only runtime owner for same/different/parent-child event identity."""

    def __init__(self, registry: ProductionV2Registry) -> None:
        self.registry = registry

    def visible_redundant(self, **_kwargs) -> bool:
        # Generated headline/summary surfaces are never an event-identity authority.
        return False

    def _core(self) -> CanonicalIdentityCore:
        pair = self.registry.current_identity_pair
        if pair is None:
            raise RuntimeError("canonical identity pair is not active")
        return CanonicalIdentityCore(
            self.registry.canonical_event(pair[0]),
            self.registry.canonical_event(pair[1]),
        )

    def precheck(
        self,
        left: CandidateEvent,
        right: CandidateEvent,
        facts: Mapping[str, EventFact],
        *,
        semantic_same_event: bool | None = None,
    ):
        del facts
        self.registry.current_identity_pair = (left.event_id, right.event_id)
        self.registry.current_identity_relation = None
        return self._core().precheck(semantic_same_event=semantic_same_event)

    def judge(
        self,
        left_text: str,
        right_text: str,
        *,
        primary,
        secondary,
    ) -> SemanticIdentityJudgment:
        core = self._core()
        if core.same_structured_bok_policy_meeting:
            pair = self.registry.current_identity_pair
            assert pair is not None
            self.registry.bind_policy_parent(*pair)
            self.registry.current_identity_relation = "parent_child"
            return SemanticIdentityJudgment(
                True,
                "canonical_parent_child:bok_policy_meeting",
                0,
                0,
            )

        # Compatibility arguments are intentionally discarded. Claim verifiers and raw/generated
        # text are not event-identity authorities; unresolved pairs enter the bounded source lane.
        del left_text, right_text, primary, secondary
        self.registry.current_identity_relation = "defer"
        return SemanticIdentityJudgment(
            None,
            "canonical_identity_unresolved_requires_identity_resolution",
            0,
            0,
        )

    def resolve(
        self,
        left: CandidateEvent,
        right: CandidateEvent,
        facts: Mapping[str, EventFact],
        *,
        semantic_same_event: bool | None = None,
    ) -> IdentityResolution:
        del facts
        try:
            decision = self._core().precheck(semantic_same_event=semantic_same_event)
            if decision.same_event:
                events = (merge_candidate_events(left, right, decision),)
            else:
                events = (left, right)
            return IdentityResolution(decision=decision, events=events)
        finally:
            self.registry.current_identity_pair = None


def _evidence_integrity_assessment(*args, **kwargs):
    """Compatibility export; evidence-integrity ownership remains unchanged by identity migration."""

    return _compat._evidence_integrity_assessment(*args, **kwargs)


def install_production_orchestration(core_module):
    """Install legacy mechanical wiring with the canonical-only identity owner substituted."""

    previous = _compat.CanonicalIdentityEngine
    _compat.CanonicalIdentityEngine = CanonicalIdentityEngine
    try:
        return _compat.install_production_orchestration(core_module)
    finally:
        _compat.CanonicalIdentityEngine = previous
