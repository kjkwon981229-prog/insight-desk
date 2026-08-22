from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from dataset import build_cases

DIRECT_FIELDS = {
    "is_material_event",
    "event_type",
    "action",
    "polarity",
    "temporal_state",
    "duration",
    "event_date",
    "location",
    "cause",
    "participants",
    "starters",
    "speaker_role",
    "same_event_with",
    "is_coherent_single_event",
    "context_noun_only_is_not_sufficient_action",
    "requires_direction_or_state_change_for_market_move",
}


def _norm(value: Any) -> Any:
    if isinstance(value, str):
        return re.sub(r"\s+", "", value).casefold()
    if isinstance(value, list):
        return sorted(_norm(item) for item in value)
    return value


def _text(output: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("headline", "summary", "subject", "speaker_role", "action", "object"):
        value = output.get(key)
        if isinstance(value, str):
            parts.append(value)
    return " ".join(parts)


def load_predictions(path: Path) -> dict[str, dict[str, Any]]:
    predictions: dict[str, dict[str, Any]] = {}
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        row = json.loads(raw)
        case_id = row.get("case_id")
        output = row.get("output")
        if not isinstance(case_id, str) or not isinstance(output, dict):
            raise ValueError(f"invalid prediction at line {line_no}")
        predictions[case_id] = output
    return predictions


def score(predictions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    case_rows: list[dict[str, Any]] = []

    for case in build_cases():
        case_id = case["id"]
        output = predictions.get(case_id)
        row = {"case_id": case_id, "task": case["task"], "checks": []}
        if output is None:
            row["missing"] = True
            case_rows.append(row)
            continue

        expected = case["expected"]
        for key, expected_value in expected.items():
            if key not in DIRECT_FIELDS:
                continue
            actual = output.get(key)
            passed = _norm(actual) == _norm(expected_value)
            totals[f"field:{key}"][1] += 1
            totals[f"field:{key}"][0] += int(passed)
            row["checks"].append({"check": key, "pass": passed, "expected": expected_value, "actual": actual})

        generated = _text(output)
        for concept in expected.get("must_preserve_concepts", []):
            passed = _norm(concept) in _norm(generated)
            totals["generation:concept_preservation"][1] += 1
            totals["generation:concept_preservation"][0] += int(passed)
            row["checks"].append({"check": f"preserve:{concept}", "pass": passed})

        for forbidden in case["constraints"].get("forbidden_outputs", []):
            passed = _norm(forbidden) not in _norm(generated)
            totals["generation:forbidden_output_absence"][1] += 1
            totals["generation:forbidden_output_absence"][0] += int(passed)
            row["checks"].append({"check": f"forbidden_output:{forbidden}", "pass": passed})

        for forbidden in case["constraints"].get("forbidden_claims", []):
            passed = _norm(forbidden) not in _norm(generated)
            totals["generation:literal_forbidden_claim_absence"][1] += 1
            totals["generation:literal_forbidden_claim_absence"][0] += int(passed)
            row["checks"].append({"check": f"literal_forbidden_claim:{forbidden}", "pass": passed})

        row["pass"] = all(check["pass"] for check in row["checks"]) if row["checks"] else None
        case_rows.append(row)

    summary = {
        key: {
            "passed": passed,
            "total": total,
            "accuracy": round(passed / total, 4) if total else None,
        }
        for key, (passed, total) in sorted(totals.items())
    }
    return {
        "schema_version": 1,
        "prediction_count": len(predictions),
        "benchmark_case_count": len(case_rows),
        "metrics": summary,
        "cases": case_rows,
        "note": "Grammar, semantic paraphrases, and unsupported-claim equivalence require an independent judge/NLI lane and are not inferred from literal matching.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("predictions", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = score(load_predictions(args.predictions))
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
