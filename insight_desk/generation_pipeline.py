from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from insight_desk.core import EvidenceField, RenderMode
from insight_desk.generation import (
    GeneratedDraft,
    GenerationRequest,
    PreservationReport,
    validate_preservation,
)


class DraftGenerator(Protocol):
    def generate(self, request: GenerationRequest) -> GeneratedDraft: ...


class GenerationAttemptKind(StrEnum):
    PRIMARY = "primary"
    ALTERNATE = "alternate"
    EXTRACTIVE_FALLBACK = "extractive_fallback"


class GenerationAttemptStatus(StrEnum):
    ACCEPTED = "accepted"
    PROVIDER_ERROR = "provider_error"
    PRESERVATION_REJECTED = "preservation_rejected"


@dataclass(frozen=True, slots=True)
class GenerationAttempt:
    kind: GenerationAttemptKind
    sequence: int
    status: GenerationAttemptStatus
    error_code: str | None = None

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError("generation attempt sequence must be >= 1")
        if self.status is GenerationAttemptStatus.PROVIDER_ERROR and not self.error_code:
            raise ValueError("provider-error attempt must carry error_code")
        if self.status is not GenerationAttemptStatus.PROVIDER_ERROR and self.error_code is not None:
            raise ValueError("only provider-error attempt may carry error_code")


@dataclass(frozen=True, slots=True)
class GenerationRecoveryResult:
    event_id: str
    draft: GeneratedDraft
    render_mode: RenderMode
    preservation: PreservationReport
    attempts: tuple[GenerationAttempt, ...]

    def __post_init__(self) -> None:
        if self.draft.event_id != self.event_id:
            raise ValueError("generation recovery result cannot cross event identity")
        if not self.preservation.accepted:
            raise ValueError("final generation recovery draft must pass deterministic preservation")
        if not self.attempts:
            raise ValueError("generation recovery result must record at least one attempt")
        if self.attempts[-1].status is not GenerationAttemptStatus.ACCEPTED:
            raise ValueError("final generation attempt must be accepted")


class ExtractiveFallbackGenerator:
    """Zero-generation fallback that copies exact cited source spans.

    It deliberately ignores NEWS_REWRITE_POLICY_V1 rule 0-4 because this is not generated rewrite
    output. RenderMode.EXTRACTIVE_FALLBACK keeps that distinction explicit for downstream rendering.
    """

    def generate(self, request: GenerationRequest) -> GeneratedDraft:
        evidence_ids = request.evidence_ids
        spans = [request.evidence[evidence_id] for evidence_id in evidence_ids]
        title_spans = [span for span in spans if span.field is EvidenceField.TITLE]
        body_spans = [span for span in spans if span.field is EvidenceField.BODY]
        headline_source = title_spans[0] if title_spans else spans[0]
        summary_source = body_spans[0] if body_spans else spans[0]
        return GeneratedDraft(
            event_id=request.event.event_id,
            headline=headline_source.text,
            summary=summary_source.text,
            evidence_ids=evidence_ids,
        )


def _attempt_generated(
    generator: DraftGenerator,
    request: GenerationRequest,
    *,
    kind: GenerationAttemptKind,
    sequence: int,
) -> tuple[GeneratedDraft | None, PreservationReport | None, GenerationAttempt]:
    try:
        draft = generator.generate(request)
    except Exception as exc:
        return (
            None,
            None,
            GenerationAttempt(
                kind=kind,
                sequence=sequence,
                status=GenerationAttemptStatus.PROVIDER_ERROR,
                error_code=f"{type(exc).__name__.lower()[:80] or 'unknown'}",
            ),
        )
    preservation = validate_preservation(request, draft)
    if not preservation.accepted:
        return (
            None,
            preservation,
            GenerationAttempt(
                kind=kind,
                sequence=sequence,
                status=GenerationAttemptStatus.PRESERVATION_REJECTED,
            ),
        )
    return (
        draft,
        preservation,
        GenerationAttempt(
            kind=kind,
            sequence=sequence,
            status=GenerationAttemptStatus.ACCEPTED,
        ),
    )


def generate_with_recovery(
    request: GenerationRequest,
    *,
    primary: DraftGenerator,
    alternate: DraftGenerator | None = None,
) -> GenerationRecoveryResult:
    """Apply the frozen zero-cost generation recovery order without deleting the event.

    Order: primary → one free retry of primary → explicitly configured alternate (optional) → exact
    extractive fallback. No alternate provider is invented here, and the final fallback is not
    injectable: it is always exact-source ExtractiveFallbackGenerator. Provider and preservation
    failures remain item-local and are recorded as attempts.
    """

    attempts: list[GenerationAttempt] = []
    sequence = 0

    for _ in range(2):
        sequence += 1
        draft, preservation, attempt = _attempt_generated(
            primary,
            request,
            kind=GenerationAttemptKind.PRIMARY,
            sequence=sequence,
        )
        attempts.append(attempt)
        if draft is not None and preservation is not None:
            return GenerationRecoveryResult(
                event_id=request.event.event_id,
                draft=draft,
                render_mode=RenderMode.GENERATED,
                preservation=preservation,
                attempts=tuple(attempts),
            )

    if alternate is not None:
        sequence += 1
        draft, preservation, attempt = _attempt_generated(
            alternate,
            request,
            kind=GenerationAttemptKind.ALTERNATE,
            sequence=sequence,
        )
        attempts.append(attempt)
        if draft is not None and preservation is not None:
            return GenerationRecoveryResult(
                event_id=request.event.event_id,
                draft=draft,
                render_mode=RenderMode.GENERATED,
                preservation=preservation,
                attempts=tuple(attempts),
            )

    sequence += 1
    draft = ExtractiveFallbackGenerator().generate(request)
    preservation = validate_preservation(request, draft)
    if not preservation.accepted:
        raise ValueError("extractive fallback violated deterministic preservation contract")
    attempts.append(
        GenerationAttempt(
            kind=GenerationAttemptKind.EXTRACTIVE_FALLBACK,
            sequence=sequence,
            status=GenerationAttemptStatus.ACCEPTED,
        )
    )
    return GenerationRecoveryResult(
        event_id=request.event.event_id,
        draft=draft,
        render_mode=RenderMode.EXTRACTIVE_FALLBACK,
        preservation=preservation,
        attempts=tuple(attempts),
    )
