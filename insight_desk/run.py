from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .collectors.cache import ResponseCache
from .collectors.collect import collect_news, collect_trends
from .collectors.naver import NaverApiClient, NaverCredentials
from .config import load_topics
from .domain.models import CollectorStatus, RunState, RunStatus, to_jsonable
from .domain.status import is_publishable, resolve_status
from .pipeline.analysis import build_briefing, make_failure_state
from .pipeline.clustering import cluster_news
from .pipeline.deduplication import deduplicate_news
from .pipeline.normalization import normalize_news_payloads
from .pipeline.scoring import score_news
from .pipeline.trend_metrics import compute_trend_metrics, parse_trend_batches
from .security import assert_no_secret_values, redact_error
from .web.render import render_site
from .web.validate import validate_artifact

SEOUL = ZoneInfo("Asia/Seoul")


def _empty_status() -> CollectorStatus:
    return CollectorStatus(attempted=0, succeeded=0, failed=0, partial=False, item_count=0)


def _write_state(path: Path, state: RunState, secrets: tuple[str, ...]) -> None:
    payload = to_jsonable(state)
    assert_no_secret_values(payload, secrets)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def execute(
    *,
    config_path: Path,
    output_dir: Path,
    state_path: Path,
    cache_path: Path,
    now: datetime | None = None,
    client: NaverApiClient | None = None,
    source_mode: str = "live",
) -> RunState:
    current = (now or datetime.now(SEOUL)).astimezone(SEOUL)
    generated_at = current.isoformat(timespec="seconds")
    cutoff = (current - timedelta(days=30)).date().isoformat()
    topics, groups = load_topics(config_path)
    secrets = tuple(value for value in (getattr(client, "credentials", None) and (client.credentials.client_id, client.credentials.client_secret)) or ())

    if client is None:
        credentials = NaverCredentials.from_environment()
        if credentials is None:
            state = make_failure_state(
                status=RunStatus.TOTAL_FAILURE,
                generated_at=generated_at,
                data_cutoff=cutoff,
                source_mode=source_mode,
                news=_empty_status(),
                trends=_empty_status(),
                errors=("NCP_CLIENT_ID 또는 NCP_CLIENT_SECRET이 없어 새 데이터를 수집하지 않았다.",),
            )
            _write_state(state_path, state, ())
            return state
        client = NaverApiClient(credentials, cache=ResponseCache(cache_path))
        secrets = (credentials.client_id, credentials.client_secret)

    try:
        news_collection = collect_news(client, topics)
        trend_collection = collect_trends(
            client,
            groups,
            start_date=current.date() - timedelta(days=30),
            end_date=current.date(),
        )
        initial_status = resolve_status(news_collection.status, trend_collection.status)
        warnings = tuple(news_collection.status.errors + trend_collection.status.errors)
        normalized = normalize_news_payloads(news_collection.raw_items)
        deduplicated = deduplicate_news(normalized)
        scored = score_news(deduplicated, topics, now=current)
        clusters = cluster_news(scored)
        points = parse_trend_batches(trend_collection.raw_batches)
        metrics = compute_trend_metrics(points)
        state = RunState(
            status=initial_status,
            publish=is_publishable(initial_status),
            generated_at=generated_at,
            data_cutoff=cutoff,
            source_mode=source_mode,
            news=news_collection.status,
            trends=trend_collection.status,
            warnings=warnings,
            errors=(),
        )
        if not state.publish:
            _write_state(state_path, state, secrets)
            return state

        briefing = build_briefing(
            state=state,
            topics=topics,
            news=scored,
            clusters=clusters,
            trend_metrics=metrics,
            generated_at=current,
        )
        try:
            render_site(briefing, output_dir)
        except Exception as exc:  # noqa: BLE001 - boundary converts to explicit state
            failure = replace(
                state,
                status=resolve_status(news_collection.status, trend_collection.status, render_ok=False),
                publish=False,
                render_errors=(redact_error(exc, secrets),),
            )
            _write_state(state_path, failure, secrets)
            return failure
        validation_errors = validate_artifact(output_dir, secrets=secrets)
        if validation_errors:
            failure = replace(
                state,
                status=resolve_status(news_collection.status, trend_collection.status, validation_ok=False),
                publish=False,
                render_errors=tuple(validation_errors),
            )
            _write_state(state_path, failure, secrets)
            return failure
        _write_state(state_path, state, secrets)
        return state
    except Exception as exc:  # noqa: BLE001 - the workflow receives a sanitized failure state
        failure = make_failure_state(
            status=RunStatus.TOTAL_FAILURE,
            generated_at=generated_at,
            data_cutoff=cutoff,
            source_mode=source_mode,
            news=_empty_status(),
            trends=_empty_status(),
            errors=(redact_error(exc, secrets),),
        )
        _write_state(state_path, failure, secrets)
        return failure
