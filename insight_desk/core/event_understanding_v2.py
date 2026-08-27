from __future__ import annotations

"""Semantic handoff contracts for the Canonical V2 event-understanding stage.

These types define what the semantic owner must produce before authoritative enrichment and
canonical identity run. They contain no provider implementation and no keyword heuristics.
Evidence/fact extraction may assist the owner, but cannot itself become the semantic answer simply
by being wrapped in a CanonicalEvent.
"""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
import hashlib
import re

from .canonical_v2 import SourceDocument
from .contracts import ContractError


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ArticleEventRole(StrEnum):
    PRIMARY = "primary"
    SUPPORTING = "supporting"
    CONTEXT = "context"


class TopicRelation(StrEnum):
    DIRECT = "direct"
    INDIRECT_EFFECT = "indirect_effect"
    BACKGROUND = "background"
    INCIDENTAL = "incidental"
    UNRELATED = "unrelated"
    UNRESOLVED = "unresolved"


class UnderstandingStatus(StrEnum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"


class UnderstandingEvidenceField(StrEnum):
    TITLE = "title"
    BODY = "body"


def _require_text(name: str, value: str) -> str:
    text = value.strip()
    if not text:
        raise ContractError(f"{name} must be non-empty")
    return text


def _require_unique(name: str, values: tuple[str, ...], *, allow_empty: bool = False) -> None:
    if not allow_empty and not values:
        raise ContractError(f"{name} must contain at least one id")
    if any(not value.strip() for value in values):
        raise ContractError(f"{name} must contain non-empty ids")
    if len(values) != len(set(values)):
        raise ContractError(f"{name} must not contain duplicate ids")


def _require_event_time(value: str | None) -> None:
    if value is None:
        return
    text = _require_text("event_time", value)
    try:
        if "T" not in text:
            date.fromisoformat(text)
            return
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("event_time must be ISO-8601 date or offset-aware datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractError("event_time datetime must be offset-aware")


@dataclass(frozen=True, slots=True)
class UnderstandingEvidenceRef:
    """Exact source-range lineage for one semantic assertion.

    The semantic owner chooses the relevant range, but deterministic validation alone proves that
    the submitted offsets and digest point to immutable SourceDocument text. No generated quote is
    trusted as provenance.
    """

    source_id: str
    field: UnderstandingEvidenceField
    start: int
    end: int
    text_sha256: str

    def __post_init__(self) -> None:
        _require_text("source_id", self.source_id)
        if self.start < 0:
            raise ContractError("evidence start must be >= 0")
        if self.end <= self.start:
            raise ContractError("evidence end must be greater than start")
        if not _SHA256_RE.fullmatch(self.text_sha256):
            raise ContractError("evidence text_sha256 must be a lowercase SHA-256 hex digest")

    @classmethod
    def from_source(
        cls,
        source: SourceDocument,
        *,
        field: UnderstandingEvidenceField,
        start: int,
        end: int,
    ) -> "UnderstandingEvidenceRef":
        text = source.title if field is UnderstandingEvidenceField.TITLE else source.body
        if start < 0 or end <= start or end > len(text):
            raise ContractError("evidence range is outside source field")
        return cls(
            source_id=source.source_id,
            field=field,
            start=start,
            end=end,
            text_sha256=hashlib.sha256(text[start:end].encode("utf-8")).hexdigest(),
        )

    def validate_against(self, source: SourceDocument) -> None:
        if source.source_id != self.source_id:
            raise ContractError("evidence source_id differs from SourceDocument")
        text = source.title if self.field is UnderstandingEvidenceField.TITLE else source.body
        if self.end > len(text):
            raise ContractError("evidence range is outside SourceDocument field")
        digest = hashlib.sha256(text[self.start : self.end].encode("utf-8")).hexdigest()
        if digest != self.text_sha256:
            raise ContractError("evidence range digest differs from SourceDocument bytes")


@dataclass(frozen=True, slots=True)
class CanonicalEventDraft:
    """One semantically understood event before canonical identity is assigned.

    ``draft_id`` is provisional and source-scoped. The identity owner, not the understanding owner,
    decides whether several drafts become one CanonicalEvent, remain distinct, or form a
    parent/child family.
    """

    draft_id: str
    topic: str
    actor: str
    action: str
    event_type: str
    source_ids: tuple[str, ...]
    evidence_refs: tuple[UnderstandingEvidenceRef, ...]
    article_role: ArticleEventRole
    topic_relation: TopicRelation
    understanding_status: UnderstandingStatus
    object: str | None = None
    event_time: str | None = None
    participants: tuple[str, ...] = ()
    metric: str | None = None
    unit: str | None = None
    value: str | None = None
    attribution: str | None = None
    parent_event_hint: str | None = None
    authoritative_fact_ids: tuple[str, ...] = ()
    uncertainty_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name, value in (
            ("draft_id", self.draft_id),
            ("topic", self.topic),
            ("actor", self.actor),
            ("action", self.action),
            ("event_type", self.event_type),
        ):
            _require_text(name, value)
        _require_unique("source_ids", self.source_ids)
        if not self.evidence_refs:
            raise ContractError("event draft requires at least one evidence ref")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ContractError("event draft evidence refs must be unique")
        if any(ref.source_id not in self.source_ids for ref in self.evidence_refs):
            raise ContractError("event draft evidence source is outside draft sources")
        _require_unique("participants", self.participants, allow_empty=True)
        _require_unique("authoritative_fact_ids", self.authoritative_fact_ids, allow_empty=True)
        _require_unique("uncertainty_reasons", self.uncertainty_reasons, allow_empty=True)
        if self.object is not None:
            _require_text("object", self.object)
        _require_event_time(self.event_time)
        if self.metric is None and self.value is not None:
            raise ContractError("value requires metric")
        if self.metric is not None and self.value is None:
            raise ContractError("metric requires value")
        for name, value in (
            ("metric", self.metric),
            ("unit", self.unit),
            ("value", self.value),
            ("attribution", self.attribution),
            ("parent_event_hint", self.parent_event_hint),
        ):
            if value is not None:
                _require_text(name, value)
        if self.understanding_status is UnderstandingStatus.RESOLVED and self.uncertainty_reasons:
            raise ContractError("resolved event draft cannot carry uncertainty reasons")
        if self.understanding_status is UnderstandingStatus.UNRESOLVED and not self.uncertainty_reasons:
            raise ContractError("unresolved event draft requires uncertainty reasons")


@dataclass(frozen=True, slots=True)
class ArticleUnderstanding:
    """Complete semantic result for one relevant source set.

    Resolved understanding must identify at least one primary event. Unresolved understanding is a
    first-class result and is routed to uncertainty resolution; it is not equivalent to DROP.
    """

    understanding_id: str
    topic: str
    source_ids: tuple[str, ...]
    event_drafts: tuple[CanonicalEventDraft, ...]
    status: UnderstandingStatus
    uncertainty_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text("understanding_id", self.understanding_id)
        _require_text("topic", self.topic)
        _require_unique("source_ids", self.source_ids)
        _require_unique("uncertainty_reasons", self.uncertainty_reasons, allow_empty=True)
        draft_ids = tuple(draft.draft_id for draft in self.event_drafts)
        _require_unique("event draft ids", draft_ids, allow_empty=True)
        source_set = set(self.source_ids)
        for draft in self.event_drafts:
            if draft.topic != self.topic:
                raise ContractError(f"{draft.draft_id}: draft topic differs from understanding topic")
            if not set(draft.source_ids).issubset(source_set):
                raise ContractError(f"{draft.draft_id}: draft source is outside understanding sources")
        if self.status is UnderstandingStatus.RESOLVED:
            if self.uncertainty_reasons:
                raise ContractError("resolved understanding cannot carry uncertainty reasons")
            if not self.event_drafts:
                raise ContractError("resolved understanding requires at least one event draft")
            if not any(
                draft.article_role is ArticleEventRole.PRIMARY
                for draft in self.event_drafts
            ):
                raise ContractError("resolved understanding requires at least one primary event")
        elif not self.uncertainty_reasons:
            raise ContractError("unresolved understanding requires uncertainty reasons")
