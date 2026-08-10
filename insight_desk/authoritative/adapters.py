from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from ..collectors.transport import HttpResponse, Transport, UrlLibTransport
from ..domain.models import AuthorityEvidence, AuthoritySourceType, NewsItem
from .config import KosisDataset, OpenDartConfig, OpenDartEntity


_DART_URL = "https://opendart.fss.or.kr/api/list.json"
_KOSIS_URL = "https://kosis.kr/openapi/statisticsParameterData.do"
_TRUNCATION_RE = re.compile(r"\.{2,}|…")
_DART_ROUTINE_MARKERS = (
    "사업보고서",
    "반기보고서",
    "분기보고서",
    "감사보고서",
    "주주총회소집",
)
_DART_EVENT_MARKERS = (
    "주요사항",
    "영업실적",
    "매출",
    "영업이익",
    "계약",
    "인수",
    "합병",
    "투자",
    "유상증자",
    "자기주식",
    "배당",
    "공급",
    "소송",
    "공시",
)


@dataclass(frozen=True)
class AdapterResult:
    adapter: str
    attempted: int = 0
    success: bool = False
    failure_reason: str = ""
    candidates_matched: int = 0
    events_augmented: int = 0
    official_facts_added: int = 0
    conflicts_found: int = 0
    stories_affected: int = 0

    def to_audit(self) -> dict[str, object]:
        return {
            "adapter": self.adapter,
            "attempted": self.attempted,
            "success": self.success,
            "failure_reason": self.failure_reason,
            "candidates_matched": self.candidates_matched,
            "events_augmented": self.events_augmented,
            "official_facts_added": self.official_facts_added,
            "conflicts_found": self.conflicts_found,
            "stories_affected": self.stories_affected,
        }


@dataclass(frozen=True)
class AdapterPayload:
    result: AdapterResult
    evidence: tuple[tuple[str, AuthorityEvidence], ...] = ()


def _json_value(response: HttpResponse) -> object:
    try:
        return json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("INVALID_JSON") from exc


def _safe_status(raw: object) -> str:
    value = str(raw or "").strip()
    return value if re.fullmatch(r"\d{3}", value) else "UNKNOWN"


def _date_iso(value: object) -> str | None:
    text = str(value or "").strip()
    if re.fullmatch(r"\d{8}", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return None


def _fold(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


def _item_text(item: NewsItem) -> str:
    values = (
        item.query,
        item.metadata_title,
        item.title,
        item.metadata_description,
        item.summary if not _TRUNCATION_RE.search(item.summary) else "",
    )
    return " ".join(value for value in values if value).casefold()


def _candidate_entities(items: tuple[NewsItem, ...], entities: tuple[OpenDartEntity, ...]) -> tuple[OpenDartEntity, ...]:
    selected: list[OpenDartEntity] = []
    for entity in entities:
        if any(
            any(_fold(alias) in _fold(_item_text(item)) for alias in entity.aliases)
            and (not entity.topic_ids or item.topic_id in entity.topic_ids)
            for item in items
        ):
            selected.append(entity)
    return tuple(selected)


def _entity_matches(item: NewsItem, entity: OpenDartEntity, corp_name: str) -> bool:
    text = _fold(_item_text(item))
    names = (*entity.aliases, corp_name)
    return any(_fold(alias) in text for alias in names if alias)


def _report_is_relevant(report_name: str, item: NewsItem) -> bool:
    report = report_name.casefold()
    text = _item_text(item)
    event_hit = any(marker.casefold() in report for marker in _DART_EVENT_MARKERS)
    if not event_hit:
        return False
    routine = any(marker.casefold() in report for marker in _DART_ROUTINE_MARKERS)
    # Routine periodic filings are only useful when the discovered story is
    # explicitly about the same financial result or metric.
    if routine and not any(marker in text for marker in ("실적", "매출", "영업이익", "순이익", "가이던스", "공시")):
        return False
    return True


def _dart_evidence(row: dict[str, object]) -> AuthorityEvidence | None:
    report_name = str(row.get("report_nm") or "").strip()
    corp_name = str(row.get("corp_name") or "").strip()
    receipt_no = str(row.get("rcept_no") or "").strip()
    receipt_date = str(row.get("rcept_dt") or "").strip()
    if not report_name or not corp_name or not re.fullmatch(r"\d{14}", receipt_no):
        return None
    published_at = _date_iso(receipt_date)
    if not published_at:
        return None
    url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt_no}"
    return AuthorityEvidence(
        adapter="opendart",
        source_type=AuthoritySourceType.OFFICIAL_CORPORATE,
        authority_strength="HIGH",
        title=f"{corp_name}: {report_name}",
        description=f"{published_at} 금융감독원 공시 접수: {corp_name} · {report_name}.",
        canonical_url=url,
        publisher="금융감독원 OpenDART",
        published_at=published_at,
        event_key=f"DART:{receipt_no}",
        fact_values=(report_name, published_at),
    )


class OpenDartAdapter:
    def __init__(self, *, api_key: str, config: OpenDartConfig, transport: Transport | None = None, timeout: float = 5.0) -> None:
        self.api_key = api_key.strip()
        self.config = config
        self.transport = transport or UrlLibTransport()
        self.timeout = max(1.0, min(10.0, timeout))

    def fetch(self, items: tuple[NewsItem, ...], *, today: date) -> AdapterPayload:
        if not self.api_key:
            return AdapterPayload(AdapterResult("opendart", failure_reason="MISSING_CREDENTIAL"))
        entities = _candidate_entities(items, self.config.entities)
        if not entities:
            return AdapterPayload(AdapterResult("opendart", failure_reason="NO_CANDIDATE_MATCH"))
        begin = today - timedelta(days=self.config.lookback_days)
        query: dict[str, str] = {
            "crtfc_key": self.api_key,
            "bgn_de": begin.strftime("%Y%m%d"),
            "end_de": today.strftime("%Y%m%d"),
            "pblntf_ty": self.config.disclosure_type,
            "sort": "date",
            "sort_mth": "desc",
            "page_no": "1",
            "page_count": str(self.config.page_count),
        }
        # A configured corporation code narrows the request.  Otherwise the
        # single bounded major-disclosure page is filtered locally by the
        # candidate entities; no unbounded company crawl is performed.
        corp_codes = tuple(entity.corp_code for entity in entities if entity.corp_code)
        if len(corp_codes) == 1:
            query["corp_code"] = corp_codes[0]
        url = f"{_DART_URL}?{urlencode(query)}"
        try:
            response = self.transport.request(
                "GET",
                url,
                {"Accept": "application/json", "User-Agent": "InsightDesk/1.0"},
                timeout=self.timeout,
            )
            if response.status < 200 or response.status >= 300:
                return AdapterPayload(AdapterResult("opendart", attempted=1, failure_reason=f"HTTP_{response.status}"))
            payload = _json_value(response)
        except (OSError, TimeoutError):
            return AdapterPayload(AdapterResult("opendart", attempted=1, failure_reason="NETWORK_OR_TIMEOUT"))
        except ValueError as exc:
            return AdapterPayload(AdapterResult("opendart", attempted=1, failure_reason=str(exc)))
        if not isinstance(payload, dict):
            return AdapterPayload(AdapterResult("opendart", attempted=1, failure_reason="INVALID_RESPONSE_SHAPE"))
        status = _safe_status(payload.get("status"))
        if status != "000":
            return AdapterPayload(AdapterResult("opendart", attempted=1, failure_reason=f"API_STATUS_{status}"))
        rows = payload.get("list", [])
        if not isinstance(rows, list):
            return AdapterPayload(AdapterResult("opendart", attempted=1, failure_reason="INVALID_LIST_SHAPE"))
        matched: list[tuple[str, AuthorityEvidence]] = []
        used: set[tuple[str, str]] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            report_name = str(row.get("report_nm") or "")
            evidence = _dart_evidence(row)
            if evidence is None:
                continue
            for item in items:
                entity = next(
                    (candidate for candidate in entities if _entity_matches(item, candidate, str(row.get("corp_name") or ""))),
                    None,
                )
                if entity is None or not _report_is_relevant(report_name, item):
                    continue
                key = (item.evidence_id, evidence.event_key)
                if key not in used:
                    used.add(key)
                    matched.append((item.evidence_id, evidence))
        result = AdapterResult(
            "opendart",
            attempted=1,
            success=True,
            candidates_matched=len({item_id for item_id, _ in matched}),
            events_augmented=len(matched),
            official_facts_added=sum(len(evidence.fact_values) for _, evidence in matched),
            stories_affected=len({item_id for item_id, _ in matched}),
        )
        return AdapterPayload(result, tuple(matched))


def _decimal(value: str) -> Decimal | None:
    cleaned = value.strip().replace(",", "")
    if not cleaned or cleaned in {"-", "..", "…", "NA", "N/A"}:
        return None
    try:
        return Decimal(cleaned.replace("%", ""))
    except InvalidOperation:
        return None


def _unit_key(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


def _kosis_records(payload: object) -> tuple[dict[str, object], ...]:
    if isinstance(payload, dict):
        error_code = str(payload.get("err") or payload.get("errorCode") or "").strip()
        if error_code:
            raise ValueError(f"API_STATUS_{error_code}")
        raise ValueError("INVALID_RESPONSE_SHAPE")
    if not isinstance(payload, list):
        raise ValueError("INVALID_RESPONSE_SHAPE")
    records = tuple(row for row in payload if isinstance(row, dict))
    if not records:
        raise ValueError("NO_DATA")
    return records


def _kosis_evidence(dataset: KosisDataset, records: tuple[dict[str, object], ...]) -> AuthorityEvidence:
    ordered = sorted(records, key=lambda row: str(row.get("PRD_DE") or ""))
    current = ordered[-1]
    previous = ordered[-2] if len(ordered) >= 2 else None
    current_period = str(current.get("PRD_DE") or "").strip()
    current_value = str(current.get("DT") or "").strip()
    unit = str(current.get("UNIT_NM") or "").strip()
    if not current_period or not current_value or not unit:
        raise ValueError("INCOMPLETE_STATISTIC_RECORD")
    if _unit_key(dataset.expected_unit) != _unit_key(unit):
        raise ValueError("UNIT_MISMATCH")
    previous_period = str(previous.get("PRD_DE") or "").strip() if previous else ""
    previous_value = str(previous.get("DT") or "").strip() if previous else ""
    description = f"{dataset.label} {current_period} 수치는 {current_value} {unit}이다."
    facts = [f"{current_period}={current_value} {unit}"]
    if previous_period and previous_value:
        description += f" 직전 {previous_period} 수치는 {previous_value} {unit}이다."
        facts.append(f"{previous_period}={previous_value} {unit}")
        current_number = _decimal(current_value)
        previous_number = _decimal(previous_value)
        if current_number is not None and previous_number is not None:
            direction = "상승" if current_number > previous_number else "하락" if current_number < previous_number else "보합"
            description += f" 두 시점의 단위는 동일하며 방향은 {direction}이다."
    revision_date = str(current.get("LST_CHN_DE") or "").strip()
    return AuthorityEvidence(
        adapter="kosis",
        source_type=AuthoritySourceType.OFFICIAL_STATISTICAL,
        authority_strength="HIGH",
        title=dataset.label,
        description=description,
        canonical_url=f"https://kosis.kr/statHtml/statHtml.do?orgId={dataset.org_id}&tblId={dataset.tbl_id}",
        publisher=dataset.publisher,
        published_at=_date_iso(revision_date),
        event_key=f"KOSIS:{dataset.id}:{current_period}",
        fact_values=tuple(facts),
        unit=unit,
        period=current_period,
        revision_date=revision_date,
    )


class KosisAdapter:
    def __init__(self, *, api_key: str, datasets: tuple[KosisDataset, ...], max_requests: int, transport: Transport | None = None, timeout: float = 5.0) -> None:
        self.api_key = api_key.strip()
        self.datasets = datasets
        self.max_requests = max(1, min(4, max_requests))
        self.transport = transport or UrlLibTransport()
        self.timeout = max(1.0, min(10.0, timeout))

    def fetch(self, items: tuple[NewsItem, ...]) -> AdapterPayload:
        if not self.api_key:
            return AdapterPayload(AdapterResult("kosis", failure_reason="MISSING_CREDENTIAL"))
        matches: list[tuple[str, AuthorityEvidence]] = []
        attempted = 0
        success_count = 0
        failure_reason = ""
        for dataset in self.datasets:
            if attempted >= self.max_requests:
                break
            candidate_ids = tuple(
                item.evidence_id
                for item in items
                if any(keyword.casefold() in _item_text(item) for keyword in dataset.keywords)
            )
            if not candidate_ids:
                continue
            attempted += 1
            query = {
                "method": "getList",
                "apiKey": self.api_key,
                "format": "json",
                "jsonVD": "Y",
                "orgId": dataset.org_id,
                "tblId": dataset.tbl_id,
                "objL1": dataset.obj_l1,
                "itmId": dataset.itm_id,
                "prdSe": dataset.prd_se,
                "newEstPrdCnt": str(dataset.max_periods),
            }
            url = f"{_KOSIS_URL}?{urlencode(query)}"
            try:
                response = self.transport.request(
                    "GET",
                    url,
                    {"Accept": "application/json", "User-Agent": "InsightDesk/1.0"},
                    timeout=self.timeout,
                )
                if response.status < 200 or response.status >= 300:
                    failure_reason = f"HTTP_{response.status}"
                    continue
                payload = _json_value(response)
                records = _kosis_records(payload)
                evidence = _kosis_evidence(dataset, records)
            except (OSError, TimeoutError):
                failure_reason = "NETWORK_OR_TIMEOUT"
                continue
            except ValueError as exc:
                failure_reason = str(exc)
                continue
            success_count += 1
            for candidate_id in candidate_ids:
                matches.append((candidate_id, evidence))
        result = AdapterResult(
            "kosis",
            attempted=attempted,
            success=success_count > 0,
            failure_reason="" if success_count else (failure_reason or "NO_CANDIDATE_MATCH"),
            candidates_matched=len({item_id for item_id, _ in matches}),
            events_augmented=len(matches),
            official_facts_added=sum(len(evidence.fact_values) for _, evidence in matches),
            stories_affected=len({item_id for item_id, _ in matches}),
        )
        return AdapterPayload(result, tuple(matches))
