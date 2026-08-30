from __future__ import annotations

"""Production-only claim-verification adapter for CanonicalEvent fidelity.

Generation is allowed to paraphrase a CanonicalEvent, but it is not allowed to change that event's
meaning. The ordinary Phase 7 verifiers historically checked generated prose only against raw source
evidence. That is necessary but not sufficient: a source article can contain multiple true statements,
so a generated headline may be source-supported while no longer expressing the CanonicalEvent that
Event Understanding admitted.

This adapter keeps Verification as the owner of generated-claim correctness. For each verifier slot it
first asks the same verifier whether the generated claim is entailed by the immutable CanonicalEvent
semantic projection. Only when that passes does it run the existing source-evidence check. No detector,
headline rule, identity heuristic, or article-specific exception is introduced.
"""

from dataclasses import dataclass

from insight_desk.core import VerificationCheck
from insight_desk.generation import GenerationContractError
from insight_desk.verification_pipeline import ClaimVerifier


CANONICAL_FIDELITY_REJECTED = "canonical_fidelity_rejected"
CANONICAL_FIDELITY_INDETERMINATE = "canonical_fidelity_indeterminate"


@dataclass(slots=True)
class CanonicalFidelityVerifier:
    """Require one verifier slot to support both canonical meaning and cited source evidence."""

    base: ClaimVerifier
    canonical_text: str

    def __post_init__(self) -> None:
        if not self.canonical_text.strip():
            raise GenerationContractError("canonical fidelity premise must be non-empty")

    @property
    def verifier_id(self) -> str:
        return self.base.verifier_id

    @property
    def model_id(self) -> str:
        return self.base.model_id

    def _validate_base_check(
        self,
        check: VerificationCheck,
        *,
        check_id: str,
        evidence_ids: tuple[str, ...],
    ) -> None:
        if check.check_id != check_id:
            raise GenerationContractError("canonical fidelity base verifier changed check identity")
        if check.verifier_id != self.verifier_id:
            raise GenerationContractError("canonical fidelity base verifier changed verifier identity")
        if check.evidence_ids != evidence_ids:
            raise GenerationContractError("canonical fidelity base verifier changed evidence identity")
        if not check.zero_cost:
            raise GenerationContractError("paid canonical fidelity verification is forbidden")

    def verify(
        self,
        *,
        check_id: str,
        claim_text: str,
        evidence_text: str,
        evidence_ids: tuple[str, ...],
    ) -> VerificationCheck:
        """Check CanonicalEvent entailment first, then ordinary source entailment.

        The caller still receives one VerificationCheck for the logical verifier slot, so the frozen
        two-slot aggregation policy is unchanged. A canonical rejection is surfaced explicitly in the
        error code and source verification is skipped for that claim.
        """

        canonical_check_id = f"{check_id}:canonical-fidelity"
        canonical_check = self.base.verify(
            check_id=canonical_check_id,
            claim_text=claim_text,
            evidence_text=self.canonical_text,
            evidence_ids=evidence_ids,
        )
        self._validate_base_check(
            canonical_check,
            check_id=canonical_check_id,
            evidence_ids=evidence_ids,
        )

        if canonical_check.entailed is False:
            return VerificationCheck(
                check_id=check_id,
                verifier_id=self.verifier_id,
                model_id=canonical_check.model_id,
                evidence_ids=evidence_ids,
                entailed=False,
                error_code=CANONICAL_FIDELITY_REJECTED,
                zero_cost=True,
            )
        if canonical_check.entailed is None:
            reason = canonical_check.error_code or "provider_inconclusive"
            return VerificationCheck(
                check_id=check_id,
                verifier_id=self.verifier_id,
                model_id=canonical_check.model_id,
                evidence_ids=evidence_ids,
                entailed=None,
                error_code=f"{CANONICAL_FIDELITY_INDETERMINATE}:{reason}",
                zero_cost=True,
            )

        source_check = self.base.verify(
            check_id=check_id,
            claim_text=claim_text,
            evidence_text=evidence_text,
            evidence_ids=evidence_ids,
        )
        self._validate_base_check(
            source_check,
            check_id=check_id,
            evidence_ids=evidence_ids,
        )
        return source_check


def wrap_claim_verifiers_for_canonical_fidelity(
    *,
    primary: ClaimVerifier,
    secondary: ClaimVerifier,
    canonical_text: str,
) -> tuple[CanonicalFidelityVerifier, CanonicalFidelityVerifier]:
    """Wrap both frozen verifier slots with the same CanonicalEvent semantic premise."""

    return (
        CanonicalFidelityVerifier(base=primary, canonical_text=canonical_text),
        CanonicalFidelityVerifier(base=secondary, canonical_text=canonical_text),
    )
