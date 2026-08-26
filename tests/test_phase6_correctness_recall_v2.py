from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from insight_desk.phase6_correctness_v2 import score_recorded_replay
from insight_desk.production_replay_v2 import run_recorded_production_replay


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "phase5_real_source_replay_v1.json"
_PRODUCTION_SEMANTIC_RUNTIME_AVAILABLE = importlib.util.find_spec("kiwipiepy") is not None


class Phase6CorrectnessRecallTests(unittest.TestCase):
    @unittest.skipUnless(
        _PRODUCTION_SEMANTIC_RUNTIME_AVAILABLE,
        "Phase 6 source-level gate requires the same semantic-local runtime as production",
    )
    def test_recoverable_historical_source_set_has_perfect_bounded_correctness_and_recall(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            replay = run_recorded_production_replay(
                fixture_path=FIXTURE,
                work_dir=Path(tmp),
            )
            report = score_recorded_replay(
                fixture=fixture,
                manifest=replay.publication_manifest,
                replay_report=replay.report,
            )

        self.assertTrue(report.passed, report.as_dict())
        self.assertEqual(report.evidence_scope, "recoverable_real_url_plus_exact_source_bytes_only")
        self.assertEqual(report.expected_publishable, 3)
        self.assertEqual(report.expected_suppressed_same_event, 1)
        self.assertEqual(report.actual_publications, 3)
        self.assertEqual(report.correctly_published, 3)
        self.assertEqual(report.correctly_suppressed_same_event, 1)
        self.assertEqual(report.publication_recall, 1.0)
        self.assertEqual(report.publication_precision, 1.0)
        self.assertEqual(report.same_event_suppression_recall, 1.0)
        self.assertTrue(report.parent_child_identity_ok)
        self.assertTrue(report.canonical_bundle_validated)
        self.assertTrue(report.publication_digest_bound)
        self.assertTrue(report.provenance_integrity_ok)
        self.assertEqual(report.historical_full_body_coverage, "unavailable_not_in_denominator")

    def test_scorer_fails_when_an_expected_source_is_missing(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        publish_cases = [case for case in fixture["cases"] if case["expected_outcome"] == "publish"]
        rows = []
        for case in publish_cases[1:]:
            rows.append(
                {
                    "publication_id": "pub:" + case["case_id"],
                    "event_id": "event:" + case["case_id"],
                    "topic": case["topic_id"],
                    "source_ids": ["source:test"],
                    "primary_source_url": case["source_url"],
                    "claim_ids": ["claim:test"],
                    "verification_check_ids": ["check:test"],
                    "parent_event_id": None,
                }
            )
        report = score_recorded_replay(
            fixture=fixture,
            manifest={"publications": rows},
            replay_report={
                "identity_same_event": 1,
                "canonical_parent_events": 1,
                "canonical_bundle_validated": True,
                "pwa_state_audit_digest_bound": True,
            },
        )
        self.assertFalse(report.passed)
        self.assertLess(report.publication_recall, 1.0)
        self.assertTrue(report.missed_expected_urls)

    def test_scorer_fails_when_suppressed_same_event_child_reappears(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        rows = []
        for case in fixture["cases"]:
            if case["expected_outcome"] not in {"publish", "suppress_same_event"}:
                continue
            parent = (
                "canonical-parent:bok_mpc:test"
                if case["expected_relation"] == "policy_meeting_parent_representative"
                else None
            )
            rows.append(
                {
                    "publication_id": "pub:" + case["case_id"],
                    "event_id": "event:" + case["case_id"],
                    "topic": case["topic_id"],
                    "source_ids": ["source:test"],
                    "primary_source_url": case["source_url"],
                    "claim_ids": ["claim:test"],
                    "verification_check_ids": ["check:test"],
                    "parent_event_id": parent,
                }
            )
        report = score_recorded_replay(
            fixture=fixture,
            manifest={"publications": rows},
            replay_report={
                "identity_same_event": 1,
                "canonical_parent_events": 1,
                "canonical_bundle_validated": True,
                "pwa_state_audit_digest_bound": True,
            },
        )
        self.assertFalse(report.passed)
        self.assertEqual(report.same_event_suppression_recall, 0.0)
        self.assertTrue(report.wrongly_published_suppressed_urls)
        self.assertTrue(report.unexpected_publication_urls)


if __name__ == "__main__":
    unittest.main()
