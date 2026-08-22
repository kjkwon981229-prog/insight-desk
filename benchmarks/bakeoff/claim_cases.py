from __future__ import annotations

from typing import Any


CLAIM_CASES: list[dict[str, Any]] = [
    {
        "id": "run97-groundbreaking-future-supported",
        "source_case": "run97-groundbreaking-future",
        "premise": "SK하이닉스, 미국 인디애나 HBM 패키징 공장 착공식. SK하이닉스가 27일 착공식을 연다.",
        "hypothesis": "SK하이닉스는 27일 미국 인디애나 HBM 패키징 공장 착공식을 열 예정이다.",
        "expected_entailed": True,
    },
    {
        "id": "run97-groundbreaking-future-completed",
        "source_case": "run97-groundbreaking-future",
        "premise": "SK하이닉스, 미국 인디애나 HBM 패키징 공장 착공식. SK하이닉스가 27일 착공식을 연다.",
        "hypothesis": "SK하이닉스는 미국 인디애나 HBM 패키징 공장 착공을 이미 완료했다.",
        "expected_entailed": False,
    },
    {
        "id": "run97-groundbreaking-completed-supported",
        "source_case": "run97-groundbreaking-completed",
        "premise": "SK하이닉스, 미국 인디애나 HBM 패키징 공장 착공식. SK하이닉스가 착공식을 열었다.",
        "hypothesis": "SK하이닉스는 미국 인디애나 HBM 패키징 공장 착공식을 열었다.",
        "expected_entailed": True,
    },
    {
        "id": "run97-groundbreaking-completed-planned",
        "source_case": "run97-groundbreaking-completed",
        "premise": "SK하이닉스, 미국 인디애나 HBM 패키징 공장 착공식. SK하이닉스가 착공식을 열었다.",
        "hypothesis": "SK하이닉스는 아직 착공식을 열지 않았고 앞으로 열 예정이다.",
        "expected_entailed": False,
    },
    {
        "id": "run97-departure-announcement-supported",
        "source_case": "run97-departure-announcement",
        "premise": "트와이스 채영, 14년 만에 JYP 떠난다. 트와이스 채영이 떠난다고 밝혔다.",
        "hypothesis": "트와이스 채영은 JYP를 떠난다고 밝혔다.",
        "expected_entailed": True,
    },
    {
        "id": "run97-departure-announcement-completed",
        "source_case": "run97-departure-announcement",
        "premise": "트와이스 채영, 14년 만에 JYP 떠난다. 트와이스 채영이 떠난다고 밝혔다.",
        "hypothesis": "트와이스 채영은 이미 JYP를 떠났다.",
        "expected_entailed": False,
    },
    {
        "id": "run97-investment-planned-supported",
        "source_case": "run97-investment-planned",
        "premise": "A사, AI 사업 투자. A사가 투자하기로 했다.",
        "hypothesis": "A사는 AI 사업에 투자하기로 했다.",
        "expected_entailed": True,
    },
    {
        "id": "run97-investment-planned-completed",
        "source_case": "run97-investment-planned",
        "premise": "A사, AI 사업 투자. A사가 투자하기로 했다.",
        "hypothesis": "A사는 AI 사업 투자를 이미 완료했다.",
        "expected_entailed": False,
    },
    {
        "id": "run97-investment-completed-supported",
        "source_case": "run97-investment-completed",
        "premise": "A사, AI 사업 투자. A사가 투자했다.",
        "hypothesis": "A사는 AI 사업에 투자했다.",
        "expected_entailed": True,
    },
    {
        "id": "run97-investment-completed-planned",
        "source_case": "run97-investment-completed",
        "premise": "A사, AI 사업 투자. A사가 투자했다.",
        "hypothesis": "A사는 아직 AI 사업에 투자하지 않았고 앞으로 투자할 예정이다.",
        "expected_entailed": False,
    },
    {
        "id": "run90-seoul-heat-supported",
        "source_case": "run90-seoul-heat",
        "premise": "서울 프로야구 경기 폭염으로 취소. 서울 경기가 폭염 영향으로 취소됐다.",
        "hypothesis": "서울 프로야구 경기는 폭염 때문에 취소됐다.",
        "expected_entailed": True,
    },
    {
        "id": "run90-seoul-heat-wrong-location",
        "source_case": "run90-seoul-heat",
        "premise": "서울 프로야구 경기 폭염으로 취소. 서울 경기가 폭염 영향으로 취소됐다.",
        "hypothesis": "부산 프로야구 경기가 폭염 때문에 취소됐다.",
        "expected_entailed": False,
    },
    {
        "id": "run90-busan-rain-supported",
        "source_case": "run90-busan-rain",
        "premise": "부산 프로야구 경기 우천 취소. 부산 경기가 비로 취소됐다.",
        "hypothesis": "부산 프로야구 경기는 비 때문에 취소됐다.",
        "expected_entailed": True,
    },
    {
        "id": "run90-busan-rain-wrong-cause",
        "source_case": "run90-busan-rain",
        "premise": "부산 프로야구 경기 우천 취소. 부산 경기가 비로 취소됐다.",
        "hypothesis": "부산 프로야구 경기는 폭염 때문에 취소됐다.",
        "expected_entailed": False,
    },
]


def as_provider_cases() -> list[dict[str, Any]]:
    return [
        {
            "id": case["id"],
            "task": "CLAIM_VERIFY",
            "input": {
                "premise": case["premise"],
                "hypothesis": case["hypothesis"],
            },
            "expected": {"entailed": case["expected_entailed"]},
            "source_case": case["source_case"],
        }
        for case in CLAIM_CASES
    ]
