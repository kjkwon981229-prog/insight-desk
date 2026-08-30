from __future__ import annotations

"""Active Event Understanding provider qualification runner for corrected protocol V5.

V4 remains frozen historical evidence. V5 reuses the exact V4 source handoff, semantic scorer,
outcome classifier, and bounded diagnostics, while using the V5 model-facing contract that makes
deterministic core invariants explicit before provider output is judged.
"""

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

from insight_desk.core import EventUnderstandingRequest
from insight_desk.event_understanding_adapter_v2 import EventUnderstandingAdapterError
from insight_desk.event_understanding_adapter_v4 import StructuredJsonEventUnderstandingAdapterV4
from insight_desk.providers.transport import ProviderTransportError
from scripts import qualify_event_understanding_provider as historical_v3
from scripts import qualify_event_understanding_provider_v4 as v4


ROOT = v4.ROOT
DEFAULT_QUALIFICATION = ROOT / "tests/fixtures/event_understanding_qualification_v5.json"
DEFAULT_SCOPES = v4.DEFAULT_SCOPES
DEFAULT_REPORT = v4.DEFAULT_REPORT
PROVIDER_CHOICES = v4.PROVIDER_CHOICES
MINIMUM_COMPATIBILITY_PASS = v4.MINIMUM_COMPATIBILITY_PASS
NOT_QUALIFIED = v4.NOT_QUALIFIED
QUALIFICATION_BLOCKED_TRANSIENT = v4.QUALIFICATION_BLOCKED_TRANSIENT
QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE = v4.QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE

# Frozen provider-neutral semantics/lifecycle. Candidate wrappers may scope-register a new provider
# exactly as under V4, but V5 itself does not add or call a provider.
_score = v4._score
_qualification_outcome = v4._qualification_outcome
_qualification_contract_metadata = v4._qualification_contract_metadata
_provider_model = v4._provider_model
_provider_configured = v4._provider_configured
_provider_client = v4._provider_client
_adapter_failures = v4._adapter_failures


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
    if qualification.get("schema_version") != 5:
        raise ValueError("active V5 runner requires qualification schema_version 5")
    if qualification.get("structured_output_schema") != "event_understanding_schema_v4":
        raise ValueError("active V5 runner requires event_understanding_schema_v4")

    source_fixture_path = ROOT / str(qualification["source_fixture"])
    source_fixture = historical_v3._load_json(source_fixture_path)
    scopes = historical_v3._scope_map(scopes_path)
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
    adapter = StructuredJsonEventUnderstandingAdapterV4(
        client=client,
        engine_id=f"qualification-v5:{provider}:{model}",
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
        source = historical_v3._source_from_case(raw_case, replay_clock)
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
            failures = historical_v3._transport_failures(exc)
        except EventUnderstandingAdapterError as exc:
            passed = False
            failures = _adapter_failures(exc)
        except Exception as exc:  # bounded diagnostics only; no raw provider/source payload.
            passed = False
            failures = historical_v3._qualification_failure_codes(exc)
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
