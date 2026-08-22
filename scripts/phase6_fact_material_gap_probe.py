from __future__ import annotations

import json
from pathlib import Path


def load(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    run96 = load("benchmarks/run96_recall_precision.json")
    run90 = load("benchmarks/run90_temporal.json")
    run9495 = load("benchmarks/run94_95_semantic.json")
    run97 = load("benchmarks/run97_generation.json")

    print(
        "PHASE6_GAP_PROBE "
        f"run96_positive={len(run96['positive_events'])} "
        f"run96_selection_tn={len(run96['true_negative_titles'])} "
        f"run90_cases={len(run90.get('cases', []))} "
        f"run9495_cases={len(run9495.get('cases', []))} "
        f"run97_cases={len(run97.get('cases', []))}"
    )
    print("FACT_GOLD_NOTE run96_positive_has_action_gold=true full_role_gold=false")
    print("MATERIAL_GOLD_NOTE selection_tn_must_not_be_repurposed_as_not_material=true")


if __name__ == "__main__":
    main()
