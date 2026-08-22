from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from provider_contract import schema_for

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "benchmarks"


def _load(name: str) -> dict[str, Any]:
    return json.loads((BENCH / name).read_text(encoding="utf-8"))


def _split_gold(task: str, gold: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    schema_keys = set(schema_for({"task": task})["properties"])
    expected = {key: value for key, value in gold.items() if key in schema_keys}
    evaluator = {key: value for key, value in gold.items() if key not in schema_keys}
    return expected, evaluator


def _assert_contract_fairness(cases: list[dict[str, Any]]) -> None:
    for case in cases:
        schema = schema_for(case)
        properties = schema["properties"]
        expected = case["expected"]
        unknown = sorted(set(expected) - set(properties))
        if unknown:
            raise AssertionError(f"{case['id']}: unscorable expected fields: {unknown}")
        for key, expected_value in expected.items():
            enum = properties[key].get("enum")
            if enum is not None and expected_value not in enum:
                raise AssertionError(
                    f"{case['id']}: expected {key}={expected_value!r} is outside schema enum {enum!r}"
                )


def build_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []

    run90 = _load("run90_temporal.json")
    for case in run90["cases"]:
        gold = dict(case["gold"])
        gold.pop("is_material_event", None)
        expected, evaluator = _split_gold("EVENT_EXTRACT", gold)
        cases.append(
            {
                "id": case["id"],
                "source_suite": run90["suite_id"],
                "task": "EVENT_EXTRACT",
                "input": case["input"],
                "expected": expected,
                "constraints": {"evaluator_requirements": evaluator},
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
        expected, evaluator = _split_gold("EVENT_OWNERSHIP", gold)
        cases.append(
            {
                "id": case["id"],
                "source_suite": run92["suite_id"],
                "task": "EVENT_OWNERSHIP",
                "input": {
                    "target": {"id": case["id"], "input": case["input"]},
                    "candidates": ownership_context,
                },
                "expected": expected,
                "constraints": {"evaluator_requirements": evaluator},
            }
        )

    run9495 = _load("run94_95_semantic.json")
    for case in run9495["cases"]:
        gold = dict(case["gold"])
        gold.pop("reason", None)
        expected, evaluator = _split_gold("SEMANTIC_CHECK", gold)
        cases.append(
            {
                "id": case["id"],
                "source_suite": run9495["suite_id"],
                "task": "SEMANTIC_CHECK",
                "input": case["input"],
                "expected": expected,
                "constraints": {
                    "forbidden_outputs": case.get("forbidden_outputs", []),
                    "forbidden_claims": case.get("forbidden_claims", []),
                    "evaluator_requirements": evaluator,
                },
            }
        )

    run96 = _load("run96_recall_precision.json")
    for item in run96["positive_events"]:
        gold = {"is_material_event": True, **item["gold"]}
        expected, evaluator = _split_gold("MATERIAL_EVENT", gold)
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
                "constraints": {"evaluator_requirements": evaluator},
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
                "constraints": {"evaluator_requirements": {}},
            }
        )

    run97 = _load("run97_generation.json")
    for case in run97["cases"]:
        expected, evaluator = _split_gold("GENERATION", dict(case["gold"]))
        cases.append(
            {
                "id": case["id"],
                "source_suite": run97["suite_id"],
                "task": "GENERATION",
                "input": case["input"],
                "expected": expected,
                "constraints": {
                    "forbidden_outputs": case.get("forbidden_outputs", []),
                    "forbidden_claims": case.get("forbidden_claims", []),
                    "must_preserve_concepts": evaluator.pop("must_preserve_concepts", []),
                    "evaluator_requirements": evaluator,
                },
            }
        )

    if len(cases) != 85:
        raise AssertionError(f"expected 85 hard-scored cases, got {len(cases)}")
    ids = [case["id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise AssertionError("duplicate bake-off case ids")
    _assert_contract_fairness(cases)
    return cases


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    cases = build_cases()
    counts: dict[str, int] = {}
    evaluator_requirements = 0
    for case in cases:
        counts[case["task"]] = counts.get(case["task"], 0) + 1
        evaluator_requirements += len(case["constraints"].get("evaluator_requirements", {}))

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps({"schema_version": 2, "cases": cases}, ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )

    if args.check or not args.output:
        print(
            "BAKEOFF_DATASET_VALID "
            + " ".join(f"{key.lower()}={value}" for key, value in sorted(counts.items()))
            + f" total={len(cases)} evaluator_only={evaluator_requirements} fairness=pass"
        )


if __name__ == "__main__":
    main()
