from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from ..domain.models import CollectorStatus, KeywordGroup, Topic
from ..security import redact_text
from .naver import NaverApiClient, NaverApiError


@dataclass(frozen=True)
class NewsCollection:
    raw_items: tuple[tuple[str, str, dict[str, object]], ...]
    status: CollectorStatus


@dataclass(frozen=True)
class TrendCollection:
    raw_batches: tuple[tuple[str, tuple[KeywordGroup, ...], dict[str, object]], ...]
    status: CollectorStatus


def collect_news(client: NaverApiClient, topics: tuple[Topic, ...]) -> NewsCollection:
    raw: list[tuple[str, str, dict[str, object]]] = []
    errors: list[str] = []
    attempted = 0
    succeeded = 0
    seen_queries: set[str] = set()
    enabled_topics = [topic for topic in topics if topic.enabled]
    for topic in enabled_topics:
        for query in topic.news_queries:
            if query in seen_queries:
                continue
            seen_queries.add(query)
            attempted += 1
            try:
                payload = client.search_news(query)
                succeeded += 1
                raw.append((topic.id, query, payload))
            except NaverApiError as exc:
                errors.append(redact_text(f"{topic.name}/{query}: {exc.kind} {exc}"))
    failed = attempted - succeeded
    status = CollectorStatus(
        attempted=attempted,
        succeeded=succeeded,
        failed=failed,
        partial=failed > 0 and succeeded > 0,
        item_count=sum(len(payload.get("items", [])) for _, _, payload in raw if isinstance(payload.get("items", []), list)),
        errors=tuple(errors[:20]),
    )
    return NewsCollection(raw_items=tuple(raw), status=status)


def chunked(values: list[KeywordGroup], size: int) -> list[list[KeywordGroup]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def collect_trends(
    client: NaverApiClient,
    groups: tuple[KeywordGroup, ...],
    *,
    start_date: date,
    end_date: date,
) -> TrendCollection:
    active = [group for group in groups if group.enabled]
    batches: list[tuple[str, tuple[KeywordGroup, ...], dict[str, object]]] = []
    errors: list[str] = []
    attempted = 0
    succeeded = 0
    for batch in chunked(active, 5):
        attempted += 1
        try:
            batch_id, payload = client.search_trend(
                batch, start_date=start_date, end_date=end_date, time_unit="date"
            )
            succeeded += 1
            batches.append((batch_id, tuple(batch), payload))
        except NaverApiError as exc:
            errors.append(redact_text(f"trend batch {attempted}: {exc.kind} {exc}"))
    status = CollectorStatus(
        attempted=attempted,
        succeeded=succeeded,
        failed=attempted - succeeded,
        partial=attempted > 0 and 0 < succeeded < attempted,
        item_count=sum(
            len(result.get("data", []))
            for _, _, payload in batches
            for result in payload.get("results", [])
            if isinstance(result, dict) and isinstance(result.get("data", []), list)
        ),
        errors=tuple(errors[:20]),
    )
    return TrendCollection(raw_batches=tuple(batches), status=status)
