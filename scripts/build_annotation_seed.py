from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS = ROOT / "benchmarks"
MATERIAL_DIR = ROOT / "annotation" / "material_event"
FACT_DIR = ROOT / "annotation" / "fact_extraction"
SHUFFLE_SEED = 20260823


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object root: {path}")
    return value


def task_id(prefix: str, text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_material_seed() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    run96 = load_json(BENCHMARKS / "run96_recall_precision.json")
    rows: list[tuple[str, dict[str, str]]] = []

    for item in run96.get("positive_events", []):
        title = str(item.get("title", "")).strip()
        lead = str(item.get("lead", "")).strip()
        if not title:
            continue
        evidence = title if not lead else f"{title}\n{lead}"
        rows.append(
            (
                str(item.get("id", "run96-positive")),
                {
                    "title": title,
                    "lead": lead,
                    "topic_id": str(item.get("topic_id", "")),
                    "query": str(item.get("query", "")),
                    "evidence": evidence,
                    "instruction": (
                        "외부 지식 없이 표시된 근거만 보고 사건성(material event)을 판정하십시오. "
                        "불충분하면 UNCERTAIN을 선택하십시오."
                    ),
                },
            )
        )

    # Architecture Freeze explicitly forbids converting these old selection TNs into
    # NOT_MATERIAL gold. They are imported as fully UNLABELED human-adjudication tasks.
    for index, title_value in enumerate(run96.get("true_negative_titles", []), start=1):
        title = str(title_value).strip()
        if not title:
            continue
        rows.append(
            (
                f"run96-selection-tn-title-{index:02d}",
                {
                    "title": title,
                    "lead": "",
                    "topic_id": "",
                    "query": "",
                    "evidence": title,
                    "instruction": (
                        "외부 지식 없이 표시된 근거만 보고 사건성(material event)을 판정하십시오. "
                        "제목만으로 부족하면 반드시 UNCERTAIN을 선택하십시오."
                    ),
                },
            )
        )

    random.Random(SHUFFLE_SEED).shuffle(rows)
    tasks: list[dict[str, Any]] = []
    provenance: dict[str, Any] = {}
    for source_ref, data in rows:
        identifier = task_id("material-v1", data["evidence"])
        tasks.append({"id": identifier, "data": data})
        provenance[identifier] = {"source_suite": "run96_recall_precision", "source_ref": source_ref}
    return tasks, provenance


def add_fact_task(
    rows: dict[str, tuple[str, dict[str, str]]],
    *,
    source_suite: str,
    source_ref: str,
    title: str,
    lead: str,
) -> None:
    title = title.strip()
    lead = lead.strip()
    text = title if not lead else f"{title}\n{lead}"
    if not text:
        return
    rows.setdefault(
        text,
        (
            f"{source_suite}:{source_ref}",
            {
                "title": title,
                "lead": lead,
                "text": text,
                "instruction": (
                    "표시된 텍스트에서 실제로 근거가 있는 사실 요소만 span으로 표시하십시오. "
                    "추정하거나 원문에 없는 정보를 보완하지 마십시오."
                ),
            },
        ),
    )


def build_fact_seed() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: dict[str, tuple[str, dict[str, str]]] = {}

    run96 = load_json(BENCHMARKS / "run96_recall_precision.json")
    for item in run96.get("positive_events", []):
        add_fact_task(
            rows,
            source_suite="run96_recall_precision",
            source_ref=str(item.get("id", "positive")),
            title=str(item.get("title", "")),
            lead=str(item.get("lead", "")),
        )

    run9495 = load_json(BENCHMARKS / "run94_95_semantic.json")
    for case in run9495.get("cases", []):
        raw = case.get("input", {})
        if not isinstance(raw, dict):
            continue
        add_fact_task(
            rows,
            source_suite="run94_95_semantic",
            source_ref=str(case.get("id", "case")),
            title=str(raw.get("title", "")),
            lead=str(raw.get("lead", "")),
        )

    run97 = load_json(BENCHMARKS / "run97_generation.json")
    for case in run97.get("cases", []):
        raw = case.get("input", {})
        if not isinstance(raw, dict):
            continue
        add_fact_task(
            rows,
            source_suite="run97_generation",
            source_ref=str(case.get("id", "case")),
            title=str(raw.get("title", "")),
            lead=str(raw.get("lead", "")),
        )

    ordered = list(rows.values())
    random.Random(SHUFFLE_SEED).shuffle(ordered)
    tasks: list[dict[str, Any]] = []
    provenance: dict[str, Any] = {}
    for source_ref, data in ordered:
        identifier = task_id("fact-v1", data["text"])
        tasks.append({"id": identifier, "data": data})
        source_suite, _, source_item = source_ref.partition(":")
        provenance[identifier] = {"source_suite": source_suite, "source_ref": source_item}
    return tasks, provenance


def main() -> None:
    material_tasks, material_provenance = build_material_seed()
    fact_tasks, fact_provenance = build_fact_seed()

    write_json(MATERIAL_DIR / "tasks_seed.json", material_tasks)
    write_json(MATERIAL_DIR / "seed_provenance.json", material_provenance)
    write_json(FACT_DIR / "tasks_seed.json", fact_tasks)
    write_json(FACT_DIR / "seed_provenance.json", fact_provenance)

    print(
        "ANNOTATION_SEED_READY "
        f"material_tasks={len(material_tasks)} fact_tasks={len(fact_tasks)} "
        "labels_prepopulated=0"
    )


if __name__ == "__main__":
    main()
