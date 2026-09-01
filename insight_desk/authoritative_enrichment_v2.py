from __future__ import annotations

"""Authoritative-data enrichment for CanonicalEvent V2.

This module is the only production owner allowed to call ECOS, KOSIS, or OpenDART.
It never decides whether a news event is relevant or publishable and never rewrites the
news event from API data. Provider absence, quota errors, network errors, and empty official
results are item-local enrichment misses; the CanonicalEvent remains usable without them.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Protocol, cast
from urllib.parse import urlencode

from insight_desk.api import EcosClient, KosisClient, OpenDartClient
from insight_desk.core import AuthoritativeFact, CanonicalEvent, SourceDocument


ECOS_PUBLIC_URL = "https://ecos.bok.or.kr/"
KOSIS_PUBLIC_URL = "https://kosis.kr/statHtml/statHtml.do"
DART_PUBLIC_URL = "https://dart.fss.or.kr/dsaf001/main.do"
_DEFAULT_CONFIG = Path("config/authoritative_sources.json")


class EcosPort(Protocol):
    def statistic_search(
        self,
        *,
        stat_code: str,
        cycle: str,
        start_period: str,
        end_period: str,
        max_rows: int = 100,
        item_code: str | None = None,
    ) -> dict[str, object]: ...


class KosisPort(Protocol):
    def statistics(
        self,
        *,
        org_id: str,
        table_id: str,
        object_l1: str,
        item_id: str,
        period_type: str,
        max_periods: int,
        object_l2: str | None = None,
    ) -> object: ...


class OpenDartPort(Protocol):
    def list_filings(
        self,
        *,
        corp_code: str,
        begin_date: date,
        end_date: date,
        disclosure_type: str = "A",
        page_no: int = 1,
        page_count: int = 100,
    ) -> dict[str, object]: ...


def _stable_id(prefix: str, *parts: str) -> str:
    material = "\x1f".join(parts)
    return f"{prefix}-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]


def _text(value: object) -> str:
    return str(value or "").strip()


def _event_surface(event: CanonicalEvent) -> str:
    values = (
        event.actor,
        event.action,
        event.object or "",
        event.metric or "",
        event.attribution or "",
        *event.participants,
    )
    return " ".join(value for value in values if value).casefold()


def _anchor_date(event: CanonicalEvent, source: SourceDocument) -> date:
    if event.event_time:
        try:
            return date.fromisoformat(event.event_time[:10])
        except ValueError:
            pass
    if event.publication_time is not None:
        return event.publication_time.date()
    return source.fetched_at.date()


def _shift_month(anchor: date, delta: int) -> tuple[int, int]:
    index = anchor.year * 12 + (anchor.month - 1) + delta
    return index // 12, index % 12 + 1


def _ecos_period_window(anchor: date, cycle: str, count: int) -> tuple[str, str] | None:
    count = max(1, count)
    if cycle == "M":
        start_year, start_month = _shift_month(anchor, -(count - 1))
        return f"{start_year:04d}{start_month:02d}", f"{anchor.year:04d}{anchor.month:02d}"
    if cycle in {"A", "Y"}:
        return str(anchor.year - count + 1), str(anchor.year)
    if cycle == "D":
        start = anchor - timedelta(days=count - 1)
        return start.strftime("%Y%m%d"), anchor.strftime("%Y%m%d")
    return None


def _canonical_row_key(row: Mapping[str, object]) -> str:
    return json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _safe_int(value: object, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _keywords_match(surface: str, raw_keywords: object) -> bool:
    if not isinstance(raw_keywords, list):
        return False
    return any(
        keyword.casefold() in surface
        for raw in raw_keywords
        if (keyword := _text(raw))
    )


def _item_code_matches(row: Mapping[str, object], item_code: str) -> bool:
    item_fields = tuple(
        _text(row.get(name))
        for name in ("ITEM_CODE", "ITEM_CODE1", "ITEM_CODE2", "ITEM_CODE3", "ITEM_CODE4")
    )
    populated = tuple(value for value in item_fields if value)
    return not populated or item_code in populated


def _filing_tokens(report_name: str) -> tuple[str, ...]:
    compact = re.sub(r"[^0-9A-Za-z가-힣]+", " ", report_name)
    tokens: list[str] = []
    for raw in compact.split():
        token = raw
        for boilerplate in (
            "주요사항보고서",
            "사업보고서",
            "반기보고서",
            "분기보고서",
            "보고서",
            "결정",
            "공시",
        ):
            token = token.replace(boilerplate, "")
        token = token.strip()
        if len(token) >= 2:
            tokens.append(token.casefold())
    return tuple(dict.fromkeys(tokens))


def _filing_matches_event(report_name: str, surface: str) -> bool:
    tokens = _filing_tokens(report_name)
    if tokens and any(token in surface for token in tokens):
        return True
    normalized_report = re.sub(r"\s+", "", report_name).casefold()
    normalized_surface = re.sub(r"\s+", "", surface).casefold()
    return len(normalized_report) >= 4 and normalized_report in normalized_surface


@dataclass(slots=True)
class AuthoritativeEnricher:
    config: Mapping[str, object]
    ecos_client: EcosPort | None = None
    kosis_client: KosisPort | None = None
    opendart_client: OpenDartPort | None = None
    _cache: dict[tuple[str, ...], tuple[AuthoritativeFact, ...]] = field(
        default_factory=dict, init=False, repr=False
    )
    _stats: dict[str, dict[str, object]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.config, Mapping):
            raise ValueError("authoritative source config must be an object")
        self._stats = {
            "ecos": self._initial_stats(self.config.get("ecos"), self.ecos_client),
            "kosis": self._initial_stats(self.config.get("kosis"), self.kosis_client),
            "opendart": self._initial_stats(self.config.get("open_dart"), self.opendart_client),
        }

    @staticmethod
    def _initial_stats(raw_config: object, client: object | None) -> dict[str, object]:
        enabled = isinstance(raw_config, Mapping) and raw_config.get("enabled") is True
        return {
            "enabled": enabled,
            "configured": client is not None,
            "matched_events": 0,
            "calls": 0,
            "success": 0,
            "errors": 0,
            "error_kinds": {},
            "cache_hits": 0,
            "budget_skips": 0,
            "facts": 0,
        }

    @classmethod
    def from_environment(
        cls,
        *,
        config_path: Path = _DEFAULT_CONFIG,
    ) -> "AuthoritativeEnricher":
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("authoritative source config must be a JSON object")
        return cls(
            payload,
            ecos_client=EcosClient.from_environment(),
            kosis_client=KosisClient.from_environment(),
            opendart_client=OpenDartClient.from_environment(),
        )

    @property
    def audit_stats(self) -> dict[str, dict[str, object]]:
        snapshot: dict[str, dict[str, object]] = {}
        for provider, stats in self._stats.items():
            copied = dict(stats)
            copied["error_kinds"] = dict(cast(dict[str, int], stats["error_kinds"]))
            snapshot[provider] = copied
        return snapshot

    def enrich(
        self,
        event: CanonicalEvent,
        source: SourceDocument,
    ) -> tuple[AuthoritativeFact, ...]:
        """Return official facts relevant to an already-created CanonicalEvent.

        Routing uses only CanonicalEvent fields plus static config. The article body is not
        semantically re-read here. Provider failures are swallowed and represented in audit stats.
        """

        surface = _event_surface(event)
        anchor = _anchor_date(event, source)
        facts: list[AuthoritativeFact] = []
        facts.extend(self._enrich_ecos(surface=surface, anchor=anchor, source=source))
        facts.extend(self._enrich_kosis(surface=surface, source=source))
        facts.extend(
            self._enrich_opendart(
                event=event,
                surface=surface,
                anchor=anchor,
                source=source,
            )
        )
        unique: dict[str, AuthoritativeFact] = {}
        for fact in facts:
            unique[fact.fact_id] = fact
        return tuple(unique.values())

    def _provider_config(self, key: str) -> Mapping[str, object] | None:
        raw = self.config.get(key)
        return raw if isinstance(raw, Mapping) and raw.get("enabled") is True else None

    def _allowed_call(self, provider: str, config: Mapping[str, object]) -> bool:
        maximum = _safe_int(config.get("max_requests"), 1)
        stats = self._stats[provider]
        if int(stats["calls"]) >= maximum:
            stats["budget_skips"] = int(stats["budget_skips"]) + 1
            return False
        return True

    def _cached_or_call(
        self,
        provider: str,
        key: tuple[str, ...],
        config: Mapping[str, object],
        call,
    ) -> tuple[AuthoritativeFact, ...]:
        if key in self._cache:
            stats = self._stats[provider]
            stats["cache_hits"] = int(stats["cache_hits"]) + 1
            return self._cache[key]
        if not self._allowed_call(provider, config):
            return ()
        stats = self._stats[provider]
        stats["calls"] = int(stats["calls"]) + 1
        try:
            facts = tuple(call())
        except Exception as exc:
            stats["errors"] = int(stats["errors"]) + 1
            error_kinds = cast(dict[str, int], stats["error_kinds"])
            error_kind = type(exc).__name__
            error_kinds[error_kind] = int(error_kinds.get(error_kind, 0)) + 1
            self._cache[key] = ()
            return ()
        stats["success"] = int(stats["success"]) + 1
        stats["facts"] = int(stats["facts"]) + len(facts)
        self._cache[key] = facts
        return facts

    def _enrich_ecos(
        self,
        *,
        surface: str,
        anchor: date,
        source: SourceDocument,
    ) -> tuple[AuthoritativeFact, ...]:
        config = self._provider_config("ecos")
        if config is None or self.ecos_client is None:
            return ()
        raw_datasets = config.get("datasets")
        if not isinstance(raw_datasets, list):
            return ()
        output: list[AuthoritativeFact] = []
        for raw_dataset in raw_datasets:
            if not isinstance(raw_dataset, Mapping) or not _keywords_match(
                surface, raw_dataset.get("keywords")
            ):
                continue
            self._stats["ecos"]["matched_events"] = int(
                self._stats["ecos"]["matched_events"]
            ) + 1
            dataset_id = _text(raw_dataset.get("id"))
            stat_code = _text(raw_dataset.get("stat_code"))
            cycle = _text(raw_dataset.get("cycle"))
            item_code = _text(raw_dataset.get("item_code"))
            if not dataset_id or not stat_code or not cycle:
                continue
            periods = _ecos_period_window(
                anchor,
                cycle,
                _safe_int(raw_dataset.get("max_periods"), 2),
            )
            if periods is None:
                continue
            start_period, end_period = periods
            cache_key = (
                "ecos",
                dataset_id,
                start_period,
                end_period,
                item_code,
            )

            def call() -> tuple[AuthoritativeFact, ...]:
                payload = self.ecos_client.statistic_search(
                    stat_code=stat_code,
                    cycle=cycle,
                    start_period=start_period,
                    end_period=end_period,
                    max_rows=100,
                    item_code=item_code or None,
                )
                search = payload.get("StatisticSearch")
                rows = search.get("row") if isinstance(search, Mapping) else None
                if not isinstance(rows, list):
                    return ()
                candidates = [
                    row
                    for row in rows
                    if isinstance(row, Mapping)
                    and _text(row.get("DATA_VALUE"))
                    and (not item_code or _item_code_matches(row, item_code))
                ]
                if not candidates:
                    return ()
                latest_time = max(_text(row.get("TIME")) for row in candidates)
                latest_rows = [row for row in candidates if _text(row.get("TIME")) == latest_time]
                facts: list[AuthoritativeFact] = []
                for row in sorted(latest_rows, key=_canonical_row_key):
                    value = _text(row.get("DATA_VALUE"))
                    subject = _text(row.get("STAT_NAME")) or _text(raw_dataset.get("label"))
                    unit = _text(row.get("UNIT_NAME")) or _text(raw_dataset.get("expected_unit"))
                    fact_id = _stable_id(
                        "authoritative-ecos",
                        dataset_id,
                        latest_time,
                        value,
                        unit,
                    )
                    facts.append(
                        AuthoritativeFact(
                            fact_id=fact_id,
                            provider_id="ecos",
                            subject=subject or dataset_id,
                            predicate="공식 통계값",
                            value=value,
                            unit=unit or None,
                            effective_time=latest_time or None,
                            retrieved_at=source.fetched_at,
                            source_url=ECOS_PUBLIC_URL,
                        )
                    )
                return tuple(facts)

            output.extend(self._cached_or_call("ecos", cache_key, config, call))
        return tuple(output)

    def _enrich_kosis(
        self,
        *,
        surface: str,
        source: SourceDocument,
    ) -> tuple[AuthoritativeFact, ...]:
        config = self._provider_config("kosis")
        if config is None or self.kosis_client is None:
            return ()
        raw_datasets = config.get("datasets")
        if not isinstance(raw_datasets, list):
            return ()
        output: list[AuthoritativeFact] = []
        for raw_dataset in raw_datasets:
            if not isinstance(raw_dataset, Mapping) or not _keywords_match(
                surface, raw_dataset.get("keywords")
            ):
                continue
            self._stats["kosis"]["matched_events"] = int(
                self._stats["kosis"]["matched_events"]
            ) + 1
            dataset_id = _text(raw_dataset.get("id"))
            org_id = _text(raw_dataset.get("org_id"))
            table_id = _text(raw_dataset.get("tbl_id"))
            object_l1 = _text(raw_dataset.get("obj_l1"))
            item_id = _text(raw_dataset.get("itm_id"))
            period_type = _text(raw_dataset.get("prd_se"))
            if not all((dataset_id, org_id, table_id, object_l1, item_id, period_type)):
                continue
            max_periods = _safe_int(raw_dataset.get("max_periods"), 2)
            object_l2 = _text(raw_dataset.get("obj_l2")) or None
            cache_key = (
                "kosis",
                dataset_id,
                str(max_periods),
                object_l2 or "",
            )

            def call() -> tuple[AuthoritativeFact, ...]:
                payload = self.kosis_client.statistics(
                    org_id=org_id,
                    table_id=table_id,
                    object_l1=object_l1,
                    object_l2=object_l2,
                    item_id=item_id,
                    period_type=period_type,
                    max_periods=max_periods,
                )
                if isinstance(payload, list):
                    rows = [row for row in payload if isinstance(row, Mapping)]
                elif isinstance(payload, Mapping) and _text(payload.get("DT")):
                    rows = [payload]
                else:
                    raw_rows = payload.get("data") if isinstance(payload, Mapping) else None
                    rows = [row for row in raw_rows if isinstance(row, Mapping)] if isinstance(raw_rows, list) else []
                candidates = [row for row in rows if _text(row.get("DT"))]
                if not candidates:
                    return ()
                latest_period = max(_text(row.get("PRD_DE")) for row in candidates)
                if latest_period:
                    candidates = [row for row in candidates if _text(row.get("PRD_DE")) == latest_period]
                public_url = KOSIS_PUBLIC_URL + "?" + urlencode(
                    {"orgId": org_id, "tblId": table_id}
                )
                facts: list[AuthoritativeFact] = []
                for row in sorted(candidates, key=_canonical_row_key):
                    value = _text(row.get("DT"))
                    item_name = _text(row.get("ITM_NM")) or _text(raw_dataset.get("label"))
                    dimension = _text(row.get("C1_NM"))
                    subject = " · ".join(part for part in (item_name, dimension) if part)
                    unit = _text(row.get("UNIT_NM")) or _text(raw_dataset.get("expected_unit"))
                    fact_id = _stable_id(
                        "authoritative-kosis",
                        dataset_id,
                        latest_period,
                        subject,
                        value,
                        unit,
                    )
                    facts.append(
                        AuthoritativeFact(
                            fact_id=fact_id,
                            provider_id="kosis",
                            subject=subject or dataset_id,
                            predicate="공식 통계값",
                            value=value,
                            unit=unit or None,
                            effective_time=latest_period or None,
                            retrieved_at=source.fetched_at,
                            source_url=public_url,
                        )
                    )
                return tuple(facts)

            output.extend(self._cached_or_call("kosis", cache_key, config, call))
        return tuple(output)

    def _enrich_opendart(
        self,
        *,
        event: CanonicalEvent,
        surface: str,
        anchor: date,
        source: SourceDocument,
    ) -> tuple[AuthoritativeFact, ...]:
        config = self._provider_config("open_dart")
        if config is None or self.opendart_client is None:
            return ()
        raw_entities = config.get("entities")
        if not isinstance(raw_entities, list):
            return ()
        output: list[AuthoritativeFact] = []
        for raw_entity in raw_entities:
            if not isinstance(raw_entity, Mapping):
                continue
            raw_topics = raw_entity.get("topic_ids")
            if isinstance(raw_topics, list) and raw_topics and event.topic not in {
                _text(topic) for topic in raw_topics
            }:
                continue
            aliases = raw_entity.get("aliases")
            if not isinstance(aliases, list) or not any(
                alias.casefold() in surface
                for raw in aliases
                if (alias := _text(raw))
            ):
                continue
            self._stats["opendart"]["matched_events"] = int(
                self._stats["opendart"]["matched_events"]
            ) + 1
            entity_id = _text(raw_entity.get("id"))
            corp_code = _text(raw_entity.get("corp_code"))
            if not entity_id or not corp_code:
                continue
            lookback_days = _safe_int(config.get("lookback_days"), 7)
            begin = anchor - timedelta(days=lookback_days)
            disclosure_type = _text(config.get("disclosure_type")) or "A"
            page_count = _safe_int(config.get("page_count"), 50)
            cache_key = (
                "opendart",
                entity_id,
                begin.isoformat(),
                anchor.isoformat(),
                disclosure_type,
            )

            def call() -> tuple[AuthoritativeFact, ...]:
                payload = self.opendart_client.list_filings(
                    corp_code=corp_code,
                    begin_date=begin,
                    end_date=anchor,
                    disclosure_type=disclosure_type,
                    page_no=1,
                    page_count=page_count,
                )
                raw_rows = payload.get("list")
                rows = raw_rows if isinstance(raw_rows, list) else []
                facts: list[AuthoritativeFact] = []
                for raw_row in rows:
                    if not isinstance(raw_row, Mapping):
                        continue
                    report_name = _text(raw_row.get("report_nm"))
                    receipt = _text(raw_row.get("rcept_no"))
                    if not report_name or not receipt or not _filing_matches_event(report_name, surface):
                        continue
                    corp_name = _text(raw_row.get("corp_name")) or entity_id
                    receipt_date = _text(raw_row.get("rcept_dt"))
                    public_url = DART_PUBLIC_URL + "?" + urlencode({"rcpNo": receipt})
                    fact_id = _stable_id(
                        "authoritative-opendart",
                        corp_code,
                        receipt,
                        report_name,
                    )
                    facts.append(
                        AuthoritativeFact(
                            fact_id=fact_id,
                            provider_id="opendart",
                            subject=corp_name,
                            predicate="공시",
                            value=report_name,
                            effective_time=receipt_date or None,
                            retrieved_at=source.fetched_at,
                            source_url=public_url,
                        )
                    )
                return tuple(facts)

            output.extend(self._cached_or_call("opendart", cache_key, config, call))
        return tuple(output)
