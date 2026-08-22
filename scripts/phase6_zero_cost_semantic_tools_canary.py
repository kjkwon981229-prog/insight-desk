from __future__ import annotations

from datetime import datetime, timezone

import dateparser
from kiwipiepy import Kiwi
from rapidfuzz import fuzz, process


BASE = datetime(2026, 8, 23, 6, 0, tzinfo=timezone.utc)


def check_kiwi() -> None:
    kiwi = Kiwi()
    cases = (
        "잠실 한화 왕옌청 두산 곽빈 선발투수 예고",
        "원·달러 환율은 6.1원 내린 1386.5원에 마감했다.",
        "정부는 AI 규제안을 9월 3일부터 시행할 예정이라고 밝혔다.",
    )
    tokenized = [kiwi.tokenize(text) for text in cases]

    first_forms = [token.form for token in tokenized[0]]
    missing_names = [name for name in ("왕옌청", "곽빈") if name not in first_forms]
    if missing_names:
        raise AssertionError(f"Kiwi lost named participants: {missing_names}")

    for text, tokens in zip(cases, tokenized, strict=True):
        for token in tokens:
            if token.start < 0 or token.len <= 0 or token.start + token.len > len(text):
                raise AssertionError(
                    f"Kiwi emitted invalid source span: form={token.form!r} start={token.start} len={token.len}"
                )

    print(
        "ZERO_COST_TOOL_CANARY tool=kiwipiepy result=PASS "
        f"cases={len(cases)} names_preserved=2 source_spans_valid=true"
    )


def parsed_date(text: str) -> str | None:
    parsed = dateparser.parse(
        text,
        languages=["ko"],
        settings={
            "RELATIVE_BASE": BASE,
            "RETURN_AS_TIMEZONE_AWARE": True,
            "TIMEZONE": "UTC",
        },
    )
    return parsed.date().isoformat() if parsed is not None else None


def check_dateparser() -> None:
    hard_cases = {
        "오늘": "2026-08-23",
        "어제": "2026-08-22",
        "내일": "2026-08-24",
        "2026년 9월 3일": "2026-09-03",
    }
    failures: list[str] = []
    for text, expected in hard_cases.items():
        actual = parsed_date(text)
        if actual != expected:
            failures.append(f"{text}:{expected}->{actual}")
    if failures:
        raise AssertionError("dateparser hard-case failure: " + ", ".join(failures))

    diagnostic_cases = ("9월 3일", "오는 27일", "지난 12일")
    diagnostics = {text: parsed_date(text) for text in diagnostic_cases}
    print(
        "ZERO_COST_TOOL_CANARY tool=dateparser result=PASS "
        f"hard_cases={len(hard_cases)} diagnostics={diagnostics!r}"
    )


def check_rapidfuzz() -> None:
    aliases = (
        "SK하이닉스",
        "SK 하이닉스",
        "삼성전자",
        "한화 이글스",
        "두산 베어스",
    )
    query = "SK하이닉스"
    matches = process.extract(query, aliases, scorer=fuzz.WRatio, limit=3)
    if not matches or matches[0][0] != "SK하이닉스" or matches[0][1] != 100.0:
        raise AssertionError(f"RapidFuzz exact candidate retrieval failed: {matches!r}")

    spaced_score = fuzz.WRatio("SK하이닉스", "SK 하이닉스")
    unrelated_score = fuzz.WRatio("SK하이닉스", "두산 베어스")
    if spaced_score <= unrelated_score:
        raise AssertionError(
            f"RapidFuzz candidate ordering unsafe: spaced={spaced_score} unrelated={unrelated_score}"
        )

    print(
        "ZERO_COST_TOOL_CANARY tool=rapidfuzz result=PASS "
        f"exact_top=true spaced_score={spaced_score:.3f} unrelated_score={unrelated_score:.3f} "
        "authority=candidate_retrieval_only"
    )


def main() -> None:
    check_kiwi()
    check_dateparser()
    check_rapidfuzz()
    print(
        "ZERO_COST_TOOL_CANARY_SUMMARY result=PASS tools=3 external_api_calls=0 "
        "credentials_required=0 paid_paths=0"
    )


if __name__ == "__main__":
    main()
