from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from claim_cases import CLAIM_CASES

MODEL = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL)
    model.eval()
    labels = [model.config.id2label[index].lower() for index in range(model.config.num_labels)]

    rows = []
    passed = 0
    with torch.no_grad():
        for case in CLAIM_CASES:
            encoded = tokenizer(
                case["premise"],
                case["hypothesis"],
                truncation=True,
                return_tensors="pt",
            )
            logits = model(**encoded).logits[0]
            probabilities = torch.softmax(logits, dim=-1).tolist()
            scores = {label: round(float(score), 6) for label, score in zip(labels, probabilities)}
            predicted = labels[max(range(len(probabilities)), key=probabilities.__getitem__)]
            expected = "entailment" if case["expected_entailed"] else "not_entailment"
            ok = predicted == "entailment" if case["expected_entailed"] else predicted != "entailment"
            passed += int(ok)
            rows.append(
                {
                    **case,
                    "expected": expected,
                    "predicted": predicted,
                    "scores": scores,
                    "pass": ok,
                }
            )

    report = {
        "model": MODEL,
        "cases": len(CLAIM_CASES),
        "passed": passed,
        "accuracy": round(passed / len(CLAIM_CASES), 4),
        "rows": rows,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(
        f"LOCAL_NLI_RESULT model={MODEL} passed={passed}/{len(CLAIM_CASES)} "
        f"accuracy={report['accuracy']}"
    )
    for row in rows:
        print(
            f"NLI_CASE {row['id']} expected={row['expected']} predicted={row['predicted']} "
            f"entailment={row['scores'].get('entailment')} pass={row['pass']}"
        )


if __name__ == "__main__":
    main()
