from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from insight_desk.core import (
    Certainty,
    EvidenceSpan,
    EventFact,
    OutcomePolarity,
    RawArticle,
    TemporalState,
)


def _require_text(name: str, value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{name} must be non-empty")
    return stripped


@dataclass(frozen=True, slots=True)
class FactExtractionRequest:
    article: RawArticle
    topic_id: str
    evidence: tuple[EvidenceSpan, ...]

    def __post_init__(self) -> None:
        _require_text("topic_id", self.topic_id)
        if self.topic_id not in self.article.topic_ids:
            raise ValueError("topic_id must already be attached to the RawArticle")
        if not self.evidence:
            raise ValueError("fact extraction requires at least one evidence span")
        ids = [span.evidence_id for span in self.evidence]
        if len(ids) != len(set(ids)):
            raise ValueError("evidence ids must be unique")
        for span in self.evidence:
            span.validate_against(self.article)


@dataclass(frozen=True, slots=True)
class FactDraft:
    """Untrusted semantic output before conversion into an EventFact."""

    draft_id: str
    subject: str
    action: str
    evidence_ids: tuple[str, ...]
    object: str | None = None
    temporal_state: TemporalState | None = None
    certainty: Certainty = Certainty.ASSERTED
    polarity: OutcomePolarity | None = None
    event_date: str | None = None
    location: str | None = None
    cause: str | None = None
    participants: tuple[str, ...] = ()
    source_start: int | None = None
    source_end: int | None = None

    def __post_init__(self) -> None:
        _require_text("draft_id", self.draft_id)
        _require_text("subject", self.subject)
        _require_text("action", self.action)
        if not self.evidence_ids:
            raise ValueError("FactDraft must cite evidence")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("FactDraft evidence ids must be unique")
        for evidence_id in self.evidence_ids:
            _require_text("evidence_id", evidence_id)
        if (self.source_start is None) != (self.source_end is None):
            raise ValueError("FactDraft source range must provide both start and end")
        if self.source_start is not None and self.source_end is not None:
            if self.source_start < 0 or self.source_end <= self.source_start:
                raise ValueError("FactDraft source range is invalid")
        if len(self.participants) != len(set(self.participants)):
            raise ValueError("participants must be unique")
        for participant in self.participants:
            _require_text("participant", participant)
        for name, value in (
            ("object", self.object),
            ("event_date", self.event_date),
            ("location", self.location),
            ("cause", self.cause),
        ):
            if value is not None:
                _require_text(name, value)

    @property
    def has_exact_source_range(self) -> bool:
        return self.source_start is not None and self.source_end is not None

    def validate_against(self, request: FactExtractionRequest) -> None:
        allowed = {span.evidence_id: span for span in request.evidence}
        for evidence_id in self.evidence_ids:
            if evidence_id not in allowed:
                raise ValueError(
                    f"{self.draft_id}: fact draft cites evidence outside extraction request: {evidence_id}"
                )
            if allowed[evidence_id].article_id != request.article.article_id:
                raise ValueError(
                    f"{self.draft_id}: fact draft cites evidence from another article"
                )

        if self.has_exact_source_range:
            if len(self.evidence_ids) != 1:
                raise ValueError(
                    f"{self.draft_id}: exact source range requires exactly one parent evidence span"
                )
            parent = allowed[self.evidence_ids[0]]
            assert self.source_start is not None and self.source_end is not None
            if self.source_start < parent.start or self.source_end > parent.end:
                raise ValueError(
                    f"{self.draft_id}: source range is outside cited evidence range"
                )
            source = request.article.field_text(parent.field)
            if self.source_end > len(source) or not source[self.source_start : self.source_end].strip():
                raise ValueError(
                    f"{self.draft_id}: source range is outside article source or empty"
                )

    def to_event_fact(
        self,
        *,
        fact_id: str,
        evidence_ids: tuple[str, ...] | None = None,
    ) -> EventFact:
        return EventFact(
            fact_id=fact_id,
            subject=self.subject.strip(),
            action=self.action.strip(),
            object=self.object.strip() if self.object is not None else None,
            temporal_state=self.temporal_state,
            certainty=self.certainty,
            polarity=self.polarity,
            event_date=self.event_date.strip() if self.event_date is not None else None,
            location=self.location.strip() if self.location is not None else None,
            cause=self.cause.strip() if self.cause is not None else None,
            participants=tuple(value.strip() for value in self.participants),
            evidence_ids=evidence_ids if evidence_ids is not None else self.evidence_ids,
        )


class FactExtractorPort(Protocol):
    extractor_id: str

    def extract(self, request: FactExtractionRequest) -> tuple[FactDraft, ...]: ...
