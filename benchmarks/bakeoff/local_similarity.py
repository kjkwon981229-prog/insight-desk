from __future__ import annotations

import argparse
import json
from pathlib import Path

from sentence_transformers import SentenceTransformer

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

PAIRS = [
    {
        "id": "run92-weather-same-event",
        "same_event": True,
        "left": "폭염으로 중단됐던 프로야구 경기 재개. 프로야구가 폭염으로 중단된 뒤 오늘 재개됐다.",
        "right": "프로야구 오늘 경기 재개. 폭염으로 멈췄던 프로야구 일정이 오늘 다시 시작됐다.",
    },
    {
        "id": "run92-policy-same-event",
        "same_event": True,
        "left": "한은 부총재 경기충격 없다면 기준금리 추가 인상 가능성 커. 유상대 한국은행 부총재가 기준금리를 추가로 올릴 가능성이 크다고 언급했다.",
        "right": "한은 부총재 특별한 충격 없으면 기준금리 추가 인상. 한국은행 부총재는 특별한 충격이 없다면 기준금리를 추가 인상할 수 있다고 밝혔다.",
    },
    {
        "id": "run92-attendance-vs-resumption",
        "same_event": False,
        "left": "2026 프로야구 최소경기 900만 관중 돌파 눈앞. 폭염으로 중단됐던 프로야구가 11일 서울 경기부터 재개됐다.",
        "right": "폭염으로 중단됐던 프로야구 경기 재개. 프로야구가 폭염으로 중단된 뒤 오늘 재개됐다.",
    },
    {
        "id": "run92-weather-vs-policy",
        "same_event": False,
        "left": "폭염으로 중단됐던 프로야구 경기 재개. 프로야구가 폭염으로 중단된 뒤 오늘 재개됐다.",
        "right": "한국은행 부총재는 특별한 충격이 없다면 기준금리를 추가 인상할 수 있다고 밝혔다.",
    },
    {
        "id": "run90-seoul-vs-busan-cancellation",
        "same_event": False,
        "left": "서울 프로야구 경기 폭염으로 취소. 서울 경기가 폭염 영향으로 취소됐다.",
        "right": "부산 프로야구 경기 우천 취소. 부산 경기가 비로 취소됐다.",
    },
    {
        "id": "run90-day12-vs-day13-hard-negative",
        "same_event": False,
        "left": "12일 서울 한화-두산 프로야구 경기 폭염으로 취소. 12일 서울에서 열릴 한화와 두산 경기가 폭염으로 취소됐다.",
        "right": "13일 서울 한화-두산 프로야구 경기 폭염으로 취소. 13일 서울에서 열릴 한화와 두산 경기가 폭염으로 취소됐다.",
    },
    {
        "id": "run96-selection-different-owners",
        "same_event": False,
        "left": "코팅솔루션포유, NVIDIA 협업 프로그램 선정. 코팅솔루션포유가 NVIDIA 협업 프로그램 참여사로 선정됐다.",
        "right": "클루커스, OpenAI Select Partner 선정. 클루커스가 OpenAI Select Partner로 공식 선정됐다.",
    },
]


def _auc(positive: list[float], negative: list[float]) -> float:
    wins = 0.0
    total = len(positive) * len(negative)
    for pos in positive:
        for neg in negative:
            if pos > neg:
                wins += 1.0
            elif pos == neg:
                wins += 0.5
    return wins / total if total else 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    model = SentenceTransformer(MODEL)
    unique_texts = list(dict.fromkeys(text for pair in PAIRS for text in (pair["left"], pair["right"])))
    vectors = model.encode(unique_texts, normalize_embeddings=True)
    by_text = {text: vector for text, vector in zip(unique_texts, vectors)}

    rows = []
    positives: list[float] = []
    negatives: list[float] = []
    for pair in PAIRS:
        score = float(by_text[pair["left"]] @ by_text[pair["right"]])
        (positives if pair["same_event"] else negatives).append(score)
        rows.append({**pair, "cosine": round(score, 6)})

    auc = _auc(positives, negatives)
    report = {
        "model": MODEL,
        "positive_pairs": len(positives),
        "negative_pairs": len(negatives),
        "pairwise_auc": round(auc, 4),
        "positive_min": round(min(positives), 6),
        "negative_max": round(max(negatives), 6),
        "separation_margin": round(min(positives) - max(negatives), 6),
        "rows": rows,
        "note": "Similarity is evaluated only as candidate retrieval. It is not authorized to decide final event identity.",
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(
        f"LOCAL_SIMILARITY_RESULT model={MODEL} auc={report['pairwise_auc']} "
        f"positive_min={report['positive_min']} negative_max={report['negative_max']} "
        f"margin={report['separation_margin']}"
    )
    for row in rows:
        print(f"SIM_CASE {row['id']} same_event={row['same_event']} cosine={row['cosine']}")


if __name__ == "__main__":
    main()
