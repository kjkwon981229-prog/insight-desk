from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

from insight_desk.core import RawArticle, SourceProvenance

DART_PUBLIC_BASE = "https://dart.fss.or.kr/dsaf001/main.do"
KOSIS_PUBLIC_BASE = "https://kosis.kr/statHtml/statHtml.do"
ECOS_PUBLIC_BASE = "https://ecos.bok.or.kr/"


def _require_aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _require_text(name: str, value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{name} must be non-empty")
    return stripped


def _canonical_json(payload: object) -> str:
    if not isinstance(payload, (dict, list)):
        raise ValueError("official API payload must be a JSON object or array")
    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        separators=(",", ": "),
    )
    if not rendered.strip():
        raise ValueError("official API payload must not be empty")
    return rendered


def _stable_id(prefix: str, *parts: str) -> str:
    material = "\x1f".join(parts)
    return f"{prefix}-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]


def _safe_topics(topic_ids: tuple[str, ...]) -> tuple[str, ...]:
    if not topic_ids:
        raise ValueError("topic_ids must not be empty")
    if any(not value.strip() for value in topic_ids):
        raise ValueError("topic_ids must contain non-empty values")
    if len(set(topic_ids)) != len(topic_ids):
        raise ValueError("topic_ids must be unique")
    return topic_ids


def normalize_opendart_filings(
    payload: dict[str, object],
    *,
    fetched_at: datetime,
    corp_code: str,
    topic_ids: tuple[str, ...],
    query: str,
) -> tuple[RawArticle, ...]:
    """Convert OpenDART filing rows into evidence-ready documents without credential URLs."""

    _require_aware("fetched_at", fetched_at)
    corp_code = _require_text("corp_code", corp_code)
    query = _require_text("query", query)
    topics = _safe_topics(topic_ids)
    raw_rows = payload.get("list", [])
    if raw_rows is None:
        raw_rows = []
    if not isinstance(raw_rows, list):
        raise ValueError("OpenDART list must be an array")

    articles: list[RawArticle] = []
    seen_receipts: set[str] = set()
    for raw in raw_rows:
        if not isinstance(raw, dict):
            continue
        row: dict[str, Any] = raw
        receipt = str(row.get("rcept_no") or "").strip()
        report_name = str(row.get("report_nm") or "").strip()
        corp_name = str(row.get("corp_name") or "").strip()
        if not receipt or not report_name or receipt in seen_receipts:
            continue
        public_url = f"{DART_PUBLIC_BASE}?{urlencode({'rcpNo': receipt})}"
        title = f"{corp_name} · {report_name}" if corp_name else report_name
        body = _canonical_json(row)
        articles.append(
            RawArticle(
                article_id=_stable_id("dart", receipt),
                provenance=SourceProvenance(
                    source_id="official:opendart",
                    source_name="금융감독원 전자공시시스템 DART",
                    url=public_url,
                    retrieved_via="opendart_api",
                    fetched_at=fetched_at,
                    published_at=None,
                ),
                title=title,
                body=body,
                topic_ids=topics,
                query=query,
            )
        )
        seen_receipts.add(receipt)
    return tuple(articles)


def normalize_kosis_statistics(
    payload: object,
    *,
    fetched_at: datetime,
    org_id: str,
    table_id: str,
    topic_ids: tuple[str, ...],
    query: str,
) -> RawArticle:
    """Represent decoded KOSIS structured data as deterministic evidence text."""

    _require_aware("fetched_at", fetched_at)
    org_id = _require_text("org_id", org_id)
    table_id = _require_text("table_id", table_id)
    query = _require_text("query", query)
    topics = _safe_topics(topic_ids)
    body = _canonical_json(payload)
    public_url = f"{KOSIS_PUBLIC_BASE}?{urlencode({'orgId': org_id, 'tblId': table_id})}"
    return RawArticle(
        article_id=_stable_id("kosis", org_id, table_id, hashlib.sha256(body.encode("utf-8")).hexdigest()),
        provenance=SourceProvenance(
            source_id=f"official:kosis:{org_id}:{table_id}",
            source_name="KOSIS 국가통계포털",
            url=public_url,
            retrieved_via="kosis_api",
            fetched_at=fetched_at,
            published_at=None,
        ),
        title=f"KOSIS {org_id}/{table_id}",
        body=body,
        topic_ids=topics,
        query=query,
    )


def normalize_ecos_statistics(
    payload: dict[str, object],
    *,
    fetched_at: datetime,
    stat_code: str,
    cycle: str,
    start_period: str,
    end_period: str,
    topic_ids: tuple[str, ...],
    query: str,
) -> RawArticle:
    """Represent decoded ECOS structured data without persisting its credential-bearing API URL."""

    _require_aware("fetched_at", fetched_at)
    stat_code = _require_text("stat_code", stat_code)
    cycle = _require_text("cycle", cycle)
    start_period = _require_text("start_period", start_period)
    end_period = _require_text("end_period", end_period)
    query = _require_text("query", query)
    topics = _safe_topics(topic_ids)
    body = _canonical_json(payload)
    return RawArticle(
        article_id=_stable_id(
            "ecos",
            stat_code,
            cycle,
            start_period,
            end_period,
            hashlib.sha256(body.encode("utf-8")).hexdigest(),
        ),
        provenance=SourceProvenance(
            source_id=f"official:ecos:{stat_code}",
            source_name="한국은행 경제통계시스템 ECOS",
            url=ECOS_PUBLIC_BASE,
            retrieved_via="ecos_api",
            fetched_at=fetched_at,
            published_at=None,
        ),
        title=f"ECOS {stat_code} · {start_period}–{end_period}",
        body=body,
        topic_ids=topics,
        query=query,
    )
