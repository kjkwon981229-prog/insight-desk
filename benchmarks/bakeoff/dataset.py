from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "benchmarks"


def _load(name: str) -> dict[str, Any]:
    return json.loads((BENCH / name).read_text(encoding="utf-8"))


def build_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []

    run90 = _load("run90_temporal.json")
    for case in run90["cases"]:
        cases.append(
            {
                "id": case["id"],
                "source_suite": run90["suite_id"],
                "task": "EVENT_EXTRACT",
                "input": case["input"],
                "expected": case["gold"],
                "constraints": {},
            }
        )

    run92 = _load("run92_ownership.json")
    groups: dict[str, list[str]] = {}
    for case in run92["cases"]:
        groups.setdefault(case["gold"]["ownership_group"], []).append(case["id"])
    ownership_context = [
        {"id": case["id"], "input": case["input"]} for case in run92["cases"]
    ]
    for case in run92["cases"]:
        gold = dict(case["gold"])
        group = gold.pop("ownership_group")
        gold.pop("should_merge_with", None)
        gold.pop("must_not_merge_with", None)
        gold["same_event_with"] = sorted(
            candidate for candidate in groups[group] if candidate != case["id"]
        )
        cases.append(
            {
                "id": case["id"],
                "source_suite": run92["suite_id"],
                "task": "EVENT_OWNERSHIP",
                "input": {
                    "target": {"id": case["id"], "input": case["input"]},
                    "candidates": ownership_context,
                },
                "expected": gold,
                "constraints": {},
            }
        )

    run9495 = _load("run94_95_semantic.json")
    for case in run9495["cases"]:
        gold = dict(case["gold"])
        gold.pop("reason", None)
        cases.append(
            {
                "id": case["id"],
                "source_suite": run9495["suite_id"],
                "task": "SEMANTIC_CHECK",
                "input": case["input"],
                "expected": gold,
                "constraints": {
                    "forbidden_outputs": case.get("forbidden_outputs", []),
                    "forbidden_claims": case.get("forbidden_claims", []),
                },
            }
        )

    run96 = _load("run96_recall_precision.json")
    for item in run96["positive_events"]:
        expected = {"is_material_event": True, **item["gold"]}
        cases.append(
            {
                "id": f"run96-positive-{item['id']}",
                "source_suite": run96["suite_id"],
                "task": "MATERIAL_EVENT",
                "input": {
                    "topic_id": item["topic_id"],
                    "query": item["query"],
                    "title": item["title"],
                    "lead": item["lead"],
                },
                "expected": expected,
                "constraints": {},
            }
        )
    for index, title in enumerate(run96["true_negative_titles"], start=1):
        cases.append(
            {
                "id": f"run96-tn-{index:02d}",
                "source_suite": run96["suite_id"],
                "task": "MATERIAL_EVENT",
                "input": {"title": title},
                "expected": {"is_material_event": False},
                "constraints": {},
            }
        )

    run97 = _load("run97_generation.json")
    for case in run97["cases"]:
        cases.append(
            {
                "id": case["id"],
                "source_suite": run97["suite_id"],
                "task": "GENERATION",
                "input": case["input"],
                "expected": case["gold"],
                "constraints": {
                    "forbidden_outputs": case.get("forbidden_outputs", []),
                    "forbidden_claims": case.get("forbidden_claims", []),
                },
            }
        )

    if len(cases) != 85:
        raise AssertionError(f"expected 85 hard-scored cases, got {len(cases)}")
    ids = [case["id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise AssertionError("duplicate bake-off case ids")
    return cases


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    cases = build_cases()
    counts: dict[str, int] = {}
    for case in cases:
        counts[case["task"]] = counts.get(case["task"], 0) + 1

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps({"schema_version": 1, "cases": cases}, ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )

    if args.check or not args.output:
        print(
            "BAKEOFF_DATASET_VALID "
            + " ".join(f"{key.lower()}={value}" for key, value in sorted(counts.items()))
            + f" total={len(cases)}"
        )


if __name__ == "__main__":
    main()
