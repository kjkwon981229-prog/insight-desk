from __future__ import annotations

import json
import os
from urllib.parse import urlparse

from insight_desk.acquisition import (
    AcquisitionError,
    AcquisitionPipeline,
    ArticleCandidate,
    PlaywrightHtmlRenderer,
    TrafilaturaExtractor,
    UrlLibHtmlFetcher,
    normalize_naver_items,
)
from insight_desk.api import NaverApiClient
from insight_desk.api.naver import NaverCredentials

QUERY = "인공지능"
TOPIC_ID = "ai_tech"
MAX_ATTEMPTS = 5


def _alternate_candidate(raw: dict[str, object], original: ArticleCandidate) -> ArticleCandidate | None:
    link = str(raw.get("link") or "").strip()
    if not link or link == original.url:
        return None
    parsed = urlparse(link)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return ArticleCandidate(
        candidate_id=original.candidate_id + "-alt",
        url=link,
        search_title=original.search_title,
        source_name=(parsed.hostname or parsed.netloc).lower(),
        published_at=original.published_at,
        topic_ids=original.topic_ids,
        query=original.query,
        retrieved_via="naver_search_alternate_link",
    )


def main() -> None:
    credentials = NaverCredentials.from_environment()
    if credentials is None:
        raise RuntimeError("NAVER credentials unavailable: NCP_CLIENT_ID/NCP_CLIENT_SECRET")

    client = NaverApiClient(credentials)
    payload = client.search_news(QUERY, display=10, start=1, sort="date")
    candidates = normalize_naver_items(payload, topic_id=TOPIC_ID, query=QUERY)
    if not candidates:
        raise AssertionError("NAVER returned no normalizable article candidates")

    raw_items = payload.get("items", [])
    raw_by_original: dict[str, dict[str, object]] = {}
    if isinstance(raw_items, list):
        for raw in raw_items:
            if isinstance(raw, dict):
                original = str(raw.get("originallink") or raw.get("link") or "").strip()
                if original:
                    raw_by_original[original] = raw

    pipeline = AcquisitionPipeline(
        fetcher=UrlLibHtmlFetcher(timeout=15),
        primary_extractor=TrafilaturaExtractor(),
        fallback_renderer=PlaywrightHtmlRenderer(timeout_ms=20_000),
    )

    attempts: list[dict[str, object]] = []
    success: dict[str, object] | None = None

    for candidate in candidates[:MAX_ATTEMPTS]:
        queue = [candidate]
        raw = raw_by_original.get(candidate.url)
        if raw is not None:
            alternate = _alternate_candidate(raw, candidate)
            if alternate is not None:
                queue.append(alternate)

        for current in queue:
            domain = (urlparse(current.url).hostname or "unknown").lower()
            try:
                result = pipeline.acquire(current)
            except AcquisitionError as exc:
                attempts.append(
                    {
                        "domain": domain,
                        "route": current.retrieved_via,
                        "status": "failed",
                        "failure_kind": exc.failure_kind.value,
                        "detail": exc.detail[:160],
                    }
                )
                continue

            success = {
                "domain": domain,
                "route": current.retrieved_via,
                "method": result.extraction_method,
                "fallback_used": result.fallback_used,
                "non_whitespace_chars": result.quality.character_count,
                "published_at_present": result.article.provenance.published_at is not None,
                "source_html_sha256_present": len(result.source_html_sha256) == 64,
            }
            attempts.append({**success, "status": "pass"})
            break
        if success is not None:
            break

    report = {
        "status": "pass" if success is not None else "fail",
        "query": QUERY,
        "topic_id": TOPIC_ID,
        "candidate_count": len(candidates),
        "attempts": attempts,
        "success": success,
        "secrets_logged": False,
        "article_body_logged": False,
    }
    print("PHASE5_LIVE_ACQUISITION_CANARY")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if success is None:
        raise AssertionError("no live article could be acquired within bounded attempts")


if __name__ == "__main__":
    main()
