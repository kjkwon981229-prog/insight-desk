from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class AuthorityConfigError(ValueError):
    pass


@dataclass(frozen=True)
class OpenDartEntity:
    id: str
    aliases: tuple[str, ...]
    topic_ids: tuple[str, ...]
    corp_code: str = ""


@dataclass(frozen=True)
class OpenDartConfig:
    enabled: bool
    lookback_days: int
    page_count: int
    disclosure_type: str
    max_requests: int
    entities: tuple[OpenDartEntity, ...]


@dataclass(frozen=True)
class KosisDataset:
    id: str
    label: str
    org_id: str
    tbl_id: str
    obj_l1: str
    itm_id: str
    prd_se: str
    keywords: tuple[str, ...]
    expected_unit: str
    publisher: str
    obj_l2: str = ""
    max_periods: int = 2


@dataclass(frozen=True)
class KosisConfig:
    enabled: bool
    max_requests: int
    datasets: tuple[KosisDataset, ...]


@dataclass(frozen=True)
class AuthorityConfig:
    schema_version: int
    open_dart: OpenDartConfig
    kosis: KosisConfig


def _text(raw: object, field: str) -> str:
    value = str(raw or "").strip()
    if not value:
        raise AuthorityConfigError(f"authoritative config field is empty: {field}")
    return value


def _bounded_int(raw: object, field: str, *, minimum: int, maximum: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise AuthorityConfigError(f"authoritative config field is not an integer: {field}") from exc
    if value < minimum or value > maximum:
        raise AuthorityConfigError(f"authoritative config field is out of bounds: {field}")
    return value


def load_authority_config(path: Path) -> AuthorityConfig:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuthorityConfigError(f"authoritative config cannot be read: {path.name}") from exc
    if not isinstance(raw, dict) or int(raw.get("schema_version", 0)) != 1:
        raise AuthorityConfigError("unsupported authoritative config schema")

    dart_raw = raw.get("open_dart") or {}
    if not isinstance(dart_raw, dict):
        raise AuthorityConfigError("open_dart must be an object")
    entities: list[OpenDartEntity] = []
    for entity_raw in dart_raw.get("entities", []):
        if not isinstance(entity_raw, dict):
            raise AuthorityConfigError("OpenDART entity must be an object")
        aliases = tuple(_text(value, "open_dart.entities.aliases") for value in entity_raw.get("aliases", []))
        if not aliases:
            raise AuthorityConfigError("OpenDART entity must have aliases")
        corp_code = str(entity_raw.get("corp_code") or "").strip()
        if corp_code and (len(corp_code) != 8 or not corp_code.isdigit()):
            raise AuthorityConfigError("OpenDART corp_code must be eight digits")
        entities.append(
            OpenDartEntity(
                id=_text(entity_raw.get("id"), "open_dart.entities.id"),
                aliases=aliases,
                topic_ids=tuple(str(value) for value in entity_raw.get("topic_ids", [])),
                corp_code=corp_code,
            )
        )
    dart = OpenDartConfig(
        enabled=bool(dart_raw.get("enabled", True)),
        lookback_days=_bounded_int(dart_raw.get("lookback_days", 7), "open_dart.lookback_days", minimum=1, maximum=31),
        page_count=_bounded_int(dart_raw.get("page_count", 50), "open_dart.page_count", minimum=1, maximum=100),
        disclosure_type=_text(dart_raw.get("disclosure_type", "B"), "open_dart.disclosure_type"),
        max_requests=_bounded_int(dart_raw.get("max_requests", 2), "open_dart.max_requests", minimum=1, maximum=4),
        entities=tuple(entities),
    )

    kosis_raw = raw.get("kosis") or {}
    if not isinstance(kosis_raw, dict):
        raise AuthorityConfigError("kosis must be an object")
    datasets: list[KosisDataset] = []
    for dataset_raw in kosis_raw.get("datasets", []):
        if not isinstance(dataset_raw, dict):
            raise AuthorityConfigError("KOSIS dataset must be an object")
        keywords = tuple(_text(value, "kosis.datasets.keywords") for value in dataset_raw.get("keywords", []))
        if not keywords:
            raise AuthorityConfigError("KOSIS dataset must have keywords")
        datasets.append(
            KosisDataset(
                id=_text(dataset_raw.get("id"), "kosis.datasets.id"),
                label=_text(dataset_raw.get("label"), "kosis.datasets.label"),
                org_id=_text(dataset_raw.get("org_id"), "kosis.datasets.org_id"),
                tbl_id=_text(dataset_raw.get("tbl_id"), "kosis.datasets.tbl_id"),
                obj_l1=_text(dataset_raw.get("obj_l1"), "kosis.datasets.obj_l1"),
                itm_id=_text(dataset_raw.get("itm_id"), "kosis.datasets.itm_id"),
                prd_se=_text(dataset_raw.get("prd_se"), "kosis.datasets.prd_se"),
                keywords=keywords,
                expected_unit=_text(dataset_raw.get("expected_unit"), "kosis.datasets.expected_unit"),
                publisher=_text(dataset_raw.get("publisher"), "kosis.datasets.publisher"),
                obj_l2=str(dataset_raw.get("obj_l2") or "").strip(),
                max_periods=_bounded_int(dataset_raw.get("max_periods", 2), "kosis.datasets.max_periods", minimum=2, maximum=4),
            )
        )
    kosis = KosisConfig(
        enabled=bool(kosis_raw.get("enabled", True)),
        max_requests=_bounded_int(kosis_raw.get("max_requests", 2), "kosis.max_requests", minimum=1, maximum=4),
        datasets=tuple(datasets),
    )
    return AuthorityConfig(schema_version=1, open_dart=dart, kosis=kosis)
