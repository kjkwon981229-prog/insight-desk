from __future__ import annotations

"""Bounded source-grounded proposition authority experiment.

This runner reuses the frozen V6 corpus and the primary evidence selection from the failed
EvidenceBoundClaim experiment, but deliberately does *not* treat flat actor/action/object fields as
the authoritative event meaning.  The exact selected source proposition is the semantic authority.

No provider calls, fresh news, production wiring, article-specific rules, or generated paraphrases
are used here.
"""

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

from insight_desk.core import RawArticle, SourceProvenance
from insight_desk.core.event_understanding_v2 import UnderstandingStatus
from insight_desk.evidence_first_event_compilation_v1 import (
    ArticleClaimCompilation,
    EvidenceBoundClaim,
    compile_article_evidence_first,
    source_document_from_raw_article,
)
from insight_desk.semantic import KiwiMorphologyHelper, SemanticPipeline, build_resilient_fact_extractor
from scripts.run_evidence_first_event_experiment_v1 import (
    ROOT,
    _baseline_primary_ids,
    _claim_evidence_text,
    _context_promoted,
    _exact_provenance_valid,
    _expected_event_groups,
    _load_cases,
    _load_json,
    _string_list,
)


DEFAULT_QUALIFICATION = ROOT / "tests/fixtures/event_understanding_qualification_v6.json"
DEFAULT_REPORT = ROOT / "source-grounded-proposition-experiment-v1.json"
SUCCESS_PENDING_HUMAN = "SUCCESS_CANDIDATE_PENDING_HUMAN"
FAILED_EXPERIMENT = "FAILED_EXPERIMENT"


def _article_from_case(case_id: str, raw: dict[str, object], replay_clock: datetime) -> RawArticle:
    candidate_id = str(raw.get("candidate_id") or case_id)
    return RawArticle(
        article_id=f"proposition-experiment:{candidate_id}",
        provenance=SourceProvenance(
            source_id=f"proposition-provenance:{case_id}",
            source_name=str(raw["source_name"]),
            url=str(raw["source_url"]),
            retrieved_via="source-grounded-proposition-frozen-experiment",
            fetched_at=replay_clock,
            published_at=replay_clock,
        ),
        title=str(raw["search_title"]),
        body=str(raw["source_excerpt"]),
        topic_ids=(str(raw["topic_id"]),),
        query=str(raw["query"]) if raw.get("query") is not None else None,
    )


def _primary_proposition(article: RawArticle, compilation: ArticleClaimCompilation) -> tuple[EvidenceBoundClaim | None, str | None]:
    primary = compilation.primary_claim()
    if primary is None:
        return None, None
    return primary, _claim_evidence_text(article, primary)


def _group_is_represented_by_proposition(proposition: str, group: dict[str, object]) -> bool:
    required_evidence = _string_list(group.get("required_evidence_literals"))
    required_entities = _string_list(group.get("required_entity_literals"))
    if required_evidence and not all(item in proposition for item in required_evidence):
        return False
    if required_entities and not all(item in proposition for item in required_entities):
        return False
    return True


def run_experiment(*, qualification_path: Path, report_path: Path) -> int:
    qualification = _load_json(qualification_path)
    if qualification.get("schema_version") != 6:
        raise ValueError("source-grounded proposition experiment requires frozen V6 qualification")
    source_cases = _load_cases(qualification)

    semantic = SemanticPipeline()
    extractor = build_resilient_fact_extractor()
    morphology = KiwiMorphologyHelper()

    raw_expected_cases = qualification.get("cases", [])
    if not isinstance(raw_expected_cases, list):
        raise ValueError("qualification cases must be an array")

    historical_case_ids = {
        "run413-bok-kbs-rate-decision",
        "run413-bok-kmib-outlook-child",
        "run413-kpop-alphadriveone-actor-preserved",
        "run413-kbo-osen-same-game-source",
    }
    historical_primary = 0
    baseline_historical_primary = 0
    reports: list[dict[str, object]] = []
    failures: list[str] = []
    manual_cases: list[dict[str, object]] = []

    for expected in raw_expected_cases:
        if not isinstance(expected, dict):
            continue
        case_id = str(expected["case_id"])
        source_entry = source_cases.get(case_id)
        if source_entry is None:
            failures.append(f"{case_id}:missing_source_case")
            reports.append({"case_id": case_id, "passed": False, "failures": ["missing_source_case"]})
            continue

        raw, replay_clock = source_entry
        article = _article_from_case(case_id, raw, replay_clock)
        result = semantic.extract_article(article, topic_id=str(raw["topic_id"]), extractor=extractor)
        baseline_primary_ids = _baseline_primary_ids(article, result, morphology, replay_clock)
        compilation = compile_article_evidence_first(article, result, morphology=morphology)
        primary, proposition = _primary_proposition(article, compilation)

        case_failures: list[str] = []
        if compilation.status is not UnderstandingStatus.RESOLVED or proposition is None:
            case_failures.append("primary_proposition_missing")

        manual_required = expected.get("manual_semantic_review_required") is True
        groups = _expected_event_groups(expected)
        if proposition is not None and not manual_required:
            if groups and not any(_group_is_represented_by_proposition(proposition, group) for group in groups):
                case_failures.append("primary_proposition_expected_event_mismatch")
        if proposition is not None and _context_promoted(article, primary, expected):
            case_failures.append("context_promoted_primary")

        provenance_ok = _exact_provenance_valid(article, compilation)
        if not provenance_ok:
            case_failures.append("exact_provenance_failed")

        if case_id in historical_case_ids:
            historical_primary += int(proposition is not None)
            baseline_historical_primary += int(bool(baseline_primary_ids))

        if manual_required:
            manual_cases.append(
                {
                    "case_id": case_id,
                    "question": expected.get("manual_review_question"),
                    "source_title": article.title,
                    "primary_proposition": proposition,
                    "full_source_excerpt": article.body,
                    "exact_provenance_valid": provenance_ok,
                }
            )

        reports.append(
            {
                "case_id": case_id,
                "passed_automatic": not case_failures,
                "failures": case_failures,
                "extractor_facts": len(result.facts),
                "baseline_primary_count": len(baseline_primary_ids),
                "primary_proposition": proposition,
                "primary_claim_actor_projection": primary.actor if primary else None,
                "primary_claim_action_projection": primary.action if primary else None,
                "primary_claim_object_projection": primary.object if primary else None,
                "context_promoted_primary": _context_promoted(article, primary, expected) if primary else False,
                "exact_provenance_valid": provenance_ok,
                "manual_semantic_review_required": manual_required,
            }
        )
        failures.extend(f"{case_id}:{failure}" for failure in case_failures)

    historical_recall_non_regressive = (
        historical_primary == len(historical_case_ids)
        and historical_primary >= baseline_historical_primary
    )
    if not historical_recall_non_regressive:
        failures.append("historical_preidentity_recall_regressed")

    outcome = SUCCESS_PENDING_HUMAN if not failures else FAILED_EXPERIMENT
    report = {
        "status": outcome,
        "experiment": "source_grounded_proposition_authority_v1",
        "production_wired": False,
        "fresh_news_used": False,
        "provider_calls": 0,
        "generated_paraphrases": 0,
        "qualification_fixture": str(qualification_path.relative_to(ROOT)),
        "evaluated_cases": len(reports),
        "automatic_passed_cases": sum(1 for item in reports if item["passed_automatic"] is True),
        "automatic_failures": failures,
        "exact_provenance_all_cases": all(item.get("exact_provenance_valid") is True for item in reports),
        "historical_preidentity_primary_count": historical_primary,
        "baseline_historical_preidentity_primary_count": baseline_historical_primary,
        "historical_preidentity_recall_non_regressive": historical_recall_non_regressive,
        "manual_semantic_review_required": bool(manual_cases),
        "manual_review_cases": manual_cases,
        "cases": reports,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if outcome == SUCCESS_PENDING_HUMAN else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qualification", type=Path, default=DEFAULT_QUALIFICATION)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    return run_experiment(qualification_path=args.qualification, report_path=args.report)


if __name__ == "__main__":
    sys.exit(main())
