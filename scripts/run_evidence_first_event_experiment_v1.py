from __future__ import annotations

"""Run the one-shot evidence-first Event Understanding architecture experiment.

The runner compares the current compatibility owner and the isolated evidence-first compiler on the
same frozen V6 source corpus.  It does not modify production wiring, call a provider, fetch fresh
news, or tune behavior per case.
"""

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Iterable

from insight_desk.core import RawArticle, SourceProvenance
from insight_desk.core.event_understanding_v2 import ArticleEventRole, UnderstandingStatus
from insight_desk.evidence_first_event_compilation_v1 import (
    ArticleClaimCompilation,
    EvidenceBoundClaim,
    canonical_draft_from_primary_claim,
    compile_article_evidence_first,
    source_document_from_raw_article,
)
from insight_desk.production_event_understanding_compat_v2 import (
    assess_compatibility_article_understanding,
)
from insight_desk.semantic import (
    KiwiMorphologyHelper,
    SemanticPipeline,
    build_resilient_fact_extractor,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUALIFICATION = ROOT / "tests/fixtures/event_understanding_qualification_v6.json"
DEFAULT_REPORT = ROOT / "evidence-first-event-experiment-v1.json"
SUCCESS_CANDIDATE = "SUCCESS_CANDIDATE"
FAILED_EXPERIMENT = "FAILED_EXPERIMENT"


def _load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected JSON object")
    return payload


def _load_cases(qualification: dict[str, object]) -> dict[str, tuple[dict[str, object], datetime]]:
    raw_paths = qualification.get("source_fixtures")
    if not isinstance(raw_paths, list) or any(not isinstance(item, str) for item in raw_paths):
        raise ValueError("qualification source_fixtures must be a string array")
    cases: dict[str, tuple[dict[str, object], datetime]] = {}
    for relative in raw_paths:
        fixture = _load_json(ROOT / relative)
        replay_clock = datetime.fromisoformat(str(fixture["replay_clock"]))
        for raw in fixture.get("cases", []):
            if not isinstance(raw, dict):
                continue
            case_id = str(raw.get("case_id", "")).strip()
            if not case_id:
                continue
            if case_id in cases:
                raise ValueError(f"duplicate source case: {case_id}")
            cases[case_id] = (raw, replay_clock)
    return cases


def _article_from_case(case_id: str, raw: dict[str, object], replay_clock: datetime) -> RawArticle:
    candidate_id = str(raw.get("candidate_id") or case_id)
    return RawArticle(
        article_id=f"experiment:{candidate_id}",
        provenance=SourceProvenance(
            source_id=f"experiment-provenance:{case_id}",
            source_name=str(raw["source_name"]),
            url=str(raw["source_url"]),
            retrieved_via="evidence-first-frozen-experiment",
            fetched_at=replay_clock,
            published_at=replay_clock,
        ),
        title=str(raw["search_title"]),
        body=str(raw["source_excerpt"]),
        topic_ids=(str(raw["topic_id"]),),
        query=str(raw["query"]) if raw.get("query") is not None else None,
    )


def _claim_evidence_text(article: RawArticle, claim: EvidenceBoundClaim) -> str:
    parts: list[str] = []
    for ref in claim.evidence_refs:
        source_text = article.title if ref.field.value == "title" else article.body
        parts.append(source_text[ref.start : ref.end])
    return "\n".join(parts)


def _claim_semantic_text(claim: EvidenceBoundClaim) -> str:
    values: list[str] = [claim.actor, claim.action]
    if claim.object:
        values.append(claim.object)
    values.extend(claim.participants)
    return "\n".join(values)


def _string_list(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError("expected string array")
    return tuple(item for item in value if item.strip())


def _expected_event_groups(expected: dict[str, object]) -> tuple[dict[str, object], ...]:
    raw = expected.get("expected_events", [])
    if not isinstance(raw, list) or any(not isinstance(item, dict) for item in raw):
        raise ValueError("expected_events must be an object array")
    return tuple(raw)


def _complete_claims(compilation: ArticleClaimCompilation) -> tuple[EvidenceBoundClaim, ...]:
    return tuple(
        claim
        for claim in compilation.claims
        if compilation.assignment(claim.claim_id).understanding_status is UnderstandingStatus.RESOLVED
    )


def _expected_group_represented(
    article: RawArticle,
    claims: Iterable[EvidenceBoundClaim],
    group: dict[str, object],
) -> bool:
    required_evidence = _string_list(group.get("required_evidence_literals"))
    required_entities = _string_list(group.get("required_entity_literals"))
    for claim in claims:
        evidence_text = _claim_evidence_text(article, claim)
        semantic_text = _claim_semantic_text(claim)
        if required_evidence and not all(item in evidence_text for item in required_evidence):
            continue
        if required_entities and not all(item in semantic_text for item in required_entities):
            continue
        return True
    return False


def _primary_matches_expected(
    article: RawArticle,
    primary: EvidenceBoundClaim | None,
    groups: tuple[dict[str, object], ...],
) -> bool:
    if primary is None:
        return False
    return any(_expected_group_represented(article, (primary,), group) for group in groups)


def _context_promoted(
    article: RawArticle,
    primary: EvidenceBoundClaim | None,
    expected: dict[str, object],
) -> bool:
    if primary is None:
        return False
    context_literals = _string_list(expected.get("context_evidence_literals"))
    if not context_literals:
        return False
    evidence_text = _claim_evidence_text(article, primary)
    return any(literal in evidence_text for literal in context_literals)


def _exact_provenance_valid(article: RawArticle, compilation: ArticleClaimCompilation) -> bool:
    source = source_document_from_raw_article(article)
    try:
        for claim in compilation.claims:
            evidence_text = _claim_evidence_text(article, claim)
            required = [claim.actor, claim.action]
            if claim.object:
                required.append(claim.object)
            if not all(value in evidence_text for value in required):
                return False
            for ref in claim.evidence_refs:
                ref.validate_against(source)
    except Exception:
        return False
    return True


def _baseline_primary_ids(article, result, morphology, replay_clock) -> tuple[str, ...]:
    facts = {fact.fact_id: fact for fact in result.facts}
    evidence = {span.evidence_id: span for span in result.evidence}
    decisions = assess_compatibility_article_understanding(
        article,
        events=result.events,
        facts=facts,
        evidence=evidence,
        morphology=morphology,
        now=replay_clock,
    )
    return tuple(
        event.event_id
        for event in result.events
        if decisions[event.event_id].status is UnderstandingStatus.RESOLVED
        and decisions[event.event_id].article_role is ArticleEventRole.PRIMARY
        and decisions[event.event_id].publishable_event
    )


def run_experiment(*, qualification_path: Path, report_path: Path) -> int:
    qualification = _load_json(qualification_path)
    if qualification.get("schema_version") != 6:
        raise ValueError("evidence-first experiment requires frozen V6 qualification fixture")
    source_cases = _load_cases(qualification)

    semantic = SemanticPipeline()
    extractor = build_resilient_fact_extractor()
    morphology = KiwiMorphologyHelper()

    reports: list[dict[str, object]] = []
    automatic_failures: list[str] = []
    historical_case_ids = {
        "run413-bok-kbs-rate-decision",
        "run413-bok-kmib-outlook-child",
        "run413-kpop-alphadriveone-actor-preserved",
        "run413-kbo-osen-same-game-source",
    }
    historical_primary = 0
    baseline_historical_primary = 0

    raw_expected_cases = qualification.get("cases", [])
    if not isinstance(raw_expected_cases, list):
        raise ValueError("qualification cases must be an array")

    for expected in raw_expected_cases:
        if not isinstance(expected, dict):
            continue
        case_id = str(expected["case_id"])
        source_entry = source_cases.get(case_id)
        if source_entry is None:
            reports.append({"case_id": case_id, "passed": False, "failures": ["missing_source_case"]})
            automatic_failures.append(f"{case_id}:missing_source_case")
            continue
        raw, replay_clock = source_entry
        article = _article_from_case(case_id, raw, replay_clock)
        result = semantic.extract_article(
            article,
            topic_id=str(raw["topic_id"]),
            extractor=extractor,
        )
        baseline_primary_ids = _baseline_primary_ids(article, result, morphology, replay_clock)
        compilation = compile_article_evidence_first(
            article,
            result,
            morphology=morphology,
        )
        primary = compilation.primary_claim()
        complete = _complete_claims(compilation)
        expected_groups = _expected_event_groups(expected)

        failures: list[str] = []
        expected_resolved = str(expected.get("expected_status")) == "resolved"
        if expected_resolved and compilation.status is not UnderstandingStatus.RESOLVED:
            failures.append("experiment_unresolved")
        if expected_resolved and primary is None:
            failures.append("primary_missing")
        if primary is not None and not _primary_matches_expected(article, primary, expected_groups):
            failures.append("primary_expected_event_mismatch")
        if any(
            not _expected_group_represented(article, complete, group)
            for group in expected_groups
        ):
            failures.append("expected_claim_evidence_not_represented")
        if _context_promoted(article, primary, expected):
            failures.append("context_promoted_primary")
        provenance_ok = _exact_provenance_valid(article, compilation)
        if not provenance_ok:
            failures.append("exact_provenance_failed")

        draft = canonical_draft_from_primary_claim(compilation)
        if primary is not None and draft is None:
            failures.append("primary_failed_canonical_draft")
        if draft is not None:
            primary_evidence_text = _claim_evidence_text(article, primary)
            semantic_values = [draft.actor, draft.action] + ([draft.object] if draft.object else [])
            if not all(value in primary_evidence_text for value in semantic_values):
                failures.append("canonical_semantics_not_source_surface")

        if case_id in historical_case_ids:
            historical_primary += int(primary is not None)
            baseline_historical_primary += int(bool(baseline_primary_ids))

        reports.append(
            {
                "case_id": case_id,
                "passed": not failures,
                "failures": failures,
                "extractor_facts": len(result.facts),
                "extractor_events": len(result.events),
                "baseline_primary_count": len(baseline_primary_ids),
                "baseline_primary_ids": list(baseline_primary_ids),
                "claim_count": len(compilation.claims),
                "complete_claim_count": len(complete),
                "experiment_status": compilation.status.value,
                "primary_claim_id": compilation.primary_claim_id,
                "primary_actor": primary.actor if primary else None,
                "primary_action": primary.action if primary else None,
                "primary_object": primary.object if primary else None,
                "primary_evidence": _claim_evidence_text(article, primary) if primary else None,
                "context_promoted_primary": _context_promoted(article, primary, expected),
                "exact_provenance_valid": provenance_ok,
                "manual_semantic_review_required": expected.get("manual_semantic_review_required") is True,
                "manual_review_question": expected.get("manual_review_question"),
            }
        )
        automatic_failures.extend(f"{case_id}:{failure}" for failure in failures)

    historical_recall_non_regressive = (
        historical_primary >= baseline_historical_primary
        and historical_primary == len(historical_case_ids)
    )
    if not historical_recall_non_regressive:
        automatic_failures.append("historical_preidentity_recall_regressed")

    outcome = SUCCESS_CANDIDATE if not automatic_failures else FAILED_EXPERIMENT
    report = {
        "status": outcome,
        "experiment": "evidence_first_event_compilation_v1",
        "production_wired": False,
        "fresh_news_used": False,
        "provider_calls": 0,
        "qualification_fixture": str(qualification_path.relative_to(ROOT)),
        "evaluated_cases": len(reports),
        "passed_cases": sum(1 for item in reports if item["passed"] is True),
        "automatic_failures": automatic_failures,
        "exact_provenance_all_cases": all(item.get("exact_provenance_valid") is True for item in reports),
        "historical_preidentity_primary_count": historical_primary,
        "baseline_historical_preidentity_primary_count": baseline_historical_primary,
        "historical_preidentity_recall_non_regressive": historical_recall_non_regressive,
        "manual_semantic_review_required": any(
            item.get("manual_semantic_review_required") is True for item in reports
        ),
        "cases": reports,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if outcome == SUCCESS_CANDIDATE else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qualification", type=Path, default=DEFAULT_QUALIFICATION)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    return run_experiment(
        qualification_path=args.qualification,
        report_path=args.report,
    )


if __name__ == "__main__":
    sys.exit(main())
