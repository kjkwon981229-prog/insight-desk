from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from insight_desk.core import RenderMode, VerificationVerdict
from insight_desk.generation import GenerationRequest, validate_preservation
from insight_desk.generation_pipeline import (
    DraftGenerator,
    ExtractiveFallbackGenerator,
    GenerationAttempt,
    GenerationAttemptKind,
    GenerationAttemptStatus,
    GenerationRecoveryResult,
    generate_with_recovery,
)
from insight_desk.verification_pipeline import (
    ClaimVerifier,
    GeneratedVerificationResult,
    verify_generated_draft,
)


class VerificationRecoveryReason(StrEnum):
    GENERATED_CLAIM_REJECTED = "generated_claim_rejected"


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
                raise ValueError("verification rejection recovery must end in extractive fallback")

    @property
    def publishable(self) -> bool:
        return self.verification.publishable

    @property
    def event_retained(self) -> bool:
        return True


def _has_explicit_rejection(result: GeneratedVerificationResult) -> bool:
    return any(
        item.claim.verdict is VerificationVerdict.REJECTED
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


def produce_phase7_entry_candidate(
    request: GenerationRequest,
    *,
    primary_generator: DraftGenerator,
    primary_verifier: ClaimVerifier,
    secondary_verifier: ClaimVerifier,
    alternate_generator: DraftGenerator | None = None,
) -> Phase7EntryCandidate:
    """Run the complete Phase 7 generation/verification gate without rendering.

    Generation recovery first produces a preservation-safe draft. That draft is then verified under
    the frozen two-verifier policy. A generated draft with an explicit REJECTED claim gets exactly one
    exact-source fallback attempt followed by one more verification pass. INDETERMINATE verification
    does not trigger regeneration because a provider failure/disagreement cannot be repaired by
    rewriting text. The established event is always retained regardless of publishability.
    """

    initial_generation = generate_with_recovery(
        request,
        primary=primary_generator,
        alternate=alternate_generator,
    )
    initial_verification = verify_generated_draft(
        request,
        initial_generation.draft,
        primary=primary_verifier,
        secondary=secondary_verifier,
    )

    if (
        initial_generation.render_mode is RenderMode.GENERATED
        and _has_explicit_rejection(initial_verification)
    ):
        fallback_generation = _exact_fallback_result(request)
        fallback_verification = verify_generated_draft(
            request,
            fallback_generation.draft,
            primary=primary_verifier,
            secondary=secondary_verifier,
        )
        return Phase7EntryCandidate(
            event_id=request.event.event_id,
            initial_generation=initial_generation,
            final_generation=fallback_generation,
            verification=fallback_verification,
            verification_recovery_reason=VerificationRecoveryReason.GENERATED_CLAIM_REJECTED,
        )

    return Phase7EntryCandidate(
        event_id=request.event.event_id,
        initial_generation=initial_generation,
        final_generation=initial_generation,
        verification=initial_verification,
    )
