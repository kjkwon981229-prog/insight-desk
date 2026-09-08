from __future__ import annotations

"""Post-merge Event Understanding provider qualification protocol V6.

V6 preserves the V5 model-facing Event Understanding contract and exact evidence binding, but
expands the benchmark beyond the four-case minimum. It adds frozen post-merge regression cases for
article centrality/background handling and requires explicit human review for semantic failures
that cannot be safely reduced to lexical rules.

This runner is qualification-only. It never wires a provider into production.
"""

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

from insight_desk.core import (
    ArticleEventRole,
    EventUnderstandingRequest,
    TopicRelation,
    UnderstandingStatus,
)
from insight_desk.event_understanding_adapter_v2 import EventUnderstandingAdapterError
from insight_desk.event_understanding_adapter_v4 import StructuredJsonEventUnderstandingAdapterV4
from insight_desk.providers.groq import GROQ_120B, GroqFreeClient
from insight_desk.providers.transport import ProviderTransportError
from scripts import qualify_event_understanding_provider as historical_v3
from scripts import qualify_event_understanding_provider_v5 as v5


ROOT = v5.ROOT
DEFAULT_QUALIFICATION = ROOT / "tests/fixtures/event_understanding_qualification_v6.json"
DEFAULT_SCOPES = v5.DEFAULT_SCOPES
DEFAULT_REPORT = ROOT / "event-understanding-qualification-v6.json"
PROVIDER_CHOICES = tuple(dict.fromkeys((*v5.PROVIDER_CHOICES, "groq_120b")))

AUTOMATIC_REGRESSION_PASS = "AUTOMATIC_REGRESSION_PASS"
NOT_QUALIFIED = v5.NOT_QUALIFIED
QUALIFICATION_BLOCKED_TRANSIENT = v5.QUALIFICATION_BLOCKED_TRANSIENT
QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE = v5.QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE


def _provider_model(provider: str) -> str:
    if provider == "groq_120b":
        return GROQ_120B
    return v5._provider_model(provider)


def _provider_configured(provider: str) -> bool:
    if provider == "groq_120b":
        return GroqFreeClient.configured(model_id=GROQ_120B)
    return v5._provider_configured(provider)


def _provider_client(provider: str):
    if provider == "groq_120b":
        return GroqFreeClient.from_env(GROQ_120B), GROQ_120B
    return v5._provider_client(provider)


def _load_source_cases(qualification: dict[str, object]) -> dict[str, tuple[dict[str, object], datetime]]:
    paths = qualification.get("source_fixtures")
    if not isinstance(paths, list) or not paths or any(not isinstance(item, str) for item in paths):
        raise ValueError("V6 source_fixtures must be a non-empty string array")
    cases: dict[str, tuple[dict[str, object], datetime]] = {}
    for relative in paths:
        fixture = historical_v3._load_json(ROOT / relative)
        replay_clock = datetime.fromisoformat(str(fixture["replay_clock"]))
        for raw in fixture.get("cases", []):
            if not isinstance(raw, dict) or "case_id" not in raw:
                continue
            case_id = str(raw["case_id"])
            if case_id in cases:
                raise ValueError(f"duplicate V6 source case_id: {case_id}")
            cases[case_id] = (raw, replay_clock)
    return cases


def _string_array(value: object, *, name: str, allow_empty: bool = True) -> tuple[str, ...]:
    if value is None and allow_empty:
        return ()
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{name} must be a string array")
    result = tuple(item.strip() for item in value if item.strip())
    if not allow_empty and not result:
        raise ValueError(f"{name} must contain at least one value")
    return result


def _primary_direct_drafts(result) -> tuple[object, ...]:
    return tuple(
        draft
        for draft in result.event_drafts
        if draft.article_role is ArticleEventRole.PRIMARY
        and draft.topic_relation is TopicRelation.DIRECT
        and draft.understanding_status is UnderstandingStatus.RESOLVED
    )


def _score_v6(
    request: EventUnderstandingRequest,
    result,
    expected: dict[str, object],
) -> tuple[bool, list[str]]:
    """Score frozen semantic structure without creating a production semantic detector.

    Context gold is an annotation on this benchmark only: exact evidence passages known to be
    background/context may not be promoted into a resolved PRIMARY+DIRECT draft. Free-form action
    meaning is not regex-scored; cases needing that judgment are emitted for human semantic review.
    """

    failures: list[str] = []
    if result.status.value != str(expected["expected_status"]):
        failures.append("status")

    drafts = result.event_drafts
    if len(drafts) < int(expected.get("event_drafts_min", 0)):
        failures.append("event_drafts_min")
    if "event_drafts_max" in expected and len(drafts) > int(expected["event_drafts_max"]):
        failures.append("event_drafts_max")

    primary_direct = _primary_direct_drafts(result)
    if len(primary_direct) < int(expected.get("primary_direct_min", 0)):
        failures.append("primary_direct_min")
    if "primary_direct_max" in expected and len(primary_direct) > int(expected["primary_direct_max"]):
        failures.append("primary_direct_max")

    expected_events_raw = expected.get("expected_events", [])
    if not isinstance(expected_events_raw, list) or any(not isinstance(item, dict) for item in expected_events_raw):
        raise ValueError("expected_events must be an object array")
    if expected_events_raw and not historical_v3._distinct_expected_events_match(
        request,
        drafts,
        list(expected_events_raw),
    ):
        failures.append("expected_event_match")

    parent_hint_count = sum(1 for draft in drafts if draft.parent_event_hint)
    if parent_hint_count < int(expected.get("parent_hint_min", 0)):
        failures.append("parent_hint_min")

    context_literals = _string_array(
        expected.get("context_evidence_literals"),
        name="context_evidence_literals",
    )
    if context_literals:
        context_promoted = False
        for draft in primary_direct:
            evidence_text = historical_v3._draft_evidence_text(request, draft)
            if any(literal in evidence_text for literal in context_literals):
                context_promoted = True
                break
        if context_promoted:
            failures.append("context_promoted_primary")

    return not failures, failures


def _manual_review_snapshot(request: EventUnderstandingRequest, result) -> list[dict[str, object]]:
    snapshots: list[dict[str, object]] = []
    for draft in result.event_drafts:
        snapshots.append(
            {
                "actor": draft.actor,
                "action": draft.action,
                "object": draft.object,
                "event_type": draft.event_type,
                "article_role": draft.article_role.value,
                "topic_relation": draft.topic_relation.value,
                "understanding_status": draft.understanding_status.value,
                "evidence_text": historical_v3._draft_evidence_text(request, draft),
            }
        )
    return snapshots


def _qualification_outcome(case_reports: list[dict[str, object]]) -> str:
    if case_reports and all(item.get("passed") is True for item in case_reports):
        return AUTOMATIC_REGRESSION_PASS
    historical_outcome = v5._qualification_outcome(case_reports)
    if historical_outcome in {
        QUALIFICATION_BLOCKED_TRANSIENT,
        QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE,
    }:
        return historical_outcome
    return NOT_QUALIFIED


def qualify(
    *,
    provider: str,
    qualification_path: Path,
    scopes_path: Path,
    report_path: Path,
) -> int:
    if provider not in PROVIDER_CHOICES:
        raise ValueError(f"unsupported qualification provider: {provider}")

    qualification = historical_v3._load_json(qualification_path)
    if qualification.get("schema_version") != 6:
        raise ValueError("active V6 runner requires qualification schema_version 6")
    if qualification.get("structured_output_schema") != "event_understanding_schema_v4":
        raise ValueError("active V6 runner requires event_understanding_schema_v4")

    source_cases = _load_source_cases(qualification)
    scopes = historical_v3._scope_map(scopes_path)
    model = _provider_model(provider)

    if not _provider_configured(provider):
        report = {
            "status": "NOT_CONFIGURED",
            "provider": provider,
            "model": model,
            "qualification_protocol": 6,
            "core_contract": qualification.get("core_contract"),
            "structured_output_schema": qualification.get("structured_output_schema"),
            "evaluated_cases": 0,
            "passed_cases": 0,
            "source_mode": "historical_exact_plus_frozen_postmerge_regressions",
            "automatic_regression_passed": False,
            "manual_semantic_review_required": True,
            "provider_selection_eligible": False,
            "production_wired": False,
            "full_production_correctness_claimed": False,
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
        return 2

    client, model = _provider_client(provider)
    adapter = StructuredJsonEventUnderstandingAdapterV4(
        client=client,
        engine_id=f"qualification-v6:{provider}:{model}",
    )
    case_reports: list[dict[str, object]] = []
    manual_review_cases: list[dict[str, object]] = []

    for expected in qualification.get("cases", []):
        if not isinstance(expected, dict):
            continue
        case_id = str(expected["case_id"])
        source_entry = source_cases.get(case_id)
        if source_entry is None:
            case_reports.append({"case_id": case_id, "passed": False, "failures": ["missing_case"]})
            continue
        raw_case, replay_clock = source_entry
        topic_id = str(raw_case["topic_id"])
        semantic_scope = scopes.get(topic_id)
        if semantic_scope is None:
            case_reports.append({"case_id": case_id, "passed": False, "failures": ["missing_scope"]})
            continue

        source = historical_v3._source_from_case(raw_case, replay_clock)
        request = EventUnderstandingRequest(
            topic=topic_id,
            semantic_scope=semantic_scope,
            sources=(source,),
        )
        result = None
        try:
            result = adapter.understand(request)
            passed, failures = _score_v6(request, result, expected)
        except ProviderTransportError as exc:
            passed = False
            failures = historical_v3._transport_failures(exc)
        except EventUnderstandingAdapterError as exc:
            passed = False
            failures = v5._adapter_failures(exc)
        except Exception as exc:
            passed = False
            failures = historical_v3._qualification_failure_codes(exc)

        case_reports.append({"case_id": case_id, "passed": passed, "failures": failures})
        if expected.get("manual_semantic_review_required") is True:
            manual_review_cases.append(
                {
                    "case_id": case_id,
                    "question": str(expected.get("manual_review_question", "Review semantic fidelity.")),
                    "automatic_case_passed": passed,
                    "drafts": _manual_review_snapshot(request, result) if result is not None else [],
                }
            )

    passed_cases = sum(1 for item in case_reports if item["passed"] is True)
    outcome = _qualification_outcome(case_reports)
    report = {
        "status": outcome,
        "provider": provider,
        "model": model,
        "qualification_protocol": 6,
        "core_contract": qualification.get("core_contract"),
        "structured_output_schema": qualification.get("structured_output_schema"),
        "evaluated_cases": len(case_reports),
        "passed_cases": passed_cases,
        "source_mode": "historical_exact_plus_frozen_postmerge_regressions",
        "automatic_regression_passed": outcome == AUTOMATIC_REGRESSION_PASS,
        "manual_semantic_review_required": bool(manual_review_cases),
        "manual_review_cases": manual_review_cases,
        "provider_selection_eligible": False,
        "production_wired": False,
        "full_production_correctness_claimed": False,
        "cases": case_reports,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if outcome == AUTOMATIC_REGRESSION_PASS:
        return 0
    if outcome == QUALIFICATION_BLOCKED_TRANSIENT:
        return 3
    if outcome == QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE:
        return 4
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=PROVIDER_CHOICES, default="groq_120b")
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
