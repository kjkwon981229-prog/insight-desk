from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
import hashlib
import re
from urllib.parse import urlsplit

from .contracts import Certainty, ContractError, OutcomePolarity, RenderMode, TemporalState


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _require_text(name: str, value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ContractError(f"{name} must be non-empty")
    return stripped


def _require_aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ContractError(f"{name} must be timezone-aware")


def _require_unique(name: str, values: tuple[str, ...], *, allow_empty: bool = False) -> None:
    if not allow_empty and not values:
        raise ContractError(f"{name} must contain at least one id")
    if any(not item.strip() for item in values):
        raise ContractError(f"{name} must contain non-empty ids")
    if len(values) != len(set(values)):
        raise ContractError(f"{name} must not contain duplicate ids")


def _require_http_url(name: str, value: str) -> str:
    stripped = _require_text(name, value)
    parsed = urlsplit(stripped)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ContractError(f"{name} must be an HTTP(S) URL without credentials")
    return stripped


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
    _require_aware("event_time", parsed)


@dataclass(frozen=True, slots=True)
class SourceDocument:
    source_id: str
    candidate_ids: tuple[str, ...]
    publisher: str
    url: str
    title: str
    body: str
    fetched_at: datetime
    publication_time: datetime | None
    retrieved_via: str
    content_sha256: str

    def __post_init__(self) -> None:
        _require_text("source_id", self.source_id)
        _require_unique("candidate_ids", self.candidate_ids)
        _require_text("publisher", self.publisher)
        object.__setattr__(self, "url", _require_http_url("url", self.url))
        _require_text("title", self.title)
        if not isinstance(self.body, str):
            raise ContractError("body must be a string")
        _require_aware("fetched_at", self.fetched_at)
        if self.publication_time is not None:
            _require_aware("publication_time", self.publication_time)
        _require_text("retrieved_via", self.retrieved_via)
        if not _SHA256_RE.fullmatch(self.content_sha256):
            raise ContractError("content_sha256 must be a lowercase SHA-256 hex digest")
        expected_digest = hashlib.sha256(self.body.encode("utf-8")).hexdigest()
        if self.content_sha256 != expected_digest:
            raise ContractError("content_sha256 differs from SourceDocument body bytes")


@dataclass(frozen=True, slots=True)
class CanonicalEvidenceRef:
    """Immutable exact source-range evidence carried across the canonical event boundary."""

    source_id: str
    field: str
    start: int
    end: int
    text_sha256: str

    def __post_init__(self) -> None:
        _require_text("source_id", self.source_id)
        if self.field not in {"title", "body"}:
            raise ContractError("canonical evidence field must be title or body")
        if self.start < 0:
            raise ContractError("canonical evidence start must be >= 0")
        if self.end <= self.start:
            raise ContractError("canonical evidence end must be greater than start")
        if not _SHA256_RE.fullmatch(self.text_sha256):
            raise ContractError("canonical evidence text_sha256 must be a lowercase SHA-256 hex digest")

    def validate_against(self, source: SourceDocument) -> None:
        if source.source_id != self.source_id:
            raise ContractError("canonical evidence source_id differs from SourceDocument")
        text = source.title if self.field == "title" else source.body
        if self.end > len(text):
            raise ContractError("canonical evidence range is outside SourceDocument field")
        digest = hashlib.sha256(text[self.start : self.end].encode("utf-8")).hexdigest()
        if digest != self.text_sha256:
            raise ContractError("canonical evidence range digest differs from SourceDocument bytes")


@dataclass(frozen=True, slots=True)
class AuthoritativeFact:
    fact_id: str
    provider_id: str
    subject: str
    predicate: str
    value: str
    retrieved_at: datetime
    source_url: str
    unit: str | None = None
    effective_time: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("fact_id", self.fact_id),
            ("provider_id", self.provider_id),
            ("subject", self.subject),
            ("predicate", self.predicate),
            ("value", self.value),
        ):
            _require_text(name, value)
        _require_aware("retrieved_at", self.retrieved_at)
        object.__setattr__(self, "source_url", _require_http_url("source_url", self.source_url))
        if self.unit is not None:
            _require_text("unit", self.unit)
        if self.effective_time is not None:
            _require_text("effective_time", self.effective_time)


@dataclass(frozen=True, slots=True)
class CanonicalEvent:
    event_id: str
    topic: str
    actor: str
    action: str
    event_type: str
    source_ids: tuple[str, ...]
    object: str | None = None
    event_time: str | None = None
    publication_time: datetime | None = None
    participants: tuple[str, ...] = ()
    metric: str | None = None
    unit: str | None = None
    value: str | None = None
    attribution: str | None = None
    parent_event_id: str | None = None
    authoritative_fact_ids: tuple[str, ...] = ()
    fact_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    evidence_refs: tuple[CanonicalEvidenceRef, ...] = ()
    temporal_state: TemporalState | None = None
    certainty: Certainty | None = None
    polarity: OutcomePolarity | None = None
    location: str | None = None
    cause: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("event_id", self.event_id),
            ("topic", self.topic),
            ("actor", self.actor),
            ("action", self.action),
            ("event_type", self.event_type),
        ):
            _require_text(name, value)
        _require_unique("source_ids", self.source_ids)
        _require_unique("participants", self.participants, allow_empty=True)
        _require_unique("authoritative_fact_ids", self.authoritative_fact_ids, allow_empty=True)
        _require_unique("fact_ids", self.fact_ids, allow_empty=True)
        _require_unique("evidence_ids", self.evidence_ids, allow_empty=True)
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ContractError("evidence_refs must not contain duplicates")
        if any(ref.source_id not in self.source_ids for ref in self.evidence_refs):
            raise ContractError("canonical evidence source is outside event sources")
        if self.object is not None:
            _require_text("object", self.object)
        _require_event_time(self.event_time)
        if self.publication_time is not None:
            _require_aware("publication_time", self.publication_time)
        if self.metric is None and self.value is not None:
            raise ContractError("value requires metric")
        if self.metric is not None and self.value is None:
            raise ContractError("metric requires value")
        for name, value in (
            ("metric", self.metric),
            ("unit", self.unit),
            ("value", self.value),
            ("attribution", self.attribution),
            ("parent_event_id", self.parent_event_id),
            ("location", self.location),
            ("cause", self.cause),
        ):
            if value is not None:
                _require_text(name, value)
        if self.parent_event_id == self.event_id:
            raise ContractError("event cannot be its own parent")


@dataclass(frozen=True, slots=True)
class VerifiedPublication:
    publication_id: str
    event_id: str
    topic: str
    headline: str
    summary: str
    source_ids: tuple[str, ...]
    primary_source_url: str
    claim_ids: tuple[str, ...]
    verification_check_ids: tuple[str, ...]
    verified_at: datetime
    render_mode: RenderMode
    event_time: str | None = None
    publication_time: datetime | None = None
    parent_event_id: str | None = None
    authoritative_fact_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name, value in (
            ("publication_id", self.publication_id),
            ("event_id", self.event_id),
            ("topic", self.topic),
            ("headline", self.headline),
            ("summary", self.summary),
        ):
            _require_text(name, value)
        _require_unique("source_ids", self.source_ids)
        _require_unique("claim_ids", self.claim_ids)
        _require_unique("verification_check_ids", self.verification_check_ids)
        _require_unique("authoritative_fact_ids", self.authoritative_fact_ids, allow_empty=True)
        object.__setattr__(
            self,
            "primary_source_url",
            _require_http_url("primary_source_url", self.primary_source_url),
        )
        _require_aware("verified_at", self.verified_at)
        _require_event_time(self.event_time)
        if self.publication_time is not None:
            _require_aware("publication_time", self.publication_time)
        if self.parent_event_id is not None:
            _require_text("parent_event_id", self.parent_event_id)
        if self.parent_event_id == self.event_id:
            raise ContractError("publication event cannot be its own parent")


@dataclass(frozen=True, slots=True)
class CanonicalPublicationBundle:
    sources: tuple[SourceDocument, ...] = field(default_factory=tuple)
    authoritative_facts: tuple[AuthoritativeFact, ...] = field(default_factory=tuple)
    events: tuple[CanonicalEvent, ...] = field(default_factory=tuple)
    publications: tuple[VerifiedPublication, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        sources = self._index("source", self.sources, "source_id")
        authoritative = self._index("authoritative fact", self.authoritative_facts, "fact_id")
        events = self._index("event", self.events, "event_id")
        self._index("publication", self.publications, "publication_id")

        for event in self.events:
            for source_id in event.source_ids:
                if source_id not in sources:
                    raise ContractError(f"{event.event_id}: missing source {source_id}")
            for evidence_ref in event.evidence_refs:
                source = sources.get(evidence_ref.source_id)
                if source is None:
                    raise ContractError(
                        f"{event.event_id}: missing evidence source {evidence_ref.source_id}"
                    )
                evidence_ref.validate_against(source)
            for fact_id in event.authoritative_fact_ids:
                if fact_id not in authoritative:
                    raise ContractError(f"{event.event_id}: missing authoritative fact {fact_id}")
            if event.parent_event_id is not None and event.parent_event_id not in events:
                raise ContractError(f"{event.event_id}: missing parent event {event.parent_event_id}")

        for publication in self.publications:
            event = events.get(publication.event_id)
            if event is None:
                raise ContractError(
                    f"{publication.publication_id}: missing canonical event {publication.event_id}"
                )
            if publication.topic != event.topic:
                raise ContractError(f"{publication.publication_id}: topic differs from canonical event")
            if publication.event_time != event.event_time:
                raise ContractError(f"{publication.publication_id}: event_time differs from canonical event")
            if publication.publication_time != event.publication_time:
                raise ContractError(
                    f"{publication.publication_id}: publication_time differs from canonical event"
                )
            if publication.parent_event_id != event.parent_event_id:
                raise ContractError(
                    f"{publication.publication_id}: parent_event_id differs from canonical event"
                )
            if not set(publication.source_ids).issubset(set(event.source_ids)):
                raise ContractError(
                    f"{publication.publication_id}: publication source is outside canonical event"
                )
            if not set(publication.authoritative_fact_ids).issubset(
                set(event.authoritative_fact_ids)
            ):
                raise ContractError(
                    f"{publication.publication_id}: authoritative fact is outside canonical event"
                )
            referenced_urls = {sources[source_id].url for source_id in publication.source_ids}
            if publication.primary_source_url not in referenced_urls:
                raise ContractError(
                    f"{publication.publication_id}: primary source URL is not in publication sources"
                )

    @staticmethod
    def _index(kind: str, values: tuple[object, ...], id_attribute: str) -> dict[str, object]:
        indexed: dict[str, object] = {}
        for value in values:
            identifier = getattr(value, id_attribute)
            if identifier in indexed:
                raise ContractError(f"duplicate {kind} id: {identifier}")
            indexed[identifier] = value
        return indexed
