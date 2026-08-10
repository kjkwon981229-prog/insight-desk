from __future__ import annotations

import os
import re
from dataclasses import dataclass, replace
from datetime import date, datetime

from ..collectors.transport import Transport
from ..domain.models import AuthorityEvidence, EvidenceType, NewsItem
from .adapters import AdapterPayload, AdapterResult, KosisAdapter, OpenDartAdapter
from .config import AuthorityConfig


@dataclass(frozen=True)
class AuthorityReport:
    items: tuple[NewsItem, ...]
    audits: tuple[dict[str, object], ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def attempted(self) -> int:
        return sum(int(audit.get("attempted", 0) or 0) for audit in self.audits)

    @property
    def succeeded(self) -> int:
        return sum(1 for audit in self.audits if audit.get("success") is True)

    @property
    def augmented(self) -> int:
        return sum(int(audit.get("events_augmented", 0) or 0) for audit in self.audits)


def _comparable_numbers(value: str) -> set[str]:
    numbers: set[str] = set()
    for match in re.finditer(r"(?<!\d)(\d[\d,.]*)(?:\s*)(%|원|명|건|개|곳|배|점|위|대|억원|조원)?", value):
        raw = match.group(1).replace(",", "")
        unit = match.group(2) or ""
        # Period labels and index bases are metadata, not observations.
        if not unit and raw.isdigit() and len(raw) in {4, 6, 8}:
            continue
        if "." not in raw and not unit and raw in {"100", "2020"}:
            continue
        numbers.add(raw)
    return numbers


def _conflict_count(item: NewsItem, evidence: AuthorityEvidence) -> int:
    """Count explicit numeric disagreement without treating it as silence.

    The router still attaches the primary evidence.  The private audit records
    the conflict so a later editorial rule can downgrade or reject the story;
    no conflicting number is synthesized merely because both sources exist.
    """

    if not evidence.fact_values:
        return 0
    item_text = " ".join((item.metadata_title, item.title, item.metadata_description))
    item_numbers = _comparable_numbers(item_text)
    official_numbers = {
        number
        for value in evidence.fact_values
        for number in _comparable_numbers(value.split("=", 1)[-1])
    }
    if not item_numbers or not official_numbers:
        return 0
    return int(item_numbers.isdisjoint(official_numbers))


def _attach(
    items: tuple[NewsItem, ...], payloads: tuple[AdapterPayload, ...]
) -> tuple[tuple[NewsItem, ...], dict[str, int]]:
    by_id = {item.evidence_id: item for item in items}
    conflicts: dict[str, int] = {}
    for payload in payloads:
        for item_id, evidence in payload.evidence:
            item = by_id.get(item_id)
            if item is None:
                continue
            conflicts[payload.result.adapter] = conflicts.get(payload.result.adapter, 0) + _conflict_count(item, evidence)
            existing_keys = {value.event_key for value in item.authoritative_evidence if value.event_key}
            if evidence.event_key and evidence.event_key in existing_keys:
                continue
            provenance = tuple(dict.fromkeys((*item.provenance, EvidenceType.OFFICIAL_SOURCE)))
            by_id[item_id] = replace(
                item,
                provenance=provenance,
                authoritative_evidence=(*item.authoritative_evidence, evidence),
            )
    return tuple(by_id[item.evidence_id] for item in items), conflicts


class AuthoritativeRouter:
    """Run bounded optional adapters against already selected candidates."""

    def __init__(
        self,
        *,
        config: AuthorityConfig,
        transport: Transport | None = None,
        open_dart_key: str | None = None,
        kosis_key: str | None = None,
    ) -> None:
        self.config = config
        self.transport = transport
        self.open_dart_key = (open_dart_key if open_dart_key is not None else os.environ.get("OPENDART_API_KEY", "")).strip()
        self.kosis_key = (kosis_key if kosis_key is not None else os.environ.get("KOSIS_API_KEY", "")).strip()

    def augment(self, items: tuple[NewsItem, ...], *, now: datetime) -> AuthorityReport:
        payloads: list[AdapterPayload] = []
        if self.config.open_dart.enabled:
            payloads.append(
                OpenDartAdapter(
                    api_key=self.open_dart_key,
                    config=self.config.open_dart,
                    transport=self.transport,
                ).fetch(items, today=now.date())
            )
        else:
            payloads.append(AdapterPayload(AdapterResult("opendart", failure_reason="DISABLED")))
        if self.config.kosis.enabled:
            payloads.append(
                KosisAdapter(
                    api_key=self.kosis_key,
                    datasets=self.config.kosis.datasets,
                    max_requests=self.config.kosis.max_requests,
                    transport=self.transport,
                ).fetch(items)
            )
        else:
            payloads.append(AdapterPayload(AdapterResult("kosis", failure_reason="DISABLED")))

        augmented, conflicts = _attach(items, tuple(payloads))
        audits: list[dict[str, object]] = []
        warnings: list[str] = []
        for payload in payloads:
            audit = payload.result.to_audit()
            audit["conflicts_found"] = conflicts.get(str(audit["adapter"]), 0)
            audits.append(audit)
            if not payload.result.success and payload.result.failure_reason not in {"", "NO_CANDIDATE_MATCH", "DISABLED"}:
                warnings.append("공식 근거 보강을 일부 사용할 수 없어 검색 결과 중심으로 게시했다.")
        return AuthorityReport(augmented, tuple(audits), tuple(dict.fromkeys(warnings)))


def build_authoritative_router(config: AuthorityConfig, *, transport: Transport | None = None) -> AuthoritativeRouter:
    """Build a router from the two repository-secret environment variables."""

    return AuthoritativeRouter(config=config, transport=transport)
