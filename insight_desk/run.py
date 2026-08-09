from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .collectors.cache import ResponseCache
from .collectors.collect import collect_news, collect_trends
from .collectors.enrichment import EnrichmentReport, MetadataEnricher
from .collectors.naver import NaverApiClient, NaverCredentials
from .config import load_topics
from .domain.models import CollectorStatus, RunState, RunStatus, to_jsonable
from .domain.status import is_publishable, resolve_status
from .pipeline.analysis import build_briefing, make_failure_state
from .pipeline.clustering import cluster_news
from .pipeline.deduplication import deduplicate_news
from .pipeline.normalization import normalize_news_payloads
from .pipeline.scoring import score_news
from .pipeline.novelty import load_previous_signatures
from .pipeline.selection import cap_topic_candidates, topic_diverse_enrichment_candidates
from .pipeline.trend_metrics import compute_trend_metrics, parse_trend_batches
from .security import assert_no_secret_values, redact_error
from .web.render import render_site
from .web.validate import validate_artifact

SEOUL = ZoneInfo("Asia/Seoul")
METADATA_ENRICHMENT_LIMIT = 5


def _empty_status() -> CollectorStatus:
    return CollectorStatus(attempted=0, succeeded=0, failed=0, partial=False, item_count=0)


def _write_state(path: Path, state: RunState, secrets: tuple[str, ...]) -> None:
    payload = to_jsonable(state)
    assert_no_secret_values(payload, secrets)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def _write_selection_audit(
    path: Path,
    *,
    audit: tuple[dict[str, object], ...],
    funnel: dict[str, dict[str, int]],
    selected_reviews: tuple[dict[str, object], ...],
    secrets: tuple[str, ...],
) -> None:
    payload = {
        "selection_audit": audit,
        "funnel": funnel,
        "selected_stories": selected_reviews,
    }
    assert_no_secret_values(payload, secrets)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
        bounded = cap_topic_candidates(scored, topics)
        enriched = bounded
        enrichment_report: EnrichmentReport | None = None
        transport = getattr(client, "transport", None)
        if transport is not None:
            metadata_cache_path = cache_path.with_name(
                f"{cache_path.stem}-metadata{cache_path.suffix or '.json'}"
            )
            enrichment_targets = topic_diverse_enrichment_candidates(
                bounded,
                topics,
                limit=METADATA_ENRICHMENT_LIMIT,
            )
            enriched_targets, enrichment_report = MetadataEnricher(
                transport=transport,
                cache=ResponseCache(metadata_cache_path),
            ).enrich(enrichment_targets, limit=METADATA_ENRICHMENT_LIMIT)
            by_evidence_id = {item.evidence_id: item for item in enriched_targets}
            enriched = tuple(by_evidence_id.get(item.evidence_id, item) for item in bounded)
        clusters = cluster_news(enriched)
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
            news=enriched,
            clusters=clusters,
            trend_metrics=metrics,
            generated_at=current,
            enrichment=enrichment_report,
            previous_signatures=load_previous_signatures(output_dir),
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
        _write_selection_audit(
            state_path.with_name("selection-audit.json"),
            audit=briefing.selection_audit,
            funnel=briefing.selection_funnel,
            selected_reviews=briefing.selected_reviews,
            secrets=secrets,
        )
        _write_selection_audit(
            state_path.with_name("live-acceptance.json"),
            audit=briefing.selection_audit,
            funnel=briefing.selection_funnel,
            selected_reviews=briefing.selected_reviews,
            secrets=secrets,
        )
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
