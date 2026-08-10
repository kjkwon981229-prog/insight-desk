from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class RunStatus(str, Enum):
    COMPLETE = "COMPLETE"
    VALID_EMPTY_DAY = "VALID_EMPTY_DAY"
    NEWS_ONLY = "NEWS_ONLY"
    TRENDS_ONLY = "TRENDS_ONLY"
    PARTIAL = "PARTIAL"
    TOTAL_FAILURE = "TOTAL_FAILURE"
    RENDER_FAILURE = "RENDER_FAILURE"
    VALIDATION_FAILURE = "VALIDATION_FAILURE"
    FILTER_COLLAPSE = "FILTER_COLLAPSE"


class Certainty(str, Enum):
    CONFIRMED = "confirmed"
    SUPPORTED_SINGLE_SOURCE = "supported_single_source"
    INFERENCE = "inference"
    UNCERTAIN = "uncertain"


class EvidenceType(str, Enum):
    SEARCH_SNIPPET = "SEARCH_SNIPPET"
    ENRICHED_METADATA = "ENRICHED_METADATA"
    OFFICIAL_SOURCE = "OFFICIAL_SOURCE"


class AuthoritySourceType(str, Enum):
    """Public authority class of an optional verification source."""

    OFFICIAL_PRIMARY = "OFFICIAL_PRIMARY"
    OFFICIAL_STATISTICAL = "OFFICIAL_STATISTICAL"
    OFFICIAL_CORPORATE = "OFFICIAL_CORPORATE"
    OFFICIAL_GOVERNMENT = "OFFICIAL_GOVERNMENT"
    OFFICIAL_SPORTS = "OFFICIAL_SPORTS"


@dataclass(frozen=True)
class AuthorityEvidence:
    """Normalized, non-secret facts returned by an authoritative adapter.

    The object is kept on the internal candidate.  The renderer uses an
    explicit whitelist and does not serialize this object to the public
    payload.
    """

    adapter: str
    source_type: AuthoritySourceType
    authority_strength: str = "HIGH"
    title: str = ""
    description: str = ""
    canonical_url: str = ""
    publisher: str = ""
    published_at: str | None = None
    event_key: str = ""
    fact_values: tuple[str, ...] = field(default_factory=tuple)
    unit: str = ""
    period: str = ""
    revision_date: str = ""


@dataclass(frozen=True)
class Topic:
    id: str
    name: str
    enabled: bool
    conditional: bool
    priority: int
    news_queries: tuple[str, ...]
    query_families: tuple[tuple[str, ...], ...] = field(default_factory=tuple)
    candidate_budget: int = 40
    selection_cap: int = 3
    intent_anchors: tuple[str, ...] = field(default_factory=tuple)
    negative_context: tuple[str, ...] = field(default_factory=tuple)
    event_terms: tuple[str, ...] = field(default_factory=tuple)
    required_intent_terms: tuple[str, ...] = field(default_factory=tuple)

    @property
    def all_news_queries(self) -> tuple[str, ...]:
        """Return the configured query family without duplicate requests."""

        values = self.news_queries
        for family in self.query_families:
            values += tuple(family)
        return tuple(dict.fromkeys(query for query in values if query.strip()))


@dataclass(frozen=True)
class KeywordGroup:
    id: str
    topic_id: str
    name: str
    keywords: tuple[str, ...]
    enabled: bool = True


@dataclass(frozen=True)
class NewsItem:
    evidence_id: str
    topic_id: str
    query: str
    title: str
    summary: str
    original_url: str
    naver_url: str
    canonical_url: str
    published_at: str | None
    source_domain: str
    content_hash: str
    score: float = 0.0
    metadata_title: str = ""
    metadata_description: str = ""
    metadata_canonical_url: str = ""
    publisher: str = ""
    metadata_published_at: str | None = None
    metadata_modified_at: str | None = None
    provenance: tuple[EvidenceType, ...] = field(default_factory=lambda: (EvidenceType.SEARCH_SNIPPET,))
    matched_topic_ids: tuple[str, ...] = field(default_factory=tuple)
    retrieval_channels: tuple[str, ...] = field(default_factory=tuple)
    # Every query that contributed this normalized item. ``matched_topic_ids``
    # is semantic attribution; this field preserves raw retrieval provenance
    # across cross-query/cross-topic deduplication.
    retrieval_queries: tuple[str, ...] = field(default_factory=tuple)
    authoritative_evidence: tuple[AuthorityEvidence, ...] = field(default_factory=tuple)
    authority_conflict: str = "NO_CONFLICT"


@dataclass(frozen=True)
class TrendPoint:
    group_id: str
    group_name: str
    topic_id: str
    period: str
    ratio: float
    batch_id: str
    aliases: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class TrendMetric:
    group_id: str
    group_name: str
    topic_id: str
    batch_id: str
    current_ratio: float | None
    previous_ratio: float | None
    moving_average: float | None
    delta: float | None
    change_percent: float | None
    spike_score: float | None
    interpretation: str
    points: tuple[TrendPoint, ...] = field(default_factory=tuple)
    state: str = "INSUFFICIENT_COMPARISON"
    aliases: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class StoryFacts:
    """Deterministic facts extracted from a story cluster.

    These are observations available in the search evidence, not generated
    claims. Empty fields mean the source set did not support that fact.
    """

    subject: str = ""
    action: str = ""
    object: str = ""
    event_type: str = "OTHER"
    date: str = ""
    time: str = ""
    location: str = ""
    key_numbers: tuple[str, ...] = field(default_factory=tuple)
    key_changes: tuple[str, ...] = field(default_factory=tuple)
    official_source: str = ""
    source_count: int = 0
    source_diversity: int = 0
    repeated_facts: tuple[str, ...] = field(default_factory=tuple)
    unique_facts: tuple[str, ...] = field(default_factory=tuple)
    trend_state: str = "비교 부족"
    next_known_event: str = ""
    uncertainty: str = ""
    event_signature: str = ""
    conflict_state: str = "NO_CONFLICT"
    temporal_state: str = ""


@dataclass(frozen=True)
class Story:
    topic_id: str
    topic_name: str
    title: str
    summary: str
    why_it_matters: str
    trend_relationship: str
    industry_impact: str
    investment_relevance: str
    watch_next: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    certainty: Certainty
    score: float
    source_count: int
    provenance: tuple[EvidenceType, ...] = field(default_factory=tuple)
    metadata_enriched_count: int = 0
    facts: StoryFacts = field(default_factory=StoryFacts)
    matched_topic_ids: tuple[str, ...] = field(default_factory=tuple)
    novelty: str = "UNKNOWN_HISTORY"
    why_selected: tuple[str, ...] = field(default_factory=tuple)
    intent_relevance: float = 0.0
    event_significance: float = 0.0
    evidence_strength: float = 0.0
    information_completeness: float = 0.0
    editorial_score: float = 0.0
    event_signature: str = ""


@dataclass(frozen=True)
class CollectorStatus:
    attempted: int
    succeeded: int
    failed: int
    partial: bool
    item_count: int
    errors: tuple[str, ...] = field(default_factory=tuple)

    @property
    def success(self) -> bool:
        return self.succeeded > 0


@dataclass(frozen=True)
class RunState:
    status: RunStatus
    publish: bool
    generated_at: str
    data_cutoff: str
    source_mode: str
    news: CollectorStatus
    trends: CollectorStatus
    warnings: tuple[str, ...] = field(default_factory=tuple)
    errors: tuple[str, ...] = field(default_factory=tuple)
    render_errors: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Briefing:
    state: RunState
    topics: tuple[Topic, ...]
    three_line_summary: tuple[str, ...]
    stories: tuple[Story, ...]
    news: tuple[NewsItem, ...]
    trend_metrics: tuple[TrendMetric, ...]
    limitations: tuple[str, ...]
    enrichment_attempted: int = 0
    enrichment_succeeded: int = 0
    enrichment_failed: int = 0
    selection_audit: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    selection_funnel: dict[str, dict[str, int]] = field(default_factory=dict)
    selected_reviews: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    authoritative_audit: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    editorial_health: str = "OK"
    strong_rejected_candidates: int = 0


def _enum_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_enum_value(item) for item in value]
    if isinstance(value, list):
        return [_enum_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _enum_value(item) for key, item in value.items()}
    return value


def to_jsonable(value: Any) -> Any:
    """Convert domain dataclasses to JSON-safe primitives without secrets."""

    if hasattr(value, "__dataclass_fields__"):
        return _enum_value(asdict(value))
    return _enum_value(value)
