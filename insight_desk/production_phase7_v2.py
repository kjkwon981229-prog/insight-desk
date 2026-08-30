from __future__ import annotations

"""Production Phase 7 ownership after CanonicalEvent promotion.

Historical generation helpers remain available for replay compatibility, but production-visible text
is rendered deterministically from CanonicalEvent. This removes the remaining semantic mutation
surface between Event Understanding and publication: provider-generated prose may not replace the
canonical event meaning in the user-visible briefing. Exact canonical evidence remains bound to the
request and ordinary claim Verification still has to support the deterministic projection.
"""

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
from types import ModuleType
from typing import Protocol

import insight_desk.generation as generation_module
import insight_desk.generation_pipeline as generation_pipeline_module
from insight_desk.core import CanonicalEvent, EventFact, RenderMode, SourceDocument
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

    def source_for_event(self, event_id: str) -> SourceDocument: ...


@dataclass(frozen=True, slots=True)
class CanonicalGenerationRequest(GenerationRequest):
    """Production GenerationRequest whose semantic payload is one CanonicalEvent.

    ``facts`` remains a compatibility projection for the existing preservation helpers. ``evidence``
    contains only exact EvidenceSpan ranges that correspond to canonical evidence refs. ``fact_text``
    remains available as a canonical semantic serialization for audit/tests, but production-visible
    text is no longer delegated to a prose-generation provider.
    """

    canonical_event: CanonicalEvent

    def __post_init__(self) -> None:
        GenerationRequest.__post_init__(self)
        if self.canonical_event.event_id != self.event.event_id:
            raise GenerationContractError("canonical generation event identity mismatch")
        if self.canonical_event.topic != self.event.topic_id:
            raise GenerationContractError("canonical generation topic identity mismatch")

    @property
    def fact_text(self) -> str:
        event = self.canonical_event
        parts = [
            f"topic={event.topic}",
            f"actor={event.actor}",
            f"action={event.action}",
        ]
        if event.object is not None:
            parts.append(f"object={event.object}")
        if event.event_time is not None:
            parts.append(f"event_time={event.event_time}")
        if event.location is not None:
            parts.append(f"location={event.location}")
        if event.cause is not None:
            parts.append(f"cause={event.cause}")
        if event.participants:
            parts.append("participants=" + ", ".join(event.participants))
        if event.temporal_state is not None:
            parts.append(f"temporal_state={event.temporal_state.value}")
        if event.certainty is not None:
            parts.append(f"certainty={event.certainty.value}")
        if event.polarity is not None:
            parts.append(f"polarity={event.polarity.value}")
        if event.metric is not None and event.value is not None:
            metric_value = event.value
            if event.unit is not None:
                metric_value += f" {event.unit}"
            parts.append(f"metric={event.metric}: {metric_value}")
        if event.attribution is not None:
            parts.append(f"attribution={event.attribution}")
        return f"canonical_event:{event.event_id}: " + " | ".join(parts)


def _canonical_evidence_ids(
    registry: CanonicalEventRegistry,
    request: GenerationRequest,
    event: CanonicalEvent,
) -> tuple[str, ...]:
    """Map immutable canonical source ranges back to existing EvidenceSpan ids.

    Raw EventFact meaning is never consulted. The legacy request is used only as a provenance index
    for evidence ids already admitted into the event. Missing or divergent canonical evidence fails
    closed instead of falling back to legacy semantic facts.
    """

    if not event.evidence_refs:
        raise GenerationContractError("canonical generation requires canonical evidence refs")
    source = registry.source_for_event(event.event_id)
    if tuple(event.source_ids) != (source.source_id,):
        raise GenerationContractError("canonical generation requires one bound primary source")

    allowed_ids = request.evidence_ids
    matched_ids: list[str] = []
    seen: set[str] = set()
    for ref in event.evidence_refs:
        try:
            ref.validate_against(source)
        except Exception as exc:
            raise GenerationContractError("canonical evidence no longer matches SourceDocument") from exc

        matched_id = None
        for evidence_id in allowed_ids:
            span = request.evidence[evidence_id]
            if span.field.value != ref.field or span.start != ref.start or span.end != ref.end:
                continue
            digest = hashlib.sha256(span.text.encode("utf-8")).hexdigest()
            if digest != ref.text_sha256:
                continue
            matched_id = evidence_id
            break
        if matched_id is None:
            raise GenerationContractError("canonical evidence ref is absent from generation provenance")
        if matched_id not in seen:
            seen.add(matched_id)
            matched_ids.append(matched_id)

    if not matched_ids:
        raise GenerationContractError("canonical generation evidence mapping is empty")
    return tuple(matched_ids)


def build_canonical_generation_request(
    registry: CanonicalEventRegistry,
    request: GenerationRequest,
) -> CanonicalGenerationRequest:
    """Replace legacy semantic input with canonical semantics before visible rendering."""

    if len(request.event.fact_ids) != 1:
        raise GenerationContractError(
            "production canonical generation requires one pre-identity fact lineage"
        )
    event = registry.canonical_event(request.event.event_id)
    if event.event_id != request.event.event_id or event.topic != request.event.topic_id:
        raise GenerationContractError("canonical generation ingress identity mismatch")
    if event.certainty is None:
        raise GenerationContractError("canonical generation requires resolved certainty")

    evidence_ids = _canonical_evidence_ids(registry, request, event)
    fact_id = request.event.fact_ids[0]
    projected_fact = EventFact(
        fact_id=fact_id,
        subject=event.actor,
        action=event.action,
        object=event.object,
        evidence_ids=evidence_ids,
        temporal_state=event.temporal_state,
        certainty=event.certainty,
        polarity=event.polarity,
        event_date=event.event_time,
        location=event.location,
        cause=event.cause,
        participants=event.participants,
    )
    evidence = {evidence_id: request.evidence[evidence_id] for evidence_id in evidence_ids}
    return CanonicalGenerationRequest(
        event=request.event,
        facts={fact_id: projected_fact},
        evidence=evidence,
        canonical_event=event,
    )


class CanonicalEventRecoveryGenerator:
    """Deterministic visible projection from CanonicalEvent, never free-form article prose."""

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

        # Only the evidence-bound core semantic slots are surfaced. CanonicalEvent can carry
        # normalized event_time/metric/location fields whose representation is useful for identity
        # and authority but is not necessarily a literal surface found in the cited EvidenceSpan.
        # Rendering those normalized values would make the preservation gate see a novel date/number
        # even though the underlying event is correct. Keep those fields downstream metadata-only.
        headline = action if actor.casefold() in action.casefold() else f"{actor}, {action}"
        summary_parts = [f"주체: {actor}", f"사건: {action}"]
        object_text = (event.object or "").strip()
        if object_text and object_text.casefold() not in action.casefold():
            if object_text in request.evidence_text:
                summary_parts.append(f"대상: {object_text}")

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
    prior: Phase7EntryCandidate | None = None,
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
    """Install CanonicalEvent as the sole production-visible text authority."""

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

        canonical_request = build_canonical_generation_request(registry, request)
        try:
            canonical_generation = _canonical_recovery_result(
                canonical_request,
                generator=recovery_generator,
            )
        except GenerationContractError:
            return None

        verification = verify_generated_draft(
            canonical_request,
            canonical_generation.draft,
            primary=primary_verifier,
            secondary=secondary_verifier,
        )
        return Phase7EntryCandidate(
            event_id=canonical_request.event.event_id,
            initial_generation=canonical_generation,
            final_generation=canonical_generation,
            verification=verification,
        )

    produce_phase7_v2._insight_desk_v2_scoped = True
    core_module.produce_phase7_entry_candidate = produce_phase7_v2
