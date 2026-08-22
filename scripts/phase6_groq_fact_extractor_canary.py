from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from insight_desk.core import RawArticle, SourceProvenance, TemporalState
from insight_desk.semantic import Groq20BFactExtractor, SemanticPipeline


ROOT = Path(__file__).resolve().parents[1]
FIXED_FETCHED_AT = datetime(2026, 8, 23, 4, 0, tzinfo=timezone.utc)
MAX_PROVIDER_CALLS = 10


def load_cases(path: str) -> dict[str, dict]:
    payload = json.loads((ROOT / path).read_text(encoding="utf-8"))
    return {case["id"]: case for case in payload["cases"]}


RUN90 = load_cases("benchmarks/run90_temporal.json")
RUN95 = load_cases("benchmarks/run94_95_semantic.json")
RUN97 = load_cases("benchmarks/run97_generation.json")


def article_from_case(case_id: str, case: dict, *, topic_id: str) -> RawArticle:
    source = case["input"]
    parts = []
    for key in ("title", "lead"):
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    body = "\n".join(parts)
    if not body:
        raise ValueError(f"{case_id}: benchmark case has no title/lead evidence")

    published_raw = source.get("published_at")
    published_at = datetime.fromisoformat(published_raw) if published_raw else None
    return RawArticle(
        article_id=f"benchmark:{case_id}",
        provenance=SourceProvenance(
            source_id="benchmark:clean-room",
            source_name="Insight Desk clean-room benchmark",
            url=f"https://example.invalid/benchmark/{case_id}",
            retrieved_via="locked_benchmark_fixture",
            fetched_at=FIXED_FETCHED_AT,
            published_at=published_at,
        ),
        title=source.get("title") or case_id,
        body=body,
        topic_ids=(topic_id,),
        query=source.get("query"),
    )


def flattened(result) -> str:
    values: list[str] = []
    for fact in result.facts:
        for value in (
            fact.subject,
            fact.action,
            fact.object,
            fact.event_date,
            fact.location,
            fact.cause,
        ):
            if value:
                values.append(str(value))
        values.extend(fact.participants)
    return " | ".join(values)


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise AssertionError(detail)


def require_fact(result, case_id: str) -> None:
    require(bool(result.facts), f"{case_id}: expected at least one explicit event fact")


def require_temporal(result, case_id: str, expected: TemporalState) -> None:
    require_fact(result, case_id)
    states = {fact.temporal_state for fact in result.facts}
    require(
        expected in states,
        f"{case_id}: expected temporal_state={expected.value}, got={sorted(str(x) for x in states)}",
    )


def require_literals(result, case_id: str, *literals: str) -> None:
    text = flattened(result)
    for literal in literals:
        require(literal in text, f"{case_id}: missing required concept/literal: {literal}")


def check_resumed(result) -> None:
    require_temporal(result, "run90-lifecycle-resumed", TemporalState.RESUMED)


def check_seoul_heat(result) -> None:
    case_id = "run90-seoul-heat"
    require_temporal(result, case_id, TemporalState.CANCELLED)
    require_literals(result, case_id, "서울", "폭염")


def check_busan_rain(result) -> None:
    case_id = "run90-busan-rain"
    require_temporal(result, case_id, TemporalState.CANCELLED)
    require_literals(result, case_id, "부산")


def check_day_12(result) -> None:
    case_id = "run90-fixture-day-12"
    require_temporal(result, case_id, TemporalState.CANCELLED)
    require_literals(result, case_id, "12일", "한화", "두산", "서울")


def check_day_13(result) -> None:
    case_id = "run90-fixture-day-13"
    require_temporal(result, case_id, TemporalState.CANCELLED)
    require_literals(result, case_id, "13일", "한화", "두산", "서울")


def check_context_market(result) -> None:
    case_id = "run95-context-market"
    require(result.facts == (), f"{case_id}: bare market value must not become an invented event action")


def check_missing_lineup(result) -> None:
    case_id = "run95-malformed-lineup"
    require_fact(result, case_id)
    text = flattened(result)
    require("한화 이글스와과" not in text, f"{case_id}: malformed Korean regression returned")
    require("두산 베어스의가" not in text, f"{case_id}: malformed Korean regression returned")
    # The source contains no starter names. Source-literal subject/object/participant gates prevent
    # the extractor from introducing an unseen starter name through those semantic slots.


def check_explicit_lineup(result) -> None:
    case_id = "run95-explicit-lineup"
    require_fact(result, case_id)
    require_literals(result, case_id, "한화", "두산", "왕옌청", "곽빈")
    text = flattened(result)
    require("선발" in text and "예고" in text, f"{case_id}: explicit lineup action was not preserved")
    subjects = {fact.subject for fact in result.facts}
    require("한화" in subjects, f"{case_id}: Hanwha subject absorbed location/context: {sorted(subjects)}")
    require("두산" in subjects, f"{case_id}: Doosan subject absorbed location/context: {sorted(subjects)}")


def check_groundbreaking_future(result) -> None:
    case_id = "run97-groundbreaking-future"
    require_temporal(result, case_id, TemporalState.PLANNED)
    require_literals(result, case_id, "SK하이닉스", "미국 인디애나", "HBM 패키징 공장", "27일")
    require(
        TemporalState.COMPLETED not in {fact.temporal_state for fact in result.facts},
        f"{case_id}: future event shifted to completed",
    )


def check_departure_announcement(result) -> None:
    case_id = "run97-departure-announcement"
    require_temporal(result, case_id, TemporalState.ANNOUNCED_PROSPECTIVE)
    require_literals(result, case_id, "트와이스 채영", "JYP")
    require(
        TemporalState.COMPLETED not in {fact.temporal_state for fact in result.facts},
        f"{case_id}: announced departure shifted to completed",
    )


CASES: tuple[tuple[str, dict, str, Callable], ...] = (
    ("run90-lifecycle-resumed", RUN90["run90-lifecycle-resumed"], "kbo_hanwha", check_resumed),
    ("run90-seoul-heat", RUN90["run90-seoul-heat"], "kbo_hanwha", check_seoul_heat),
    ("run90-busan-rain", RUN90["run90-busan-rain"], "kbo_hanwha", check_busan_rain),
    ("run90-fixture-day-12", RUN90["run90-fixture-day-12"], "kbo_hanwha", check_day_12),
    ("run90-fixture-day-13", RUN90["run90-fixture-day-13"], "kbo_hanwha", check_day_13),
    ("run95-context-market", RUN95["run95-context-market"], "economy", check_context_market),
    ("run95-malformed-lineup", RUN95["run95-malformed-lineup"], "kbo_hanwha", check_missing_lineup),
    ("run95-explicit-lineup", RUN95["run95-explicit-lineup"], "kbo_hanwha", check_explicit_lineup),
    ("run97-groundbreaking-future", RUN97["run97-groundbreaking-future"], "ai_tech", check_groundbreaking_future),
    ("run97-departure-announcement", RUN97["run97-departure-announcement"], "kpop", check_departure_announcement),
)


def main() -> int:
    require(len(CASES) <= MAX_PROVIDER_CALLS, "canary exceeds bounded provider-call budget")
    extractor = Groq20BFactExtractor.from_env(delay_seconds=2.1)
    pipeline = SemanticPipeline()
    summaries: list[dict[str, object]] = []

    for case_id, case, topic_id, checker in CASES:
        raw = article_from_case(case_id, case, topic_id=topic_id)
        result = pipeline.extract_article(raw, topic_id=topic_id, extractor=extractor)
        checker(result)
        summaries.append({"case_id": case_id, "status": "pass", "fact_count": len(result.facts)})
        print(json.dumps(summaries[-1], ensure_ascii=False, sort_keys=True))

    final = {
        "status": "pass",
        "provider_calls": len(CASES),
        "case_count": len(CASES),
        "extractor_id": extractor.extractor_id,
        "logged_article_bodies": False,
        "logged_credentials": False,
    }
    print(json.dumps(final, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
