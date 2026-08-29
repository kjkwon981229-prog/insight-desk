from __future__ import annotations

"""Scope Phase 4 generation authority changes to the actual production call.

Historical generation utilities keep their exact-source fallback for replay compatibility. Production
publication does not: any extractive fallback is replaced by a compact CanonicalEvent projection and
must pass the ordinary claim-verification policy before it can be published.
"""

from contextlib import contextmanager
from types import ModuleType
from typing import Protocol

import insight_desk.generation as generation_module
import insight_desk.generation_pipeline as generation_pipeline_module
from insight_desk.core import CanonicalEvent, RenderMode
from insight_desk.generation import (
    GeneratedDraft,
    GenerationContractError,
    GenerationRequest,
    validate_preservation,
)
from insight_desk.generation_pipeline import (
    GenerationAttempt,
    GenerationAttemptKind,
    GenerationAttemptStatus,
    GenerationRecoveryResult,
)
from insight_desk.phase7 import Phase7EntryCandidate
from insight_desk.verification_pipeline import verify_generated_draft


_ORIGINAL_GENERATION_STORY_ADMISSION = generation_module.validate_story_admission
_ORIGINAL_PIPELINE_STORY_ADMISSION = generation_pipeline_module.validate_story_admission


class CanonicalEventRegistry(Protocol):
    def canonical_event(self, event_id: str) -> CanonicalEvent: ...


class CanonicalEventRecoveryGenerator:
    """Deterministic compact recovery from canonical semantics, never article prose."""

    def __init__(self, registry: CanonicalEventRegistry) -> None:
        self.registry = registry

    def generate(self, request: GenerationRequest) -> GeneratedDraft:
        event = self.registry.canonical_event(request.event.event_id)
        if event.event_id != request.event.event_id:
            raise GenerationContractError("canonical recovery event identity mismatch")
        if event.fact_ids and tuple(event.fact_ids) != tuple(request.event.fact_ids):
            raise GenerationContractError("canonical recovery fact lineage mismatch")

        actor = event.actor.strip()
        action = event.action.strip()
        if not actor or not action:
            raise GenerationContractError("canonical recovery requires actor and action")

        headline = action if actor.casefold() in action.casefold() else f"{actor}, {action}"
        summary_parts = [f"주체: {actor}", f"사건: {action}"]
        if event.object is not None:
            summary_parts.append(f"대상: {event.object.strip()}")
        if event.event_time is not None:
            summary_parts.append(f"시점: {event.event_time}")
        if event.location is not None:
            summary_parts.append(f"장소: {event.location.strip()}")
        if event.cause is not None:
            summary_parts.append(f"원인: {event.cause.strip()}")
        if event.metric is not None and event.value is not None:
            metric_value = f"{event.metric}: {event.value}"
            if event.unit is not None:
                metric_value += f" {event.unit}"
            summary_parts.append(metric_value)

        return GeneratedDraft(
            event_id=event.event_id,
            headline=headline,
            summary=" · ".join(summary_parts),
            evidence_ids=request.evidence_ids,
        )


def _no_story_readmission(*_args, **_kwargs) -> None:
    return None


@contextmanager
def _production_generation_authority():
    generation_module.validate_story_admission = _no_story_readmission
    generation_pipeline_module.validate_story_admission = _no_story_readmission
    try:
        yield
    finally:
        generation_module.validate_story_admission = _ORIGINAL_GENERATION_STORY_ADMISSION
        generation_pipeline_module.validate_story_admission = _ORIGINAL_PIPELINE_STORY_ADMISSION


def _canonical_recovery_result(
    request: GenerationRequest,
    *,
    generator: CanonicalEventRecoveryGenerator,
    prior: Phase7EntryCandidate | None,
) -> GenerationRecoveryResult:
    draft = generator.generate(request)
    preservation = validate_preservation(request, draft)
    if not preservation.accepted:
        raise GenerationContractError("canonical recovery failed deterministic preservation")

    previous_attempts: tuple[GenerationAttempt, ...] = ()
    if prior is not None:
        previous_attempts = tuple(
            attempt
            for attempt in prior.initial_generation.attempts
            if attempt.kind is not GenerationAttemptKind.EXTRACTIVE_FALLBACK
        )
    next_sequence = max((attempt.sequence for attempt in previous_attempts), default=0) + 1
    attempts = previous_attempts + (
        GenerationAttempt(
            kind=GenerationAttemptKind.ALTERNATE,
            sequence=next_sequence,
            status=GenerationAttemptStatus.ACCEPTED,
        ),
    )
    return GenerationRecoveryResult(
        event_id=request.event.event_id,
        draft=draft,
        render_mode=RenderMode.CANONICAL_RECOVERY,
        preservation=preservation,
        attempts=attempts,
    )


def scope_phase7_story_readmission(core_module: ModuleType, registry: CanonicalEventRegistry) -> None:
    """Install production-only generation ownership without changing historical helpers."""

    generation_module.validate_story_admission = _ORIGINAL_GENERATION_STORY_ADMISSION
    generation_pipeline_module.validate_story_admission = _ORIGINAL_PIPELINE_STORY_ADMISSION

    current = core_module.produce_phase7_entry_candidate
    if getattr(current, "_insight_desk_v2_scoped", False):
        return

    recovery_owner = CanonicalEventRecoveryGenerator(registry)

    def produce_phase7_v2(*args, **kwargs):
        kwargs.setdefault("recovery_generator", recovery_owner)
        recovery_generator = kwargs.pop("recovery_generator")
        if not isinstance(recovery_generator, CanonicalEventRecoveryGenerator):
            raise GenerationContractError("production recovery owner must be canonical-event based")

        if args:
            request = args[0]
        else:
            request = kwargs.get("request")
        if not isinstance(request, GenerationRequest):
            raise GenerationContractError("production Phase7 requires GenerationRequest")

        primary_verifier = kwargs.get("primary_verifier")
        secondary_verifier = kwargs.get("secondary_verifier")
        if primary_verifier is None or secondary_verifier is None:
            raise GenerationContractError("production canonical recovery requires claim verifiers")

        with _production_generation_authority():
            result = current(*args, **kwargs)

        if result is not None and result.final_generation.render_mode is not RenderMode.EXTRACTIVE_FALLBACK:
            return result

        try:
            canonical_generation = _canonical_recovery_result(
                request,
                generator=recovery_generator,
                prior=result,
            )
        except GenerationContractError:
            return None

        verification = verify_generated_draft(
            request,
            canonical_generation.draft,
            primary=primary_verifier,
            secondary=secondary_verifier,
        )
        return Phase7EntryCandidate(
            event_id=request.event.event_id,
            initial_generation=canonical_generation,
            final_generation=canonical_generation,
            verification=verification,
        )

    produce_phase7_v2._insight_desk_v2_scoped = True
    core_module.produce_phase7_entry_candidate = produce_phase7_v2
