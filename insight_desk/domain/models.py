from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class RunStatus(str, Enum):
    COMPLETE = "COMPLETE"
    NEWS_ONLY = "NEWS_ONLY"
    TRENDS_ONLY = "TRENDS_ONLY"
    PARTIAL = "PARTIAL"
    TOTAL_FAILURE = "TOTAL_FAILURE"
    RENDER_FAILURE = "RENDER_FAILURE"
    VALIDATION_FAILURE = "VALIDATION_FAILURE"


class Certainty(str, Enum):
    CONFIRMED = "confirmed"
    INFERENCE = "inference"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class Topic:
    id: str
    name: str
    enabled: bool
    conditional: bool
    priority: int
    news_queries: tuple[str, ...]


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


@dataclass(frozen=True)
class TrendPoint:
    group_id: str
    group_name: str
    topic_id: str
    period: str
    ratio: float
    batch_id: str


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
