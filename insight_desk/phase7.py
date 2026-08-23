from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from insight_desk.core import RenderMode, VerificationVerdict
from insight_desk.generation import GenerationRequest, validate_preservation
from insight_desk.generation_pipeline import (
    DraftGenerator,
    ExtractiveFallbackGenerator,
    ExtractiveFallbackUnavailable,
    GenerationAttempt,
    GenerationAttemptKind,
    GenerationAttemptStatus,
    GenerationRecoveryResult,
    generate_with_recovery,
)
from insight_desk.verification_pipeline import (
    ClaimVerifier,
    GeneratedVerificationResult,
    verify_exact_source_draft,
    verify_generated_draft,
)


class VerificationRecoveryReason(StrEnum):
    # Retained for historical audit compatibility; explicit semantic rejection no longer recovers
    # into different visible text.
    GENERATED_CLAIM_REJECTED = "generated_claim_rejected"
    GENERATED_VERIFICATION_UNAVAILABLE = "generated_verification_unavailable"


@dataclass(frozen=True, slots=True)
class Phase7EntryCandidate:
    event_id: str
    initial_generation: GenerationRecoveryResult
    final_generation: GenerationRecoveryResult
    verification: GeneratedVerificationResult
    verification_recovery_reason: VerificationRecoveryReason | None = None

    def __post_init__(self) -> None:
        if self.initial_generation.event_id != self.event_id:
            raise ValueError("initial generation belongs to another event")
        if self.final_generation.event_id != self.event_id:
            raise ValueError("final generation belongs to another event")
        if self.verification.event_id != self.event_id:
            raise ValueError("verification belongs to another event")
        if self.verification_recovery_reason is None:
            if self.initial_generation is not self.final_generation:
                raise ValueError("generation changed without a verification recovery reason")
        else:
            if self.final_generation.render_mode is not RenderMode.EXTRACTIVE_FALLBACK:
                raise ValueError("verification recovery must end in extractive fallback")

    @property
    def publishable(self) -> bool:
        return self.verification.publishable

    @property
    def event_retained(self) -> bool:
        return True


def _has_indeterminate_verification(result: GeneratedVerificationResult) -> bool:
    return any(
        item.claim.verdict is VerificationVerdict.INDETERMINATE
        for item in result.claims
    )


def _exact_fallback_result(request: GenerationRequest) -> GenerationRecoveryResult:
    draft = ExtractiveFallbackGenerator().generate(request)
    preservation = validate_preservation(request, draft)
    if not preservation.accepted:
        raise ValueError("exact extractive fallback failed deterministic preservation")
    return GenerationRecoveryResult(
        event_id=request.event.event_id,
        draft=draft,
        render_mode=RenderMode.EXTRACTIVE_FALLBACK,
        preservation=preservation,
        attempts=(
            GenerationAttempt(
                kind=GenerationAttemptKind.EXTRACTIVE_FALLBACK,
                sequence=1,
                status=GenerationAttemptStatus.ACCEPTED,
            ),
        ),
    )


def _verify_generation_result(
    request: GenerationRequest,
    generation: GenerationRecoveryResult,
    *,
    primary_verifier: ClaimVerifier,
    secondary_verifier: ClaimVerifier,
) -> GeneratedVerificationResult:
    if generation.render_mode is RenderMode.EXTRACTIVE_FALLBACK:
        return verify_exact_source_draft(request, generation.draft)
    return verify_generated_draft(
        request,
        generation.draft,
        primary=primary_verifier,
        secondary=secondary_verifier,
    )


def produce_phase7_entry_candidate(
    request: GenerationRequest,
    *,
    primary_generator: DraftGenerator | None,
    primary_verifier: ClaimVerifier,
    secondary_verifier: ClaimVerifier,
    alternate_generator: DraftGenerator | None = None,
) -> Phase7EntryCandidate | None:
    """Run the complete Phase 7 generation/verification gate without rendering.

    Generated prose keeps the frozen two-verifier semantic gate. Explicit semantic rejection is a
    content verdict and remains rejected; it is not converted into support by replacing the visible
    text. Verification infrastructure unavailability is different: generated prose stays unauthorized,
    but one display-safe exact-source fallback may be proved deterministically against immutable cited
    EvidenceSpan text. If no safe exact excerpt exists, the item fails closed without aborting the run.
    """

    try:
        initial_generation = generate_with_recovery(
            request,
            primary=primary_generator,
            alternate=alternate_generator,
        )
    except ExtractiveFallbackUnavailable:
        return None

    initial_verification = _verify_generation_result(
        request,
        initial_generation,
        primary_verifier=primary_verifier,
        secondary_verifier=secondary_verifier,
    )

    recovery_reason: VerificationRecoveryReason | None = None
    if (
        initial_generation.render_mode is RenderMode.GENERATED
        and _has_indeterminate_verification(initial_verification)
    ):
        recovery_reason = VerificationRecoveryReason.GENERATED_VERIFICATION_UNAVAILABLE

    if recovery_reason is not None:
        try:
            fallback_generation = _exact_fallback_result(request)
        except ExtractiveFallbackUnavailable:
            return Phase7EntryCandidate(
                event_id=request.event.event_id,
                initial_generation=initial_generation,
                final_generation=initial_generation,
                verification=initial_verification,
            )
        fallback_verification = verify_exact_source_draft(
            request,
            fallback_generation.draft,
        )
        return Phase7EntryCandidate(
            event_id=request.event.event_id,
            initial_generation=initial_generation,
            final_generation=fallback_generation,
            verification=fallback_verification,
            verification_recovery_reason=recovery_reason,
        )

    return Phase7EntryCandidate(
        event_id=request.event.event_id,
        initial_generation=initial_generation,
        final_generation=initial_generation,
        verification=initial_verification,
    )
