from __future__ import annotations

"""One-shot minimum qualification for an Event Understanding provider.

This is not production and does not fetch fresh news. It uses only the bounded historical exact-
source excerpt fixture. A failure marks the tested provider/model contract NOT_QUALIFIED; this
script is not a prompt-tuning loop.
"""

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

from insight_desk.core import (
    ArticleEventRole,
    EventUnderstandingRequest,
    SourceDocument,
    TopicRelation,
    UnderstandingStatus,
)
from insight_desk.event_understanding_adapter_v2 import StructuredJsonEventUnderstandingAdapter
from insight_desk.providers.gemini import GEMINI_FLASH_LITE, GeminiStructuredClient
from insight_desk.providers.groq import GROQ_20B, GroqFreeClient
from insight_desk.providers.transport import ProviderTransportError


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUALIFICATION = ROOT / "tests/fixtures/event_understanding_qualification_v1.json"
DEFAULT_SCOPES = ROOT / "config/semantic_topics_v2.json"
DEFAULT_REPORT = ROOT / "event-understanding-qualification.json"
PROVIDER_CHOICES = ("groq", "gemini")


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return value


def _scope_map(path: Path) -> dict[str, str]:
    payload = _load_json(path)
    result: dict[str, str] = {}
    for raw in payload.get("topics", []):
        if not isinstance(raw, dict):
            continue
        topic_id = raw.get("id")
        scope = raw.get("semantic_scope")
        if isinstance(topic_id, str) and isinstance(scope, str) and topic_id.strip() and scope.strip():
            result[topic_id] = scope.strip()
    return result


def _source_from_case(case: dict[str, object], replay_clock: datetime) -> SourceDocument:
    case_id = str(case["case_id"])
    body = str(case["source_excerpt"])
    return SourceDocument(
        source_id=f"qualification-source:{case_id}",
        candidate_ids=(str(case["candidate_id"]),),
        publisher=str(case["source_name"]),
        url=str(case["source_url"]),
        title=str(case["search_title"]),
        body=body,
        fetched_at=replay_clock,
        publication_time=replay_clock,
        retrieved_via="historical_exact_source_excerpt_qualification",
        content_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
    )


def _structured_text(result) -> str:
    values: list[str] = []
    for draft in result.event_drafts:
        values.extend((draft.actor, draft.action, draft.event_type))
        for optional in (
            draft.object,
            draft.event_time,
            draft.metric,
            draft.unit,
            draft.value,
            draft.attribution,
            draft.parent_event_hint,
        ):
            if optional:
                values.append(optional)
        values.extend(draft.participants)
    return "\n".join(values)


def _score(result, expected: dict[str, object]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    if result.status.value != str(expected["expected_status"]):
        failures.append("status")
    if len(result.event_drafts) < int(expected["event_drafts_min"]):
        failures.append("event_drafts_min")
    primary_direct = sum(
        1
        for draft in result.event_drafts
        if draft.article_role is ArticleEventRole.PRIMARY
        and draft.topic_relation is TopicRelation.DIRECT
        and draft.understanding_status is UnderstandingStatus.RESOLVED
    )
    if primary_direct < int(expected["primary_direct_min"]):
        failures.append("primary_direct_min")
    structured = _structured_text(result)
    required_literals = expected.get("required_structured_literals", [])
    if not isinstance(required_literals, list):
        raise ValueError("required_structured_literals must be an array")
    for literal in required_literals:
        if not isinstance(literal, str) or literal not in structured:
            failures.append("required_structured_literal")
            break
    parent_hint_count = sum(1 for draft in result.event_drafts if draft.parent_event_hint)
    if parent_hint_count < int(expected.get("parent_hint_min", 0)):
        failures.append("parent_hint_min")
    return not failures, failures


def _provider_configured(provider: str) -> bool:
    if provider == "groq":
        return GroqFreeClient.configured(model_id=GROQ_20B)
    if provider == "gemini":
        return GeminiStructuredClient.configured()
    raise ValueError(f"unsupported qualification provider: {provider}")


def _provider_client(provider: str):
    if provider == "groq":
        return GroqFreeClient.from_env(GROQ_20B), GROQ_20B
    if provider == "gemini":
        return GeminiStructuredClient.from_env(), GEMINI_FLASH_LITE
    raise ValueError(f"unsupported qualification provider: {provider}")


def _transport_failures(exc: ProviderTransportError) -> list[str]:
    failures = [f"provider_transport:{exc.failure_kind.value}"]
    if exc.status_code is not None:
        failures.append(f"http_status:{exc.status_code}")
    return failures


def qualify(
    *,
    provider: str,
    qualification_path: Path,
    scopes_path: Path,
    report_path: Path,
) -> int:
    if provider not in PROVIDER_CHOICES:
        raise ValueError(f"unsupported qualification provider: {provider}")

    qualification = _load_json(qualification_path)
    source_fixture_path = ROOT / str(qualification["source_fixture"])
    source_fixture = _load_json(source_fixture_path)
    scopes = _scope_map(scopes_path)
    source_cases = {
        str(case["case_id"]): case
        for case in source_fixture.get("cases", [])
        if isinstance(case, dict) and "case_id" in case
    }
    replay_clock = datetime.fromisoformat(str(source_fixture["replay_clock"]))

    if not _provider_configured(provider):
        model = GROQ_20B if provider == "groq" else GEMINI_FLASH_LITE
        report = {
            "status": "NOT_CONFIGURED",
            "provider": provider,
            "model": model,
            "evaluated_cases": 0,
            "passed_cases": 0,
            "source_mode": "historical_exact_source_excerpt_only",
            "full_production_correctness_claimed": False,
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
        return 2

    client, model = _provider_client(provider)
    adapter = StructuredJsonEventUnderstandingAdapter(
        client=client,
        engine_id=f"qualification:{provider}:{model}",
    )
    case_reports: list[dict[str, object]] = []

    for expected in qualification.get("cases", []):
        if not isinstance(expected, dict):
            continue
        case_id = str(expected["case_id"])
        raw_case = source_cases.get(case_id)
        if raw_case is None:
            case_reports.append({"case_id": case_id, "passed": False, "failures": ["missing_case"]})
            continue
        topic_id = str(raw_case["topic_id"])
        semantic_scope = scopes.get(topic_id)
        if semantic_scope is None:
            case_reports.append({"case_id": case_id, "passed": False, "failures": ["missing_scope"]})
            continue
        source = _source_from_case(raw_case, replay_clock)
        request = EventUnderstandingRequest(
            topic=topic_id,
            semantic_scope=semantic_scope,
            sources=(source,),
        )
        try:
            result = adapter.understand(request)
            passed, failures = _score(result, expected)
        except ProviderTransportError as exc:
            passed = False
            failures = _transport_failures(exc)
        except Exception as exc:  # contract/output failure is qualification failure; no fallback.
            passed = False
            failures = [f"provider_or_contract_error:{type(exc).__name__}"]
        case_reports.append(
            {
                "case_id": case_id,
                "passed": passed,
                "failures": failures,
            }
        )

    passed_cases = sum(1 for item in case_reports if item["passed"] is True)
    all_pass = bool(case_reports) and passed_cases == len(case_reports)
    report = {
        "status": "MINIMUM_COMPATIBILITY_PASS" if all_pass else "NOT_QUALIFIED",
        "provider": provider,
        "model": model,
        "evaluated_cases": len(case_reports),
        "passed_cases": passed_cases,
        "source_mode": "historical_exact_source_excerpt_only",
        "full_production_correctness_claimed": False,
        "cases": case_reports,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if all_pass else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=PROVIDER_CHOICES, default="groq")
    parser.add_argument("--qualification", type=Path, default=DEFAULT_QUALIFICATION)
    parser.add_argument("--scopes", type=Path, default=DEFAULT_SCOPES)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    return qualify(
        provider=args.provider,
        qualification_path=args.qualification,
        scopes_path=args.scopes,
        report_path=args.report,
    )


if __name__ == "__main__":
    sys.exit(main())
