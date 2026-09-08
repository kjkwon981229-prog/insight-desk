from __future__ import annotations

from dataclasses import dataclass

from .contracts import VerificationCheck, VerificationVerdict


@dataclass(frozen=True, slots=True)
class VerificationPolicy:
    primary_verifier_id: str
    secondary_verifier_id: str

    def __post_init__(self) -> None:
        if not self.primary_verifier_id.strip() or not self.secondary_verifier_id.strip():
            raise ValueError("verifier ids must be non-empty")
        if self.primary_verifier_id == self.secondary_verifier_id:
            raise ValueError("primary and secondary verifiers must be independent ids")


def aggregate_verdict(
    checks: tuple[VerificationCheck, ...],
    policy: VerificationPolicy,
) -> VerificationVerdict:
    """Aggregate one independent primary and one local secondary check conservatively.

    Rules are precision-first:
    - primary explicit rejection => REJECTED;
    - primary + secondary explicit support => SUPPORTED;
    - disagreement, missing result, provider error, or missing role => INDETERMINATE.

    The secondary verifier is never allowed to turn a primary rejection into support. Likewise a
    primary positive alone is not enough to publish when the required secondary check is missing.
    """

    by_verifier: dict[str, VerificationCheck] = {}
    for check in checks:
        if check.verifier_id in by_verifier:
            raise ValueError(f"duplicate verifier result: {check.verifier_id}")
        by_verifier[check.verifier_id] = check

    primary = by_verifier.get(policy.primary_verifier_id)
    secondary = by_verifier.get(policy.secondary_verifier_id)

    if primary is None or primary.entailed is None:
        return VerificationVerdict.INDETERMINATE
    if primary.entailed is False:
        return VerificationVerdict.REJECTED
    if secondary is None or secondary.entailed is None:
        return VerificationVerdict.INDETERMINATE
    if secondary.entailed is False:
        return VerificationVerdict.INDETERMINATE
    return VerificationVerdict.SUPPORTED
