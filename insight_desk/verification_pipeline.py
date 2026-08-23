from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from insight_desk.core import VerificationCheck, VerificationVerdict, VerifiedClaim
from insight_desk.core.verification import VerificationPolicy, aggregate_verdict
from insight_desk.generation import (
    GeneratedDraft,
    GenerationContractError,
    GenerationRequest,
    PreservationReport,
    validate_preservation,
)
from insight_desk.providers.cloudflare import CLOUDFLARE_VERIFIER_ID
from insight_desk.providers.local_nli import LOCAL_NLI_VERIFIER_ID


class ClaimRole(StrEnum):
    HEADLINE = "headline"
    SUMMARY = "summary"


class ClaimVerifier(Protocol):
    verifier_id: str
    model_id: str

    def verify(
        self,
        *,
        check_id: str,
        claim_text: str,
        evidence_text: str,
        evidence_ids: tuple[str, ...],
    ) -> VerificationCheck: ...


DEFAULT_VERIFICATION_POLICY = VerificationPolicy(
    primary_verifier_id=CLOUDFLARE_VERIFIER_ID,
    secondary_verifier_id=LOCAL_NLI_VERIFIER_ID,
)


@dataclass(frozen=True, slots=True)
class GeneratedClaimResult:
    role: ClaimRole
    claim: VerifiedClaim


@dataclass(frozen=True, slots=True)
class GeneratedVerificationResult:
    event_id: str
    preservation: PreservationReport
    claims: tuple[GeneratedClaimResult, ...]

    def __post_init__(self) -> None:
        if not self.event_id.strip():
            raise GenerationContractError("verification result event_id must be non-empty")
        if not self.preservation.accepted and self.claims:
            raise GenerationContractError(
                "preservation-rejected generation must not reach claim verifiers"
            )
        roles = tuple(item.role for item in self.claims)
        if len(roles) != len(set(roles)):
            raise GenerationContractError("generated claim roles must be unique")
        for item in self.claims:
            if item.claim.event_id != self.event_id:
                raise GenerationContractError("verified claim belongs to another event")

    @property
    def publishable(self) -> bool:
        if not self.preservation.accepted:
            return False
        by_role = {item.role: item.claim for item in self.claims}
        return all(
            role in by_role and by_role[role].verdict is VerificationVerdict.SUPPORTED
            for role in (ClaimRole.HEADLINE, ClaimRole.SUMMARY)
        )


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}:{digest}"


def _safe_verify(
    verifier: ClaimVerifier,
    *,
    check_id: str,
    claim_text: str,
    evidence_text: str,
    evidence_ids: tuple[str, ...],
) -> VerificationCheck:
    try:
        check = verifier.verify(
            check_id=check_id,
            claim_text=claim_text,
            evidence_text=evidence_text,
            evidence_ids=evidence_ids,
        )
    except Exception as exc:
        return VerificationCheck(
            check_id=check_id,
            verifier_id=verifier.verifier_id,
            model_id=verifier.model_id,
            evidence_ids=evidence_ids,
            entailed=None,
            error_code=f"verifier_exception:{type(exc).__name__.lower()[:80] or 'unknown'}",
            zero_cost=True,
        )
    if check.check_id != check_id:
        raise GenerationContractError("verifier returned mismatched check_id")
    if check.verifier_id != verifier.verifier_id:
        raise GenerationContractError("verifier returned mismatched verifier_id")
    if check.evidence_ids != evidence_ids:
        raise GenerationContractError("verifier returned mismatched evidence_ids")
    return check


def _verify_claim(
    *,
    request: GenerationRequest,
    role: ClaimRole,
    text: str,
    primary: ClaimVerifier,
    secondary: ClaimVerifier,
    policy: VerificationPolicy,
) -> GeneratedClaimResult:
    evidence_ids = request.evidence_ids
    evidence_text = request.evidence_text
    claim_id = _stable_id("claim", request.event.event_id, role.value, text)
    primary_check = _safe_verify(
        primary,
        check_id=_stable_id("check", claim_id, primary.verifier_id),
        claim_text=text,
        evidence_text=evidence_text,
        evidence_ids=evidence_ids,
    )

    checks: list[VerificationCheck] = [primary_check]
    # Primary explicit rejection is final. Primary failure/inconclusive also cannot become SUPPORTED,
    # so invoking the secondary would add compute without changing the aggregate verdict.
    if primary_check.entailed is True:
        checks.append(
            _safe_verify(
                secondary,
                check_id=_stable_id("check", claim_id, secondary.verifier_id),
                claim_text=text,
                evidence_text=evidence_text,
                evidence_ids=evidence_ids,
            )
        )

    frozen_checks = tuple(checks)
    verdict = aggregate_verdict(frozen_checks, policy)
    return GeneratedClaimResult(
        role=role,
        claim=VerifiedClaim(
            claim_id=claim_id,
            event_id=request.event.event_id,
            text=text,
            evidence_ids=evidence_ids,
            checks=frozen_checks,
            verdict=verdict,
        ),
    )


def verify_generated_draft(
    request: GenerationRequest,
    draft: GeneratedDraft,
    *,
    primary: ClaimVerifier,
    secondary: ClaimVerifier,
    policy: VerificationPolicy = DEFAULT_VERIFICATION_POLICY,
) -> GeneratedVerificationResult:
    """Verify generated headline and summary under the frozen Phase 7 policy.

    The deterministic preservation gate always runs first. Rejected preservation never reaches an
    external/local verifier. After preservation passes, Cloudflare-equivalent primary verification
    is decisive for explicit rejection; secondary verification is required only after primary TRUE
    because only TRUE+TRUE can publish. Provider exceptions are converted to item-local inconclusive
    checks and never delete the established event.
    """

    if primary.verifier_id != policy.primary_verifier_id:
        raise GenerationContractError("primary verifier does not match frozen verification policy")
    if secondary.verifier_id != policy.secondary_verifier_id:
        raise GenerationContractError("secondary verifier does not match frozen verification policy")
    if primary.verifier_id == secondary.verifier_id:
        raise GenerationContractError("primary and secondary verifiers must be independent")

    preservation = validate_preservation(request, draft)
    if not preservation.accepted:
        return GeneratedVerificationResult(
            event_id=request.event.event_id,
            preservation=preservation,
            claims=(),
        )

    claims = tuple(
        _verify_claim(
            request=request,
            role=role,
            text=text,
            primary=primary,
            secondary=secondary,
            policy=policy,
        )
        for role, text in (
            (ClaimRole.HEADLINE, draft.headline),
            (ClaimRole.SUMMARY, draft.summary),
        )
    )
    return GeneratedVerificationResult(
        event_id=request.event.event_id,
        preservation=preservation,
        claims=claims,
    )
