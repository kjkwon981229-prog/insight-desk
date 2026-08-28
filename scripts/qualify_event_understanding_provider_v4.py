from __future__ import annotations

"""Active Event Understanding provider qualification runner for protocol V4.

Protocol V3 remains frozen in ``qualify_event_understanding_provider.py`` for historical evidence.
V4 reuses the exact V3 provider inventory, source handoff, semantic scorer, outcome classifier, and
bounded diagnostics. The only changed provider contract is evidence handoff: the semantic owner
selects source_id/field/verbatim text and the V4 adapter binds the unique exact source range.
"""

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

from insight_desk.core import EventUnderstandingRequest
from insight_desk.event_understanding_adapter_v3 import (
    EventUnderstandingAdapterError,
    StructuredJsonEventUnderstandingAdapterV3,
)
from insight_desk.providers.transport import ProviderTransportError
from scripts import qualify_event_understanding_provider as v3


ROOT = v3.ROOT
DEFAULT_QUALIFICATION = ROOT / "tests/fixtures/event_understanding_qualification_v4.json"
DEFAULT_SCOPES = v3.DEFAULT_SCOPES
DEFAULT_REPORT = v3.DEFAULT_REPORT
PROVIDER_CHOICES = v3.PROVIDER_CHOICES
MINIMUM_COMPATIBILITY_PASS = v3.MINIMUM_COMPATIBILITY_PASS
NOT_QUALIFIED = v3.NOT_QUALIFIED
QUALIFICATION_BLOCKED_TRANSIENT = v3.QUALIFICATION_BLOCKED_TRANSIENT
QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE = v3.QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE

# Re-export the frozen provider-neutral scorer/lifecycle helpers for tests and candidate wrappers.
_score = v3._score
_qualification_outcome = v3._qualification_outcome
_qualification_contract_metadata = v3._qualification_contract_metadata
_provider_model = v3._provider_model
_provider_configured = v3._provider_configured
_provider_client = v3._provider_client


def qualify(
    *,
    provider: str,
    qualification_path: Path,
    scopes_path: Path,
    report_path: Path,
) -> int:
    if provider not in PROVIDER_CHOICES:
        raise ValueError(f"unsupported qualification provider: {provider}")

    qualification = v3._load_json(qualification_path)
    if qualification.get("schema_version") != 4:
        raise ValueError("active V4 runner requires qualification schema_version 4")
    if qualification.get("structured_output_schema") != "event_understanding_schema_v3":
        raise ValueError("active V4 runner requires event_understanding_schema_v3")

    source_fixture_path = ROOT / str(qualification["source_fixture"])
    source_fixture = v3._load_json(source_fixture_path)
    scopes = v3._scope_map(scopes_path)
    source_cases = {
        str(case["case_id"]): case
        for case in source_fixture.get("cases", [])
        if isinstance(case, dict) and "case_id" in case
    }
    replay_clock = datetime.fromisoformat(str(source_fixture["replay_clock"]))

    if not _provider_configured(provider):
        report = {
            "status": "NOT_CONFIGURED",
            "provider": provider,
            "model": _provider_model(provider),
            **_qualification_contract_metadata(qualification),
            "evaluated_cases": 0,
            "passed_cases": 0,
            "source_mode": "historical_exact_source_excerpt_only",
            "full_production_correctness_claimed": False,
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
        return 2

    client, model = _provider_client(provider)
    adapter = StructuredJsonEventUnderstandingAdapterV3(
        client=client,
        engine_id=f"qualification-v4:{provider}:{model}",
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
        source = v3._source_from_case(raw_case, replay_clock)
        request = EventUnderstandingRequest(
            topic=topic_id,
            semantic_scope=semantic_scope,
            sources=(source,),
        )
        try:
            result = adapter.understand(request)
            passed, failures = _score(request, result, expected)
        except ProviderTransportError as exc:
            passed = False
            failures = v3._transport_failures(exc)
        except EventUnderstandingAdapterError as exc:
            passed = False
            failures = [f"adapter_contract:{exc.failure_code}"]
        except Exception as exc:  # bounded diagnostic only; no raw exception/source/provider payload.
            passed = False
            failures = v3._qualification_failure_codes(exc)
        case_reports.append(
            {
                "case_id": case_id,
                "passed": passed,
                "failures": failures,
            }
        )

    passed_cases = sum(1 for item in case_reports if item["passed"] is True)
    outcome = _qualification_outcome(case_reports)
    report = {
        "status": outcome,
        "provider": provider,
        "model": model,
        **_qualification_contract_metadata(qualification),
        "evaluated_cases": len(case_reports),
        "passed_cases": passed_cases,
        "source_mode": "historical_exact_source_excerpt_only",
        "full_production_correctness_claimed": False,
        "cases": case_reports,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if outcome == MINIMUM_COMPATIBILITY_PASS:
        return 0
    if outcome == QUALIFICATION_BLOCKED_TRANSIENT:
        return 3
    if outcome == QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE:
        return 4
    return 1


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
