from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PipelineStage(StrEnum):
    INGESTION = "ingestion"
    CONTENT_EXTRACTION = "content_extraction"
    FACT_EXTRACTION = "fact_extraction"
    EVENT_IDENTITY = "event_identity"
    CLAIM_VERIFICATION = "claim_verification"
    GENERATION = "generation"
    RENDERING = "rendering"


class FailureKind(StrEnum):
    TRANSIENT_PROVIDER = "transient_provider"
    FREE_QUOTA_EXHAUSTED = "free_quota_exhausted"
    INVALID_OUTPUT = "invalid_output"
    EXTRACTION_EMPTY = "extraction_empty"
    IDENTITY_AMBIGUOUS = "identity_ambiguous"
    UNSUPPORTED_CLAIM = "unsupported_claim"


class RecoveryAction(StrEnum):
    RETRY_FREE_PROVIDER = "retry_free_provider"
    TRY_PLAYWRIGHT_FALLBACK = "try_playwright_fallback"
    TRY_ALTERNATE_FREE_PROVIDER = "try_alternate_free_provider"
    USE_LOCAL_SECONDARY_VERIFIER = "use_local_secondary_verifier"
    MARK_CLAIM_INDETERMINATE = "mark_claim_indeterminate"
    REJECT_CLAIM = "reject_claim"
    KEEP_EVENTS_SEPARATE = "keep_events_separate"
    USE_EXTRACTIVE_FALLBACK = "use_extractive_fallback"
    SKIP_ITEM = "skip_item"


@dataclass(frozen=True, slots=True)
class RecoveryDecision:
    action: RecoveryAction
    preserves_existing_event: bool
    global_abort: bool = False

    def __post_init__(self) -> None:
        if self.global_abort:
            raise ValueError("item-level failures must never become global briefing aborts")


def recovery_action(
    stage: PipelineStage,
    failure: FailureKind,
    *,
    attempts: int = 0,
) -> RecoveryDecision:
    """Return the next zero-cost, item-scoped action for a pipeline failure.

    This policy intentionally has no paid-fallback action and no global-abort action.
    Generation happens after event/claim state exists, so every generation recovery path
    preserves the event. Ambiguous identity fails safe by keeping candidates separate.
    """

    if attempts < 0:
        raise ValueError("attempts must be >= 0")

    if stage is PipelineStage.INGESTION:
        action = RecoveryAction.RETRY_FREE_PROVIDER if attempts == 0 else RecoveryAction.SKIP_ITEM
        return RecoveryDecision(action=action, preserves_existing_event=False)

    if stage is PipelineStage.CONTENT_EXTRACTION:
        if failure is FailureKind.EXTRACTION_EMPTY and attempts == 0:
            return RecoveryDecision(
                action=RecoveryAction.TRY_PLAYWRIGHT_FALLBACK,
                preserves_existing_event=False,
            )
        action = (
            RecoveryAction.RETRY_FREE_PROVIDER
            if failure is FailureKind.TRANSIENT_PROVIDER and attempts == 0
            else RecoveryAction.SKIP_ITEM
        )
        return RecoveryDecision(action=action, preserves_existing_event=False)

    if stage is PipelineStage.FACT_EXTRACTION:
        action = (
            RecoveryAction.TRY_ALTERNATE_FREE_PROVIDER
            if attempts == 0
            else RecoveryAction.SKIP_ITEM
        )
        return RecoveryDecision(action=action, preserves_existing_event=False)

    if stage is PipelineStage.EVENT_IDENTITY:
        return RecoveryDecision(
            action=RecoveryAction.KEEP_EVENTS_SEPARATE,
            preserves_existing_event=True,
        )

    if stage is PipelineStage.CLAIM_VERIFICATION:
        if failure is FailureKind.UNSUPPORTED_CLAIM:
            return RecoveryDecision(
                action=RecoveryAction.REJECT_CLAIM,
                preserves_existing_event=True,
            )
        action = (
            RecoveryAction.USE_LOCAL_SECONDARY_VERIFIER
            if attempts == 0
            else RecoveryAction.MARK_CLAIM_INDETERMINATE
        )
        return RecoveryDecision(action=action, preserves_existing_event=True)

    if stage is PipelineStage.GENERATION:
        if attempts == 0:
            action = RecoveryAction.RETRY_FREE_PROVIDER
        elif attempts == 1:
            action = RecoveryAction.TRY_ALTERNATE_FREE_PROVIDER
        else:
            action = RecoveryAction.USE_EXTRACTIVE_FALLBACK
        return RecoveryDecision(action=action, preserves_existing_event=True)

    return RecoveryDecision(
        action=RecoveryAction.SKIP_ITEM,
        preserves_existing_event=True,
    )
