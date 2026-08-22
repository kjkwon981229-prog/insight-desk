from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

MODEL = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"

CASES = [
    {
        "id": "run97-groundbreaking-future-supported",
        "source_case": "run97-groundbreaking-future",
        "premise": "SK하이닉스, 미국 인디애나 HBM 패키징 공장 착공식. SK하이닉스가 27일 착공식을 연다.",
        "hypothesis": "SK하이닉스는 27일 미국 인디애나 HBM 패키징 공장 착공식을 열 예정이다.",
        "expected": "entailment",
    },
    {
        "id": "run97-groundbreaking-future-completed",
        "source_case": "run97-groundbreaking-future",
        "premise": "SK하이닉스, 미국 인디애나 HBM 패키징 공장 착공식. SK하이닉스가 27일 착공식을 연다.",
        "hypothesis": "SK하이닉스는 미국 인디애나 HBM 패키징 공장 착공을 이미 완료했다.",
        "expected": "not_entailment",
    },
    {
        "id": "run97-groundbreaking-completed-supported",
        "source_case": "run97-groundbreaking-completed",
        "premise": "SK하이닉스, 미국 인디애나 HBM 패키징 공장 착공식. SK하이닉스가 착공식을 열었다.",
        "hypothesis": "SK하이닉스는 미국 인디애나 HBM 패키징 공장 착공식을 열었다.",
        "expected": "entailment",
    },
    {
        "id": "run97-groundbreaking-completed-planned",
        "source_case": "run97-groundbreaking-completed",
        "premise": "SK하이닉스, 미국 인디애나 HBM 패키징 공장 착공식. SK하이닉스가 착공식을 열었다.",
        "hypothesis": "SK하이닉스는 아직 착공식을 열지 않았고 앞으로 열 예정이다.",
        "expected": "not_entailment",
    },
    {
        "id": "run97-departure-announcement-supported",
        "source_case": "run97-departure-announcement",
        "premise": "트와이스 채영, 14년 만에 JYP 떠난다. 트와이스 채영이 떠난다고 밝혔다.",
        "hypothesis": "트와이스 채영은 JYP를 떠난다고 밝혔다.",
        "expected": "entailment",
    },
    {
        "id": "run97-departure-announcement-completed",
        "source_case": "run97-departure-announcement",
        "premise": "트와이스 채영, 14년 만에 JYP 떠난다. 트와이스 채영이 떠난다고 밝혔다.",
        "hypothesis": "트와이스 채영은 이미 JYP를 떠났다.",
        "expected": "not_entailment",
    },
    {
        "id": "run97-investment-planned-supported",
        "source_case": "run97-investment-planned",
        "premise": "A사, AI 사업 투자. A사가 투자하기로 했다.",
        "hypothesis": "A사는 AI 사업에 투자하기로 했다.",
        "expected": "entailment",
    },
    {
        "id": "run97-investment-planned-completed",
        "source_case": "run97-investment-planned",
        "premise": "A사, AI 사업 투자. A사가 투자하기로 했다.",
        "hypothesis": "A사는 AI 사업 투자를 이미 완료했다.",
        "expected": "not_entailment",
    },
    {
        "id": "run97-investment-completed-supported",
        "source_case": "run97-investment-completed",
        "premise": "A사, AI 사업 투자. A사가 투자했다.",
        "hypothesis": "A사는 AI 사업에 투자했다.",
        "expected": "entailment",
    },
    {
        "id": "run97-investment-completed-planned",
        "source_case": "run97-investment-completed",
        "premise": "A사, AI 사업 투자. A사가 투자했다.",
        "hypothesis": "A사는 아직 AI 사업에 투자하지 않았고 앞으로 투자할 예정이다.",
        "expected": "not_entailment",
    },
    {
        "id": "run90-seoul-heat-supported",
        "source_case": "run90-seoul-heat",
        "premise": "서울 프로야구 경기 폭염으로 취소. 서울 경기가 폭염 영향으로 취소됐다.",
        "hypothesis": "서울 프로야구 경기는 폭염 때문에 취소됐다.",
        "expected": "entailment",
    },
    {
        "id": "run90-seoul-heat-wrong-location",
        "source_case": "run90-seoul-heat",
        "premise": "서울 프로야구 경기 폭염으로 취소. 서울 경기가 폭염 영향으로 취소됐다.",
        "hypothesis": "부산 프로야구 경기가 폭염 때문에 취소됐다.",
        "expected": "not_entailment",
    },
    {
        "id": "run90-busan-rain-supported",
        "source_case": "run90-busan-rain",
        "premise": "부산 프로야구 경기 우천 취소. 부산 경기가 비로 취소됐다.",
        "hypothesis": "부산 프로야구 경기는 비 때문에 취소됐다.",
        "expected": "entailment",
    },
    {
        "id": "run90-busan-rain-wrong-cause",
        "source_case": "run90-busan-rain",
        "premise": "부산 프로야구 경기 우천 취소. 부산 경기가 비로 취소됐다.",
        "hypothesis": "부산 프로야구 경기는 폭염 때문에 취소됐다.",
        "expected": "not_entailment",
    },
]


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
        for case in CASES:
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
            ok = predicted == "entailment" if case["expected"] == "entailment" else predicted != "entailment"
            passed += int(ok)
            rows.append(
                {
                    **case,
                    "predicted": predicted,
                    "scores": scores,
                    "pass": ok,
                }
            )

    report = {
        "model": MODEL,
        "cases": len(CASES),
        "passed": passed,
        "accuracy": round(passed / len(CASES), 4),
        "rows": rows,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(f"LOCAL_NLI_RESULT model={MODEL} passed={passed}/{len(CASES)} accuracy={report['accuracy']}")
    for row in rows:
        print(
            f"NLI_CASE {row['id']} expected={row['expected']} predicted={row['predicted']} "
            f"entailment={row['scores'].get('entailment')} pass={row['pass']}"
        )


if __name__ == "__main__":
    main()
