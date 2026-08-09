from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ..domain.models import CollectorStatus, KeywordGroup, Topic
from ..security import redact_text
from .naver import NaverApiClient, NaverApiError


@dataclass(frozen=True)
class NewsCollection:
    raw_items: tuple[tuple[str, str, str, dict[str, object]], ...]
    status: CollectorStatus


@dataclass(frozen=True)
class TrendCollection:
    raw_batches: tuple[tuple[str, tuple[KeywordGroup, ...], dict[str, object]], ...]
    status: CollectorStatus


def collect_news(client: NaverApiClient, topics: tuple[Topic, ...]) -> NewsCollection:
    """Retrieve a bounded, topic-fair union of relevance and freshness results.

    ``sim`` is the primary intent-retrieval channel and ``date`` is a bounded
    freshness channel.  A query/channel pair is fetched once even when several
    interests share it.  The per-query slice is capped before normalization so
    request volume cannot silently become editorial authority.
    """

    raw: list[tuple[str, str, str, dict[str, object]]] = []
    errors: list[str] = []
    attempted = 0
    succeeded = 0
    seen_payloads: dict[tuple[str, str], dict[str, object]] = {}
    enabled_topics = [topic for topic in topics if topic.enabled]
    allocations: dict[tuple[str, str], dict[str, int]] = {}
    for topic in enabled_topics:
        queries = topic.all_news_queries
        if not queries:
            continue
        per_query = max(5, (topic.candidate_budget + len(queries) - 1) // len(queries))
        sim_budget = max(1, (per_query * 3 + 4) // 5)
        date_budget = max(0, per_query - sim_budget)
        for query in queries:
            allocations[(topic.id, query)] = {"SIM": sim_budget, "DATE": date_budget}

    # The largest allocation wins for a shared query.  Each topic still gets
    # only its own slice below, so sharing never increases a topic's candidate
    # budget while it does prevent duplicate network calls.
    request_budget: dict[tuple[str, str], int] = {}
    for (topic_id, query), channels in allocations.items():
        for channel, budget in channels.items():
            if budget:
                request_budget[(query, channel)] = max(request_budget.get((query, channel), 0), budget)

    legacy_sort_client = False
    for topic in enabled_topics:
        for query in topic.all_news_queries:
            for channel in ("SIM", "DATE"):
                budget = allocations.get((topic.id, query), {}).get(channel, 0)
                if not budget:
                    continue
                key = (query, channel)
                payload = seen_payloads.get(key)
                if payload is None and legacy_sort_client and channel == "DATE":
                    payload = seen_payloads.get((query, "SIM"))
                if payload is None:
                    attempted += 1
                    try:
                        if legacy_sort_client:
                            payload = client.search_news(query, display=min(100, request_budget[key]))
                        else:
                            payload = client.search_news(
                                query,
                                display=min(100, request_budget[key]),
                                sort=channel.casefold(),
                            )
                        succeeded += 1
                        items = payload.get("items", [])
                        if isinstance(items, list):
                            payload = {**payload, "items": items[: request_budget[key]]}
                        seen_payloads[key] = payload
                    except TypeError as exc:
                        # Small isolated test transports from older package
                        # versions may not expose ``sort``.  Production's
                        # NaverApiClient always takes the explicit channel.
                        if "sort" not in str(exc):
                            raise
                        legacy_sort_client = True
                        try:
                            payload = client.search_news(
                                query,
                                display=min(100, request_budget[key]),
                            )
                            succeeded += 1
                            items = payload.get("items", [])
                            if isinstance(items, list):
                                payload = {**payload, "items": items[: request_budget[key]]}
                            seen_payloads[key] = payload
                        except NaverApiError as fallback_exc:
                            errors.append(
                                redact_text(
                                    f"{topic.name}/{query}/{channel}: {fallback_exc.kind} {fallback_exc}"
                                )
                            )
                            continue
                    except NaverApiError as exc:
                        errors.append(redact_text(f"{topic.name}/{query}/{channel}: {exc.kind} {exc}"))
                        continue
                items = payload.get("items", [])
                sliced = {**payload, "items": items[:budget]} if isinstance(items, list) else payload
                raw.append((topic.id, query, channel, sliced))
    failed = attempted - succeeded
    status = CollectorStatus(
        attempted=attempted,
        succeeded=succeeded,
        failed=failed,
        partial=failed > 0 and succeeded > 0,
        item_count=sum(
            len(payload.get("items", []))
            for _, _, _, payload in raw
            if isinstance(payload.get("items", []), list)
        ),
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
