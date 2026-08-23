from __future__ import annotations

import argparse
import json
from pathlib import Path

from insight_desk.providers.local_nli import (
    LOCAL_NLI_FALLBACK_MODEL,
    LOCAL_NLI_MODEL,
    LocalNliVerifier,
)


CASES = (
    # Positive entailments: same fact or conservative paraphrase, no added material content.
    ("p01_exact_fx", True, "원·달러 환율은 1386.5원으로 마감했다.", "원·달러 환율은 1386.5원으로 마감했다."),
    ("p02_fx_paraphrase", True, "원·달러 환율은 전 거래일보다 6.1원 내린 1386.5원으로 마감했다.", "원·달러 환율이 1386.5원에 마감했다."),
    ("p03_split", True, "카카오는 인적분할을 추진한다고 밝혔다.", "카카오가 인적분할을 추진한다."),
    ("p04_kbo_streak", True, "한화는 이날 승리로 연패를 끊었다.", "한화가 연패를 종료했다."),
    ("p05_innings", True, "양현종은 13시즌 연속 100이닝을 달성했다.", "양현종이 13시즌 연속 100이닝을 기록했다."),
    ("p06_future_announced", True, "정부는 9월 3일부터 새 제도를 시행한다고 밝혔다.", "정부가 9월 3일부터 새 제도를 시행할 예정이라고 밝혔다."),
    ("p07_contract", True, "네오팩토리가 AI 공장 구축 사업을 15억달러에 수주했다.", "네오팩토리가 15억달러 규모 AI 공장 구축 사업을 수주했다."),
    ("p08_price", True, "생산자물가는 전월보다 0.4% 상승했다.", "생산자물가가 전월 대비 0.4% 올랐다."),
    ("p09_launch", True, "테스트 기업은 2026년 8월 23일 신제품을 출시했다.", "테스트 기업이 2026년 8월 23일 신제품을 내놓았다."),
    ("p10_watch", True, "한국은행 부총재는 물가 흐름을 더 지켜봐야 한다고 밝혔다.", "한국은행 부총재가 물가 흐름을 더 지켜봐야 한다고 말했다."),
    # High-risk negatives: polarity, chronology, number, event type, entity/action mismatches.
    ("n01_fx_number", False, "원·달러 환율은 1386.5원으로 마감했다.", "원·달러 환율은 1399.9원으로 마감했다."),
    ("n02_fx_direction", False, "원·달러 환율은 전 거래일보다 6.1원 내린 1386.5원으로 마감했다.", "원·달러 환율이 전 거래일보다 6.1원 올랐다."),
    ("n03_split_type", False, "카카오는 인적분할을 추진한다고 밝혔다.", "카카오가 물적분할을 추진한다."),
    ("n04_kbo_polarity", False, "한화는 이날 승리로 연패를 끊었다.", "한화가 연승을 이어갔다."),
    ("n05_innings_number", False, "양현종은 13시즌 연속 100이닝을 달성했다.", "양현종이 14시즌 연속 100이닝을 달성했다."),
    ("n06_future_completed", False, "정부는 9월 3일부터 새 제도를 시행한다고 밝혔다.", "정부가 새 제도를 이미 시행했다."),
    ("n07_contract_cancelled", False, "네오팩토리가 AI 공장 구축 사업을 15억달러에 수주했다.", "네오팩토리가 AI 공장 구축 사업 수주를 취소했다."),
    ("n08_price_direction", False, "생산자물가는 전월보다 0.4% 상승했다.", "생산자물가가 전월보다 0.4% 하락했다."),
    ("n09_launch_cancel", False, "테스트 기업은 2026년 8월 23일 신제품을 출시했다.", "테스트 기업이 신제품 출시를 취소했다."),
    ("n10_speaker", False, "한국은행 부총재는 물가 흐름을 더 지켜봐야 한다고 밝혔다.", "기획재정부 장관이 물가 흐름을 더 지켜봐야 한다고 밝혔다."),
)


def evaluate(model_id: str, *, route_id: str) -> dict[str, object]:
    verifier = LocalNliVerifier.transformers_model(model_id, verifier_id=route_id)
    rows: list[dict[str, object]] = []
    positive_correct = 0
    negative_correct = 0
    positive_total = 0
    negative_total = 0

    for case_id, expected, evidence, claim in CASES:
        check = verifier.verify(
            check_id=f"bench:{route_id}:{case_id}",
            claim_text=claim,
            evidence_text=evidence,
            evidence_ids=(f"ev:{case_id}",),
        )
        actual = check.entailed
        correct = actual is expected
        if expected:
            positive_total += 1
            positive_correct += int(correct)
        else:
            negative_total += 1
            negative_correct += int(correct)
        rows.append(
            {
                "case_id": case_id,
                "expected": expected,
                "actual": actual,
                "correct": correct,
                "error_code": check.error_code,
            }
        )

    accepted = negative_correct == negative_total and positive_correct >= 9
    return {
        "model_id": model_id,
        "positive_correct": positive_correct,
        "positive_total": positive_total,
        "negative_correct": negative_correct,
        "negative_total": negative_total,
        "accepted_for_secondary_failover": accepted,
        "cases": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="build/local-nli-benchmark.json")
    args = parser.parse_args()

    result = {
        "acceptance_rule": {
            "positive_min_correct": 9,
            "positive_total": 10,
            "negative_required_correct": 10,
            "negative_total": 10,
        },
        "primary": evaluate(LOCAL_NLI_MODEL, route_id="bench-mdeberta"),
        "fallback": evaluate(LOCAL_NLI_FALLBACK_MODEL, route_id="bench-minilm"),
    }
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    for key in ("primary", "fallback"):
        item = result[key]
        print(
            "LOCAL_NLI_BENCHMARK "
            f"route={key} "
            f"positive={item['positive_correct']}/{item['positive_total']} "
            f"negative={item['negative_correct']}/{item['negative_total']} "
            f"accepted={str(item['accepted_for_secondary_failover']).lower()}"
        )


if __name__ == "__main__":
    main()
