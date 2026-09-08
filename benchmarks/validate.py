from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"BENCHMARK_INVALID: {message}")


def main() -> None:
    manifest = load("manifest.json")
    taxonomy = load("taxonomy.json")
    category_ids = {item["id"] for item in taxonomy["categories"]}
    require(len(category_ids) == len(taxonomy["categories"]), "duplicate taxonomy id")

    expected = {
        "run89_semantic_evidence.json": ("evidence", 7),
        "run90_temporal.json": ("cases", 7),
        "run92_ownership.json": ("cases", 5),
        "run94_95_semantic.json": ("cases", 7),
        "run97_generation.json": ("cases", 7),
    }

    scored_case_ids: set[str] = set()
    hard_scored = 0
    evidence_only = 0

    for filename, (kind, count) in expected.items():
        suite = load(filename)
        cases = suite["cases"]
        require(len(cases) == count, f"{filename}: expected {count} cases, got {len(cases)}")
        ids = [case["id"] for case in cases]
        require(len(ids) == len(set(ids)), f"{filename}: duplicate case id")

        if kind == "evidence":
            require(suite.get("status") == "EVIDENCE_ONLY_NOT_SCORED", f"{filename}: evidence suite status")
            require(all("gold" not in case for case in cases), f"{filename}: evidence-only cases must not invent gold")
            evidence_only += len(cases)
            continue

        for case in cases:
            require(case.get("gold") is not None, f"{filename}/{case['id']}: missing gold")
            categories = case.get("categories") or []
            require(categories, f"{filename}/{case['id']}: missing categories")
            unknown = set(categories) - category_ids
            require(not unknown, f"{filename}/{case['id']}: unknown categories {sorted(unknown)}")
            require(case["id"] not in scored_case_ids, f"duplicate scored case id {case['id']}")
            scored_case_ids.add(case["id"])
        hard_scored += len(cases)

    run96 = load("run96_recall_precision.json")
    positives = run96["positive_events"]
    negatives = run96["true_negative_titles"]
    require(run96["confirmed_fn_event_count"] == 15, "Run96 confirmed FN event count changed")
    require(len(positives) == 15, f"Run96 positives: expected 15, got {len(positives)}")
    require(len(negatives) == 44, f"Run96 true negatives: expected 44, got {len(negatives)}")
    require(len({item['id'] for item in positives}) == 15, "Run96 positive ids not unique")
    require(len(set(negatives)) == 44, "Run96 true-negative titles not unique")
    for item in positives:
        require(item.get("gold", {}).get("event_type"), f"Run96/{item['id']}: missing event_type")
        require(item.get("gold", {}).get("action"), f"Run96/{item['id']}: missing action")
    hard_scored += len(positives) + len(negatives)

    require(hard_scored == manifest["counts"]["hard_scored_cases"], f"hard scored count {hard_scored}")
    require(evidence_only == manifest["counts"]["evidence_only_cases"], f"evidence-only count {evidence_only}")
    require(manifest["counts"]["run96_confirmed_positive_events"] == len(positives), "manifest Run96 positive count")
    require(manifest["counts"]["run96_confirmed_true_negatives"] == len(negatives), "manifest Run96 negative count")

    required_metrics = set(manifest["required_bakeoff_metrics"])
    require("local_failure_isolation" in required_metrics, "local failure isolation metric is mandatory")
    require("sentence_faithfulness" in required_metrics, "sentence faithfulness metric is mandatory")

    print(
        "BENCHMARK_VALID "
        f"hard_scored={hard_scored} evidence_only={evidence_only} "
        f"taxonomy={len(category_ids)} run96_positive={len(positives)} run96_tn={len(negatives)}"
    )


if __name__ == "__main__":
    main()
