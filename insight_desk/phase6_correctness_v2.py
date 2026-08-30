from __future__ import annotations

"""Evidence-bounded correctness/recall scoring for Canonical V2 production replay.

This scorer intentionally refuses to use the historical 126-card visible proxy corpus as a
source-replay denominator. Its denominator is only replay cases with explicit real source identity,
exact preserved source bytes, and an explicit expected production outcome.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class Phase6CorrectnessReport:
    status: str
    evidence_scope: str
    expected_publishable: int
    expected_suppressed_same_event: int
    actual_publications: int
    correctly_published: int
    correctly_suppressed_same_event: int
    missed_expected_urls: tuple[str, ...]
    unexpected_publication_urls: tuple[str, ...]
    wrongly_published_suppressed_urls: tuple[str, ...]
    publication_recall: float
    publication_precision: float
    same_event_suppression_recall: float
    parent_child_identity_ok: bool
    canonical_bundle_validated: bool
    publication_digest_bound: bool
    provenance_integrity_ok: bool
    historical_full_body_coverage: str = "unavailable_not_in_denominator"

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "evidence_scope": self.evidence_scope,
            "expected_publishable": self.expected_publishable,
            "expected_suppressed_same_event": self.expected_suppressed_same_event,
            "actual_publications": self.actual_publications,
            "correctly_published": self.correctly_published,
            "correctly_suppressed_same_event": self.correctly_suppressed_same_event,
            "missed_expected_urls": list(self.missed_expected_urls),
            "unexpected_publication_urls": list(self.unexpected_publication_urls),
            "wrongly_published_suppressed_urls": list(self.wrongly_published_suppressed_urls),
            "publication_recall": self.publication_recall,
            "publication_precision": self.publication_precision,
            "same_event_suppression_recall": self.same_event_suppression_recall,
            "parent_child_identity_ok": self.parent_child_identity_ok,
            "canonical_bundle_validated": self.canonical_bundle_validated,
            "publication_digest_bound": self.publication_digest_bound,
            "provenance_integrity_ok": self.provenance_integrity_ok,
            "historical_full_body_coverage": self.historical_full_body_coverage,
        }


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 1.0
    return numerator / denominator


def _publication_rows(manifest: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    rows = manifest.get("publications", ())
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise ValueError("publication manifest must contain a publications sequence")
    normalized: list[Mapping[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("publication manifest row must be an object")
        normalized.append(row)
    return tuple(normalized)


def score_recorded_replay(
    *,
    fixture: Mapping[str, Any],
    manifest: Mapping[str, Any],
    replay_report: Mapping[str, Any],
) -> Phase6CorrectnessReport:
    """Score one production replay without inventing unavailable historical source coverage."""

    cases = fixture.get("cases", ())
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes)) or not cases:
        raise ValueError("Phase 6 fixture requires replay cases")

    publish_cases: list[Mapping[str, Any]] = []
    suppress_cases: list[Mapping[str, Any]] = []
    for case in cases:
        if not isinstance(case, Mapping):
            raise ValueError("Phase 6 replay case must be an object")
        outcome = case.get("expected_outcome")
        if outcome == "publish":
            publish_cases.append(case)
        elif outcome == "suppress_same_event":
            suppress_cases.append(case)
        else:
            raise ValueError(f"unsupported Phase 6 expected_outcome: {outcome!r}")

    expected_publish_urls = {str(case["source_url"]) for case in publish_cases}
    expected_suppress_urls = {str(case["source_url"]) for case in suppress_cases}
    if expected_publish_urls & expected_suppress_urls:
        raise ValueError("one source URL cannot be both publish and suppress expectation")

    publications = _publication_rows(manifest)
    actual_urls = {
        str(row.get("primary_source_url", "")).strip()
        for row in publications
        if str(row.get("primary_source_url", "")).strip()
    }
    if len(actual_urls) != len(publications):
        raise ValueError("every replay publication must retain a unique primary source URL")

    correctly_published_urls = expected_publish_urls & actual_urls
    missed_expected = tuple(sorted(expected_publish_urls - actual_urls))
    unexpected = tuple(sorted(actual_urls - expected_publish_urls))
    wrongly_published_suppressed = tuple(sorted(expected_suppress_urls & actual_urls))
    correctly_suppressed = expected_suppress_urls - actual_urls

    representative_parent_rows = [
        row
        for row in publications
        if str(row.get("primary_source_url", "")) in expected_publish_urls
        and str(row.get("primary_source_url", ""))
        == next(
            (
                str(case["source_url"])
                for case in publish_cases
                if case.get("expected_relation") == "policy_meeting_parent_representative"
            ),
            "",
        )
    ]
    expected_non_parent_urls = {
        str(case["source_url"])
        for case in publish_cases
        if case.get("expected_relation") != "policy_meeting_parent_representative"
    }
    parent_child_identity_ok = (
        len(representative_parent_rows) == 1
        and bool(representative_parent_rows[0].get("parent_event_id"))
        and str(representative_parent_rows[0].get("parent_event_id", "")).startswith(
            "canonical-parent:bok_mpc"
        )
        and all(
            row.get("parent_event_id") is None
            for row in publications
            if str(row.get("primary_source_url", "")) in expected_non_parent_urls
        )
        and int(replay_report.get("identity_same_event", 0)) >= len(suppress_cases)
        and int(replay_report.get("canonical_parent_events", 0)) >= 1
    )

    provenance_integrity_ok = all(
        bool(row.get("publication_id"))
        and bool(row.get("event_id"))
        and bool(row.get("topic"))
        and bool(row.get("source_ids"))
        and bool(row.get("primary_source_url"))
        and bool(row.get("claim_ids"))
        and bool(row.get("verification_check_ids"))
        for row in publications
    )
    canonical_bundle_validated = replay_report.get("canonical_bundle_validated") is True
    publication_digest_bound = replay_report.get("pwa_state_audit_digest_bound") is True

    publication_recall = _ratio(len(correctly_published_urls), len(expected_publish_urls))
    publication_precision = _ratio(len(correctly_published_urls), len(actual_urls))
    suppression_recall = _ratio(len(correctly_suppressed), len(expected_suppress_urls))

    passed = (
        not missed_expected
        and not unexpected
        and not wrongly_published_suppressed
        and publication_recall == 1.0
        and publication_precision == 1.0
        and suppression_recall == 1.0
        and parent_child_identity_ok
        and canonical_bundle_validated
        and publication_digest_bound
        and provenance_integrity_ok
    )

    return Phase6CorrectnessReport(
        status="PASS" if passed else "FAIL",
        evidence_scope="recoverable_real_url_plus_exact_source_bytes_only",
        expected_publishable=len(expected_publish_urls),
        expected_suppressed_same_event=len(expected_suppress_urls),
        actual_publications=len(publications),
        correctly_published=len(correctly_published_urls),
        correctly_suppressed_same_event=len(correctly_suppressed),
        missed_expected_urls=missed_expected,
        unexpected_publication_urls=unexpected,
        wrongly_published_suppressed_urls=wrongly_published_suppressed,
        publication_recall=publication_recall,
        publication_precision=publication_precision,
        same_event_suppression_recall=suppression_recall,
        parent_child_identity_ok=parent_child_identity_ok,
        canonical_bundle_validated=canonical_bundle_validated,
        publication_digest_bound=publication_digest_bound,
        provenance_integrity_ok=provenance_integrity_ok,
    )
