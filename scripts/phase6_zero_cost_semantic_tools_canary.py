from __future__ import annotations

from datetime import datetime, timezone

import dateparser
from kiwipiepy import Kiwi
from rapidfuzz import fuzz, process


BASE = datetime(2026, 8, 23, 6, 0, tzinfo=timezone.utc)


def _surface_span_is_covered(text: str, tokens, surface: str) -> bool:
    start = text.find(surface)
    if start < 0:
        return False
    end = start + len(surface)
    covered: set[int] = set()
    for token in tokens:
        token_start = token.start
        token_end = token.start + token.len
        for index in range(max(start, token_start), min(end, token_end)):
            covered.add(index)
    return covered == set(range(start, end))


def check_kiwi() -> None:
    kiwi = Kiwi()
    cases = (
        "잠실 한화 왕옌청 두산 곽빈 선발투수 예고",
        "원·달러 환율은 6.1원 내린 1386.5원에 마감했다.",
        "정부는 AI 규제안을 9월 3일부터 시행할 예정이라고 밝혔다.",
    )
    tokenized = [kiwi.tokenize(text) for text in cases]
    for text, tokens in zip(cases, tokenized, strict=True):
        for token in tokens:
            if token.start < 0 or token.len <= 0 or token.start + token.len > len(text):
                raise AssertionError(
                    f"Kiwi emitted invalid source span: form={token.form!r} start={token.start} len={token.len}"
                )
    first_text = cases[0]
    first_tokens = tokenized[0]
    uncovered_names = [
        name for name in ("왕옌청", "곽빈") if not _surface_span_is_covered(first_text, first_tokens, name)
    ]
    if uncovered_names:
        raise AssertionError(f"Kiwi source-offset coverage lost named surfaces: {uncovered_names}")
    first_forms = [token.form for token in first_tokens]
    whole_token_names = [name for name in ("왕옌청", "곽빈") if name in first_forms]
    split_token_names = [name for name in ("왕옌청", "곽빈") if name not in first_forms]
    print(
        "ZERO_COST_TOOL_CANARY tool=kiwipiepy result=PASS "
        f"cases={len(cases)} named_surface_coverage=2 whole_tokens={whole_token_names!r} "
        f"split_tokens={split_token_names!r} source_spans_valid=true "
        "authority=morphology_and_offsets_only"
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


def diagnose_dateparser() -> bool:
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
    diagnostics = {
        text: parsed_date(text) for text in ("9월 3일", "오는 27일", "지난 12일")
    }
    if failures:
        print(
            "ZERO_COST_TOOL_CANARY tool=dateparser result=REJECT "
            f"hard_failures={failures!r} diagnostics={diagnostics!r} "
            "reason=korean_news_date_reliability"
        )
        return False
    print(
        "ZERO_COST_TOOL_CANARY tool=dateparser result=PASS "
        f"hard_cases={len(hard_cases)} diagnostics={diagnostics!r} "
        "authority=date_normalization_helper_only"
    )
    return True


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
    dateparser_pass = diagnose_dateparser()
    check_rapidfuzz()
    if dateparser_pass:
        raise AssertionError("dateparser unexpectedly passed after locked rejection diagnostic")
    print(
        "ZERO_COST_TOOL_CANARY_SUMMARY result=PASS accepted=kiwipiepy,rapidfuzz "
        "rejected=dateparser external_api_calls=0 credentials_required=0 paid_paths=0"
    )


if __name__ == "__main__":
    main()
