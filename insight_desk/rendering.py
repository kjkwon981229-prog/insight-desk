from __future__ import annotations

from datetime import datetime

from insight_desk.core import RenderedBriefing, RenderedEntry, VerificationVerdict
from insight_desk.phase7 import Phase7EntryCandidate
from insight_desk.verification_pipeline import ClaimRole


class RenderingContractError(ValueError):
    """Raised when Phase 8 rendering would cross a verified Phase 7 boundary."""


def render_phase7_candidate(candidate: Phase7EntryCandidate) -> RenderedEntry | None:
    """Convert one verified Phase 7 candidate into the frozen renderer contract.

    Unpublishable candidates are omitted item-locally. The bridge copies only the final draft text,
    supported claim ids, event id, and render mode already established upstream. It has no API for
    manufacturing confidence, numeric key facts, history, watch-next text, or other UI-only content.
    """

    if not candidate.publishable:
        return None

    claims_by_role = {item.role: item.claim for item in candidate.verification.claims}
    headline_claim = claims_by_role.get(ClaimRole.HEADLINE)
    summary_claim = claims_by_role.get(ClaimRole.SUMMARY)
    if headline_claim is None or summary_claim is None:
        raise RenderingContractError("publishable candidate is missing headline or summary claim")
    if headline_claim.verdict is not VerificationVerdict.SUPPORTED:
        raise RenderingContractError("headline claim is not supported")
    if summary_claim.verdict is not VerificationVerdict.SUPPORTED:
        raise RenderingContractError("summary claim is not supported")

    draft = candidate.final_generation.draft
    if headline_claim.text != draft.headline:
        raise RenderingContractError("headline text differs from verified claim")
    if summary_claim.text != draft.summary:
        raise RenderingContractError("summary text differs from verified claim")
    if headline_claim.event_id != candidate.event_id or summary_claim.event_id != candidate.event_id:
        raise RenderingContractError("verified claim belongs to another event")

    return RenderedEntry(
        event_id=candidate.event_id,
        headline=draft.headline,
        summary=draft.summary,
        claim_ids=(headline_claim.claim_id, summary_claim.claim_id),
        render_mode=candidate.final_generation.render_mode,
    )


def build_rendered_briefing(
    *,
    briefing_id: str,
    generated_at: datetime,
    candidates: tuple[Phase7EntryCandidate, ...],
) -> RenderedBriefing:
    """Build a briefing from publishable candidates without global-aborting on rejected items."""

    entries: list[RenderedEntry] = []
    seen_event_ids: set[str] = set()
    for candidate in candidates:
        entry = render_phase7_candidate(candidate)
        if entry is None:
            continue
        if entry.event_id in seen_event_ids:
            raise RenderingContractError(f"duplicate rendered event: {entry.event_id}")
        seen_event_ids.add(entry.event_id)
        entries.append(entry)

    return RenderedBriefing(
        briefing_id=briefing_id,
        generated_at=generated_at,
        entries=tuple(entries),
    )
