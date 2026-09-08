from __future__ import annotations

"""One-shot minimum qualification for an Event Understanding provider.

This is not production and does not fetch fresh news. It uses only the bounded historical exact-
source excerpt fixture. A provider/model contract is evaluated once against the active provider-
neutral qualification protocol. Missing credentials and provider availability failures are kept
separate from definitive semantic/contract qualification failures.
"""

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

from insight_desk.core import (
    ArticleEventRole,
    ContractError,
    EventUnderstandingRequest,
    SourceDocument,
    TopicRelation,
    UnderstandingEvidenceField,
    UnderstandingStatus,
)
from insight_desk.event_understanding_adapter_v2 import (
    EventUnderstandingAdapterError,
    StructuredJsonEventUnderstandingAdapter,
)
from insight_desk.providers.cerebras import (
    CEREBRAS_GLM_47,
    CerebrasGlm47StructuredClient,
)
from insight_desk.providers.cohere import (
    COHERE_COMMAND_A_PLUS,
    CohereCommandAPlusStructuredClient,
)
from insight_desk.providers.gemini import GEMINI_FLASH_LITE, GeminiStructuredClient
from insight_desk.providers.gemini37 import (
    GEMINI_37_FLASH,
    Gemini37FlashStructuredClient,
)
from insight_desk.providers.groq import GROQ_20B, GroqFreeClient
from insight_desk.providers.groq_qwen38 import (
    GROQ_QWEN_38_27B,
    GroqQwen38StructuredClient,
)
from insight_desk.providers.mistral import MISTRAL_LARGE_3, MistralStructuredClient
from insight_desk.providers.openrouter import (
    OPENROUTER_NEMOTRON_3_SUPER_FREE,
    OpenRouterNemotronStructuredClient,
)
from insight_desk.providers.openrouter_glm52 import (
    OPENROUTER_GLM_52_FREE,
    OpenRouterGlm52StructuredClient,
)
from insight_desk.providers.openrouter_gpt54mini import (
    OPENROUTER_GPT_54_MINI,
    OpenRouterGpt54MiniStructuredClient,
)
from insight_desk.providers.openrouter_qwen235b2507 import (
    OPENROUTER_QWEN3_235B_2507_FREE,
    OpenRouterQwen235B2507StructuredClient,
)
from insight_desk.providers.transport import ProviderTransportError


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUALIFICATION = ROOT / "tests/fixtures/event_understanding_qualification_v3.json"
DEFAULT_SCOPES = ROOT / "config/semantic_topics_v2.json"
DEFAULT_REPORT = ROOT / "event-understanding-qualification.json"
PROVIDER_CHOICES = (
    "groq",
    "gemini",
    "mistral",
    "openrouter_nemotron",
    "cohere_command_a_plus",
    "cerebras_glm_47",
    "groq_qwen38_27b",
    "gemini_37_flash",
    "openrouter_glm52_free",
    "openrouter_gpt54mini",
    "openrouter_qwen235b2507_free",
)
MINIMUM_COMPATIBILITY_PASS = "MINIMUM_COMPATIBILITY_PASS"
NOT_QUALIFIED = "NOT_QUALIFIED"
QUALIFICATION_BLOCKED_TRANSIENT = "QUALIFICATION_BLOCKED_TRANSIENT"
QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE = "QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE"
_TRANSIENT_TRANSPORT_FAILURES = frozenset(
    {
        "provider_transport:transient_provider",
        "provider_transport:rate_limited",
    }
)


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
        publication_time=None,
        retrieved_via="historical_exact_source_excerpt_qualification",
        content_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
    )


def _expected_strings(value: object, *, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{name} must be a string array")
    values = tuple(item.strip() for item in value if item.strip())
    if not values:
        raise ValueError(f"{name} must contain at least one value")
    return values


def _draft_entity_text(draft) -> str:
    values = [draft.actor]
    if draft.object:
        values.append(draft.object)
    values.extend(draft.participants)
    return "\n".join(values)


def _draft_evidence_text(request: EventUnderstandingRequest, draft) -> str:
    sources = {source.source_id: source for source in request.sources}
    values: list[str] = []
    for ref in draft.evidence_refs:
        source = sources.get(ref.source_id)
        if source is None:
            continue
        text = source.title if ref.field is UnderstandingEvidenceField.TITLE else source.body
        values.append(text[ref.start : ref.end])
    return "\n".join(values)


def _draft_matches_expected_event(
    request: EventUnderstandingRequest,
    draft,
    expected_event: dict[str, object],
) -> bool:
    roles = _expected_strings(expected_event.get("allowed_article_roles"), name="allowed_article_roles")
    relations = _expected_strings(
        expected_event.get("allowed_topic_relations"), name="allowed_topic_relations"
    )
    status = str(expected_event.get("understanding_status", ""))
    if draft.article_role.value not in roles:
        return False
    if draft.topic_relation.value not in relations:
        return False
    if draft.understanding_status.value != status:
        return False

    entity_text = _draft_entity_text(draft)
    entity_literals = expected_event.get("required_entity_literals", [])
    if not isinstance(entity_literals, list) or any(not isinstance(item, str) for item in entity_literals):
        raise ValueError("required_entity_literals must be a string array")
    if any(literal and literal not in entity_text for literal in entity_literals):
        return False

    evidence_text = _draft_evidence_text(request, draft)
    evidence_literals = _expected_strings(
        expected_event.get("required_evidence_literals"), name="required_evidence_literals"
    )
    if any(literal not in evidence_text for literal in evidence_literals):
        return False
    return True


def _distinct_expected_events_match(
    request: EventUnderstandingRequest,
    drafts: tuple[object, ...],
    expected_events: list[dict[str, object]],
) -> bool:
    options: list[tuple[int, ...]] = []
    for expected_event in expected_events:
        matches = tuple(
            index
            for index, draft in enumerate(drafts)
            if _draft_matches_expected_event(request, draft, expected_event)
        )
        if not matches:
            return False
        options.append(matches)

    order = sorted(range(len(options)), key=lambda index: len(options[index]))

    def assign(position: int, used: set[int]) -> bool:
        if position == len(order):
            return True
        expected_index = order[position]
        for draft_index in options[expected_index]:
            if draft_index in used:
                continue
            used.add(draft_index)
            if assign(position + 1, used):
                return True
            used.remove(draft_index)
        return False

    return assign(0, set())


def _score(
    request: EventUnderstandingRequest,
    result,
    expected: dict[str, object],
) -> tuple[bool, list[str]]:
    """Score semantic structure without lexical matching on free-form semantic fields."""

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

    expected_events_raw = expected.get("expected_events")
    if not isinstance(expected_events_raw, list) or not expected_events_raw:
        raise ValueError("expected_events must be a non-empty array")
    expected_events: list[dict[str, object]] = []
    for raw in expected_events_raw:
        if not isinstance(raw, dict):
            raise ValueError("expected event must be an object")
        expected_events.append(raw)
    if not _distinct_expected_events_match(request, result.event_drafts, expected_events):
        failures.append("expected_event_match")

    parent_hint_count = sum(1 for draft in result.event_drafts if draft.parent_event_hint)
    if parent_hint_count < int(expected.get("parent_hint_min", 0)):
        failures.append("parent_hint_min")
    return not failures, failures


def _provider_model(provider: str) -> str:
    if provider == "groq":
        return GROQ_20B
    if provider == "gemini":
        return GEMINI_FLASH_LITE
    if provider == "mistral":
        return MISTRAL_LARGE_3
    if provider == "openrouter_nemotron":
        return OPENROUTER_NEMOTRON_3_SUPER_FREE
    if provider == "cohere_command_a_plus":
        return COHERE_COMMAND_A_PLUS
    if provider == "cerebras_glm_47":
        return CEREBRAS_GLM_47
    if provider == "groq_qwen38_27b":
        return GROQ_QWEN_38_27B
    if provider == "gemini_37_flash":
        return GEMINI_37_FLASH
    if provider == "openrouter_glm52_free":
        return OPENROUTER_GLM_52_FREE
    if provider == "openrouter_gpt54mini":
        return OPENROUTER_GPT_54_MINI
    if provider == "openrouter_qwen235b2507_free":
        return OPENROUTER_QWEN3_235B_2507_FREE
    raise ValueError(f"unsupported qualification provider: {provider}")


def _provider_configured(provider: str) -> bool:
    if provider == "groq":
        return GroqFreeClient.configured(model_id=GROQ_20B)
    if provider == "gemini":
        return GeminiStructuredClient.configured()
    if provider == "mistral":
        return MistralStructuredClient.configured()
    if provider == "openrouter_nemotron":
        return OpenRouterNemotronStructuredClient.configured()
    if provider == "cohere_command_a_plus":
        return CohereCommandAPlusStructuredClient.configured()
    if provider == "cerebras_glm_47":
        return CerebrasGlm47StructuredClient.configured()
    if provider == "groq_qwen38_27b":
        return GroqQwen38StructuredClient.configured()
    if provider == "gemini_37_flash":
        return Gemini37FlashStructuredClient.configured()
    if provider == "openrouter_glm52_free":
        return OpenRouterGlm52StructuredClient.configured()
    if provider == "openrouter_gpt54mini":
        return OpenRouterGpt54MiniStructuredClient.configured()
    if provider == "openrouter_qwen235b2507_free":
        return OpenRouterQwen235B2507StructuredClient.configured()
    raise ValueError(f"unsupported qualification provider: {provider}")


def _provider_client(provider: str):
    if provider == "groq":
        return GroqFreeClient.from_env(GROQ_20B), GROQ_20B
    if provider == "gemini":
        return GeminiStructuredClient.from_env(), GEMINI_FLASH_LITE
    if provider == "mistral":
        return MistralStructuredClient.from_env(), MISTRAL_LARGE_3
    if provider == "openrouter_nemotron":
        return (
            OpenRouterNemotronStructuredClient.from_env(),
            OPENROUTER_NEMOTRON_3_SUPER_FREE,
        )
    if provider == "cohere_command_a_plus":
        return CohereCommandAPlusStructuredClient.from_env(), COHERE_COMMAND_A_PLUS
    if provider == "cerebras_glm_47":
        return CerebrasGlm47StructuredClient.from_env(), CEREBRAS_GLM_47
    if provider == "groq_qwen38_27b":
        return GroqQwen38StructuredClient.from_env(), GROQ_QWEN_38_27B
    if provider == "gemini_37_flash":
        return Gemini37FlashStructuredClient.from_env(), GEMINI_37_FLASH
    if provider == "openrouter_glm52_free":
        return OpenRouterGlm52StructuredClient.from_env(), OPENROUTER_GLM_52_FREE
    if provider == "openrouter_gpt54mini":
        return OpenRouterGpt54MiniStructuredClient.from_env(), OPENROUTER_GPT_54_MINI
    if provider == "openrouter_qwen235b2507_free":
        return (
            OpenRouterQwen235B2507StructuredClient.from_env(),
            OPENROUTER_QWEN3_235B_2507_FREE,
        )
    raise ValueError(f"unsupported qualification provider: {provider}")


def _transport_failures(exc: ProviderTransportError) -> list[str]:
    failures = [f"provider_transport:{exc.failure_kind.value}"]
    if exc.status_code is not None:
        failures.append(f"http_status:{exc.status_code}")
    return failures


def _qualification_failure_codes(exc: Exception) -> list[str]:
    """Return bounded diagnostics without exception text, source bytes, or provider payloads."""

    if isinstance(exc, EventUnderstandingAdapterError):
        return [f"adapter_contract:{exc.failure_code}"]
    if isinstance(exc, ContractError):
        return ["core_contract:unwrapped_contract_error"]
    return [f"provider_or_contract_error:{type(exc).__name__}"]


def _case_is_transiently_blocked(item: dict[str, object]) -> bool:
    if item.get("passed") is True:
        return False
    failures = item.get("failures")
    if not isinstance(failures, list) or not failures or any(
        not isinstance(failure, str) for failure in failures
    ):
        return False
    transport_codes = [failure for failure in failures if failure.startswith("provider_transport:")]
    if len(transport_codes) != 1 or transport_codes[0] not in _TRANSIENT_TRANSPORT_FAILURES:
        return False
    return all(
        failure == transport_codes[0] or failure.startswith("http_status:")
        for failure in failures
    )


def _case_is_provider_unavailable(item: dict[str, object]) -> bool:
    if item.get("passed") is True:
        return False
    failures = item.get("failures")
    if not isinstance(failures, list) or len(failures) != 2 or any(
        not isinstance(failure, str) for failure in failures
    ):
        return False
    return set(failures) == {"provider_transport:invalid_output", "http_status:404"}


def _qualification_outcome(case_reports: list[dict[str, object]]) -> str:
    if case_reports and all(item.get("passed") is True for item in case_reports):
        return MINIMUM_COMPATIBILITY_PASS
    failed = [item for item in case_reports if item.get("passed") is not True]
    if failed and all(_case_is_transiently_blocked(item) for item in failed):
        return QUALIFICATION_BLOCKED_TRANSIENT
    if failed and all(_case_is_provider_unavailable(item) for item in failed):
        return QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE
    return NOT_QUALIFIED


def _qualification_contract_metadata(qualification: dict[str, object]) -> dict[str, object]:
    return {
        "qualification_protocol": qualification.get("schema_version"),
        "core_contract": qualification.get("core_contract"),
        "structured_output_schema": qualification.get("structured_output_schema"),
    }


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
            passed, failures = _score(request, result, expected)
        except ProviderTransportError as exc:
            passed = False
            failures = _transport_failures(exc)
        except Exception as exc:  # bounded diagnostic only; no raw exception text is emitted.
            passed = False
            failures = _qualification_failure_codes(exc)
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