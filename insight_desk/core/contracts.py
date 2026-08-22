from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class ContractError(ValueError):
    """Raised when clean-room engine data violates a structural invariant."""


class EvidenceField(StrEnum):
    TITLE = "title"
    BODY = "body"


class TemporalState(StrEnum):
    PLANNED = "planned"
    ANNOUNCED_PROSPECTIVE = "announced_prospective"
    RESUMING = "resuming"
    RESUMED = "resumed"
    ONGOING = "ongoing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Certainty(StrEnum):
    ASSERTED = "asserted"
    POSSIBLE = "possible"
    CONDITIONAL = "conditional"


class OutcomePolarity(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class VerificationVerdict(StrEnum):
    SUPPORTED = "supported"
    REJECTED = "rejected"
    INDETERMINATE = "indeterminate"


class RenderMode(StrEnum):
    GENERATED = "generated"
    EXTRACTIVE_FALLBACK = "extractive_fallback"


def _require_text(name: str, value: str) -> None:
    if not value or not value.strip():
        raise ContractError(f"{name} must be non-empty")


def _require_aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ContractError(f"{name} must be timezone-aware")


def _require_unique_nonempty(name: str, values: tuple[str, ...], *, allow_empty: bool = False) -> None:
    if not allow_empty and not values:
        raise ContractError(f"{name} must contain at least one id")
    for value in values:
        _require_text(name, value)
    if len(values) != len(set(values)):
        raise ContractError(f"{name} must not contain duplicate ids")


@dataclass(frozen=True, slots=True)
class SourceProvenance:
    source_id: str
    source_name: str
    url: str
    retrieved_via: str
    fetched_at: datetime
    published_at: datetime | None = None

    def __post_init__(self) -> None:
        _require_text("source_id", self.source_id)
        _require_text("source_name", self.source_name)
        _require_text("url", self.url)
        _require_text("retrieved_via", self.retrieved_via)
        _require_aware("fetched_at", self.fetched_at)
        if self.published_at is not None:
            _require_aware("published_at", self.published_at)


@dataclass(frozen=True, slots=True)
class RawArticle:
    article_id: str
    provenance: SourceProvenance
    title: str
    body: str
    topic_ids: tuple[str, ...] = ()
    query: str | None = None

    def __post_init__(self) -> None:
        _require_text("article_id", self.article_id)
        _require_text("title", self.title)
        if not isinstance(self.body, str):
            raise ContractError("body must be a string")
        _require_unique_nonempty("topic_ids", self.topic_ids, allow_empty=True)
        if self.query is not None:
            _require_text("query", self.query)

    def field_text(self, evidence_field: EvidenceField) -> str:
        if evidence_field is EvidenceField.TITLE:
            return self.title
        return self.body


@dataclass(frozen=True, slots=True)
class EvidenceSpan:
    evidence_id: str
    article_id: str
    field: EvidenceField
    start: int
    end: int
    text: str

    def __post_init__(self) -> None:
        _require_text("evidence_id", self.evidence_id)
        _require_text("article_id", self.article_id)
        _require_text("evidence text", self.text)
        if self.start < 0:
            raise ContractError("evidence start must be >= 0")
        if self.end <= self.start:
            raise ContractError("evidence end must be greater than start")
        if self.end - self.start != len(self.text):
            raise ContractError("evidence offsets must match evidence text length")

    @classmethod
    def from_article(
        cls,
        *,
        evidence_id: str,
        article: RawArticle,
        field: EvidenceField,
        start: int,
        end: int,
    ) -> EvidenceSpan:
        source = article.field_text(field)
        if start < 0 or end > len(source) or end <= start:
            raise ContractError("evidence offsets are outside the source field")
        return cls(
            evidence_id=evidence_id,
            article_id=article.article_id,
            field=field,
            start=start,
            end=end,
            text=source[start:end],
        )

    def validate_against(self, article: RawArticle) -> None:
        if self.article_id != article.article_id:
            raise ContractError(f"{self.evidence_id}: evidence/article id mismatch")
        source = article.field_text(self.field)
        if self.end > len(source) or source[self.start : self.end] != self.text:
            raise ContractError(f"{self.evidence_id}: evidence no longer matches source text")


@dataclass(frozen=True, slots=True)
class EventFact:
    fact_id: str
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

    def __post_init__(self) -> None:
        _require_text("fact_id", self.fact_id)
        _require_text("subject", self.subject)
        _require_text("action", self.action)
        _require_unique_nonempty("evidence_ids", self.evidence_ids)
        _require_unique_nonempty("participants", self.participants, allow_empty=True)
        for name, value in (
            ("object", self.object),
            ("event_date", self.event_date),
            ("location", self.location),
            ("cause", self.cause),
        ):
            if value is not None:
                _require_text(name, value)


@dataclass(frozen=True, slots=True)
class CandidateEvent:
    event_id: str
    topic_id: str
    fact_ids: tuple[str, ...]
    article_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_text("event_id", self.event_id)
        _require_text("topic_id", self.topic_id)
        _require_unique_nonempty("fact_ids", self.fact_ids)
        _require_unique_nonempty("article_ids", self.article_ids)


@dataclass(frozen=True, slots=True)
class VerificationCheck:
    check_id: str
    verifier_id: str
    model_id: str
    evidence_ids: tuple[str, ...]
    entailed: bool | None
    error_code: str | None = None
    zero_cost: bool = True

    def __post_init__(self) -> None:
        _require_text("check_id", self.check_id)
        _require_text("verifier_id", self.verifier_id)
        _require_text("model_id", self.model_id)
        _require_unique_nonempty("evidence_ids", self.evidence_ids)
        if not self.zero_cost:
            raise ContractError("paid verification is forbidden by the zero-cost architecture")
        if self.entailed is None and self.error_code is None:
            raise ContractError("an inconclusive verification check must carry an error_code")
        if self.error_code is not None:
            _require_text("error_code", self.error_code)


@dataclass(frozen=True, slots=True)
class VerifiedClaim:
    claim_id: str
    event_id: str
    text: str
    evidence_ids: tuple[str, ...]
    checks: tuple[VerificationCheck, ...]
    verdict: VerificationVerdict

    def __post_init__(self) -> None:
        _require_text("claim_id", self.claim_id)
        _require_text("event_id", self.event_id)
        _require_text("claim text", self.text)
        _require_unique_nonempty("evidence_ids", self.evidence_ids)
        if not self.checks:
            raise ContractError("a verified claim must contain at least one verification check")
        check_ids = tuple(check.check_id for check in self.checks)
        _require_unique_nonempty("verification check ids", check_ids)
        decisions = [check.entailed for check in self.checks]
        if self.verdict is VerificationVerdict.SUPPORTED:
            if True not in decisions or False in decisions:
                raise ContractError("supported claim requires positive verification and no explicit rejection")
        if self.verdict is VerificationVerdict.REJECTED and False not in decisions:
            raise ContractError("rejected claim requires at least one explicit rejection")


@dataclass(frozen=True, slots=True)
class RenderedEntry:
    event_id: str
    headline: str
    summary: str
    claim_ids: tuple[str, ...]
    render_mode: RenderMode

    def __post_init__(self) -> None:
        _require_text("event_id", self.event_id)
        _require_text("headline", self.headline)
        _require_text("summary", self.summary)
        _require_unique_nonempty("claim_ids", self.claim_ids)


@dataclass(frozen=True, slots=True)
class RenderedBriefing:
    briefing_id: str
    generated_at: datetime
    entries: tuple[RenderedEntry, ...] = ()

    def __post_init__(self) -> None:
        _require_text("briefing_id", self.briefing_id)
        _require_aware("generated_at", self.generated_at)
        event_ids = tuple(entry.event_id for entry in self.entries)
        _require_unique_nonempty("rendered event ids", event_ids, allow_empty=True)


@dataclass(frozen=True, slots=True)
class ContractBundle:
    articles: tuple[RawArticle, ...] = field(default_factory=tuple)
    evidence: tuple[EvidenceSpan, ...] = field(default_factory=tuple)
    facts: tuple[EventFact, ...] = field(default_factory=tuple)
    events: tuple[CandidateEvent, ...] = field(default_factory=tuple)
    claims: tuple[VerifiedClaim, ...] = field(default_factory=tuple)
    briefing: RenderedBriefing | None = None

    def validate(self) -> None:
        articles = self._index("article", self.articles, "article_id")
        evidence = self._index("evidence", self.evidence, "evidence_id")
        facts = self._index("fact", self.facts, "fact_id")
        events = self._index("event", self.events, "event_id")
        claims = self._index("claim", self.claims, "claim_id")

        for span in self.evidence:
            article = articles.get(span.article_id)
            if article is None:
                raise ContractError(f"{span.evidence_id}: missing article {span.article_id}")
            span.validate_against(article)

        for fact in self.facts:
            for evidence_id in fact.evidence_ids:
                if evidence_id not in evidence:
                    raise ContractError(f"{fact.fact_id}: missing evidence {evidence_id}")

        for event in self.events:
            for article_id in event.article_ids:
                if article_id not in articles:
                    raise ContractError(f"{event.event_id}: missing article {article_id}")
            for fact_id in event.fact_ids:
                fact = facts.get(fact_id)
                if fact is None:
                    raise ContractError(f"{event.event_id}: missing fact {fact_id}")
                fact_article_ids = {evidence[evidence_id].article_id for evidence_id in fact.evidence_ids}
                if not fact_article_ids.issubset(set(event.article_ids)):
                    raise ContractError(
                        f"{event.event_id}: fact {fact_id} depends on article outside the event"
                    )

        for claim in self.claims:
            event = events.get(claim.event_id)
            if event is None:
                raise ContractError(f"{claim.claim_id}: missing event {claim.event_id}")
            for evidence_id in claim.evidence_ids:
                span = evidence.get(evidence_id)
                if span is None:
                    raise ContractError(f"{claim.claim_id}: missing evidence {evidence_id}")
                if span.article_id not in event.article_ids:
                    raise ContractError(
                        f"{claim.claim_id}: claim evidence comes from article outside the event"
                    )
            for check in claim.checks:
                for evidence_id in check.evidence_ids:
                    if evidence_id not in evidence:
                        raise ContractError(f"{check.check_id}: missing evidence {evidence_id}")

        if self.briefing is not None:
            for entry in self.briefing.entries:
                event = events.get(entry.event_id)
                if event is None:
                    raise ContractError(f"briefing entry references missing event {entry.event_id}")
                for claim_id in entry.claim_ids:
                    claim = claims.get(claim_id)
                    if claim is None:
                        raise ContractError(f"briefing entry references missing claim {claim_id}")
                    if claim.event_id != event.event_id:
                        raise ContractError(
                            f"briefing entry mixes claim {claim_id} from another event"
                        )
                    if claim.verdict is not VerificationVerdict.SUPPORTED:
                        raise ContractError(
                            f"briefing entry cannot publish non-supported claim {claim_id}"
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
