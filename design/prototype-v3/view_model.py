from __future__ import annotations

from dataclasses import dataclass

from insight_desk.core import (
    ContractBundle,
    RenderMode,
    RenderedEntry,
    TemporalState,
    VerificationVerdict,
)


TEMPORAL_LABELS: dict[TemporalState, str] = {
    TemporalState.PLANNED: "예정",
    TemporalState.ANNOUNCED_PROSPECTIVE: "발표 → 예정",
    TemporalState.RESUMING: "재개 예정",
    TemporalState.RESUMED: "재개",
    TemporalState.ONGOING: "진행 중",
    TemporalState.COMPLETED: "완료",
    TemporalState.CANCELLED: "취소",
}

RENDER_MODE_LABELS: dict[RenderMode, str] = {
    RenderMode.GENERATED: "검증 생성",
    RenderMode.EXTRACTIVE_FALLBACK: "원문 기반",
}


@dataclass(frozen=True, slots=True)
class EvidenceView:
    evidence_id: str
    source_name: str
    text: str
    field: str


@dataclass(frozen=True, slots=True)
class EventView:
    event_id: str
    topic_id: str
    headline: str
    summary: str
    state_label: str
    event_date: str | None
    evidence_count: int
    evidence: tuple[EvidenceView, ...]
    verdict_label: str
    render_mode_label: str
    has_partial_verifier_failure: bool
    watch_next: str | None = None
    history_available: bool = False


class RendererMappingError(ValueError):
    pass


def _single_value_or_none(values: list[str]) -> str | None:
    unique = {value for value in values if value}
    if len(unique) == 1:
        return next(iter(unique))
    return None


def _state_label(bundle: ContractBundle, entry: RenderedEntry) -> str:
    event = next(event for event in bundle.events if event.event_id == entry.event_id)
    fact_by_id = {fact.fact_id: fact for fact in bundle.facts}
    states = [fact_by_id[fact_id].temporal_state for fact_id in event.fact_ids]
    states = [state for state in states if state is not None]
    if not states:
        return "상태 미확정"
    unique = set(states)
    if len(unique) != 1:
        return "상태 추가 확인"
    return TEMPORAL_LABELS[next(iter(unique))]


def build_event_view(bundle: ContractBundle, entry: RenderedEntry) -> EventView:
    """Map a validated clean-room bundle into the frozen V3 UI contract.

    The mapper deliberately does not invent numeric confidence, watch-next text,
    or event-history data. Those fields do not exist in the current core contract.
    """
    bundle.validate()

    events = {event.event_id: event for event in bundle.events}
    facts = {fact.fact_id: fact for fact in bundle.facts}
    claims = {claim.claim_id: claim for claim in bundle.claims}
    evidence = {span.evidence_id: span for span in bundle.evidence}
    articles = {article.article_id: article for article in bundle.articles}

    event = events.get(entry.event_id)
    if event is None:
        raise RendererMappingError(f"missing event for entry: {entry.event_id}")

    entry_claims = [claims[claim_id] for claim_id in entry.claim_ids]
    if any(claim.verdict is not VerificationVerdict.SUPPORTED for claim in entry_claims):
        raise RendererMappingError("V3 published event view cannot contain a non-supported claim")

    evidence_ids: list[str] = []
    for claim in entry_claims:
        for evidence_id in claim.evidence_ids:
            if evidence_id not in evidence_ids:
                evidence_ids.append(evidence_id)

    evidence_rows: list[EvidenceView] = []
    for evidence_id in evidence_ids:
        span = evidence[evidence_id]
        article = articles[span.article_id]
        evidence_rows.append(
            EvidenceView(
                evidence_id=evidence_id,
                source_name=article.provenance.source_name,
                text=span.text,
                field=span.field.value,
            )
        )

    event_dates = [facts[fact_id].event_date for fact_id in event.fact_ids if facts[fact_id].event_date]
    event_date = _single_value_or_none(event_dates)

    has_partial_failure = any(
        check.error_code is not None or check.entailed is None
        for claim in entry_claims
        for check in claim.checks
    )

    return EventView(
        event_id=entry.event_id,
        topic_id=event.topic_id,
        headline=entry.headline,
        summary=entry.summary,
        state_label=_state_label(bundle, entry),
        event_date=event_date,
        evidence_count=len(evidence_rows),
        evidence=tuple(evidence_rows),
        verdict_label="검증 완료",
        render_mode_label=RENDER_MODE_LABELS[entry.render_mode],
        has_partial_verifier_failure=has_partial_failure,
    )


def build_briefing_views(bundle: ContractBundle) -> tuple[EventView, ...]:
    bundle.validate()
    if bundle.briefing is None:
        return ()
    return tuple(build_event_view(bundle, entry) for entry in bundle.briefing.entries)
