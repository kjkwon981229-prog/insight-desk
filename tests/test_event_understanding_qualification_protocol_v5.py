from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from insight_desk.core import EventUnderstandingRequest, SourceDocument
from insight_desk.event_understanding_adapter_v4 import (
    EVENT_UNDERSTANDING_SCHEMA_V4,
    V5_PROVIDER_CONTRACT_INVARIANTS,
    build_event_understanding_prompt_v5,
)
from insight_desk.event_understanding_provider_status_v2 import (
    AWAITING_PROVIDER_QUALIFICATION,
    CANDIDATE_QUALIFICATION_BLOCKED,
    QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE,
    load_provider_status,
    validate_provider_status,
)
from scripts import qualify_event_understanding_provider_v4 as qualification_v4
from scripts import qualify_event_understanding_provider_v5 as qualification_v5


ROOT = Path(__file__).resolve().parents[1]
V4_PATH = ROOT / "tests/fixtures/event_understanding_qualification_v4.json"
V5_PATH = ROOT / "tests/fixtures/event_understanding_qualification_v5.json"
STATUS_PATH = ROOT / "config/event_understanding_provider_status_v2.json"
MIGRATION_GATE_PATH = ROOT / "config/event_understanding_migration_gate_v2.json"


EXPECTED_DRAFT_DIAGNOSTICS = {
    "duplicate_evidence_refs",
    "duplicate_participants",
    "duplicate_event_uncertainty_reasons",
    "event_time_format",
    "event_time_timezone",
    "value_requires_metric",
    "metric_requires_value",
    "resolved_event_with_uncertainty",
    "unresolved_event_without_uncertainty",
}
EXPECTED_ARTICLE_DIAGNOSTICS = {
    "duplicate_article_uncertainty_reasons",
    "resolved_article_with_uncertainty",
    "resolved_article_without_event",
    "resolved_article_without_primary",
    "unresolved_article_without_uncertainty",
}


class EventUnderstandingQualificationProtocolV5Tests(unittest.TestCase):
    def test_v5_changes_provider_contract_only_not_semantic_cases_or_scorer(self) -> None:
        v4 = json.loads(V4_PATH.read_text(encoding="utf-8"))
        v5 = json.loads(V5_PATH.read_text(encoding="utf-8"))

        self.assertEqual(v5["schema_version"], 5)
        self.assertEqual(v5["core_contract"], v4["core_contract"])
        self.assertEqual(v5["structured_output_schema"], "event_understanding_schema_v4")
        self.assertEqual(v5["source_fixture"], v4["source_fixture"])
        self.assertEqual(v5["source_contract_corrections"], v4["source_contract_corrections"])
        self.assertEqual(v5["scoring_policy"], v4["scoring_policy"])
        self.assertEqual(v5["cases"], v4["cases"])
        self.assertEqual(v5["acceptance"], v4["acceptance"])
        self.assertIs(qualification_v5._score, qualification_v4._score)
        self.assertIs(
            qualification_v5._qualification_outcome,
            qualification_v4._qualification_outcome,
        )

    def test_v5_model_facing_contract_covers_every_bounded_core_invariant(self) -> None:
        expected = EXPECTED_DRAFT_DIAGNOSTICS | EXPECTED_ARTICLE_DIAGNOSTICS
        self.assertEqual(set(V5_PROVIDER_CONTRACT_INVARIANTS), expected)
        for code, instruction in V5_PROVIDER_CONTRACT_INVARIANTS.items():
            with self.subTest(code=code):
                self.assertIsInstance(instruction, str)
                self.assertTrue(instruction.strip())

        source = SourceDocument(
            source_id="source-1",
            candidate_ids=("candidate-1",),
            publisher="fixture",
            url="https://example.com/article",
            title="한국은행 기준금리 결정",
            body="한국은행은 기준금리를 결정했다.",
            fetched_at=qualification_v5.datetime.fromisoformat("2026-08-28T00:00:00+00:00"),
            publication_time=None,
            retrieved_via="fixture",
            content_sha256="f" * 64,
        )
        request = EventUnderstandingRequest(
            topic="macro",
            semantic_scope="한국은행 통화정책",
            sources=(source,),
        )
        prompt = build_event_understanding_prompt_v5(request)
        for code, instruction in V5_PROVIDER_CONTRACT_INVARIANTS.items():
            with self.subTest(code=code):
                self.assertIn(instruction, prompt)

    def test_v5_schema_keeps_v4_exact_evidence_handoff_and_no_provider_specific_fields(self) -> None:
        event = EVENT_UNDERSTANDING_SCHEMA_V4["properties"]["events"]["items"]
        evidence = event["properties"]["evidence"]["items"]
        self.assertEqual(evidence["required"], ["source_id", "field", "text"])
        self.assertEqual(set(evidence["properties"]), {"source_id", "field", "text"})
        self.assertNotIn("provider", EVENT_UNDERSTANDING_SCHEMA_V4["properties"])
        self.assertNotIn("model", EVENT_UNDERSTANDING_SCHEMA_V4["properties"])

    def test_v5_unconfigured_report_identifies_v5_without_provider_call(self) -> None:
        original_configured = qualification_v5._provider_configured
        original_model = qualification_v5._provider_model
        try:
            qualification_v5._provider_configured = lambda provider: False
            qualification_v5._provider_model = lambda provider: "fixture-model"
            with tempfile.TemporaryDirectory() as tmpdir:
                report_path = Path(tmpdir) / "report.json"
                exit_code = qualification_v5.qualify(
                    provider="groq",
                    qualification_path=V5_PATH,
                    scopes_path=qualification_v5.DEFAULT_SCOPES,
                    report_path=report_path,
                )
                report = json.loads(report_path.read_text(encoding="utf-8"))
        finally:
            qualification_v5._provider_configured = original_configured
            qualification_v5._provider_model = original_model

        self.assertEqual(exit_code, 2)
        self.assertEqual(report["status"], "NOT_CONFIGURED")
        self.assertEqual(report["qualification_protocol"], 5)
        self.assertEqual(report["structured_output_schema"], "event_understanding_schema_v4")
        self.assertEqual(report["evaluated_cases"], 0)

    def test_v5_active_non_pass_evidence_does_not_create_selection(self) -> None:
        status = load_provider_status(STATUS_PATH)
        validate_provider_status(status)
        self.assertEqual(status["active_qualification_protocol"], 5)
        self.assertEqual(status["structured_output_schema"], "event_understanding_schema_v4")
        self.assertEqual(status["qualification_contract_status"], AWAITING_PROVIDER_QUALIFICATION)
        self.assertEqual(status["provider_inventory_status"], CANDIDATE_QUALIFICATION_BLOCKED)
        self.assertIsNone(status["selected_event_understanding_provider"])
        self.assertFalse(status["production_wired"])

        active_records = {
            provider_id: record
            for provider_id, record in status["providers"].items()
            if record.get("qualification_protocol") == 5
        }
        self.assertEqual(
            set(active_records),
            {
                "mistral_medium35_v5",
                "mistral_small4_v5",
                "cohere_command_a_reasoning_v5",
                "gemini_3_flash_v5",
                "openrouter_dots3note_v5",
                "openrouter_nexn2pro_v5",
                "openrouter_qwen3next80b_v5",
            },
        )
        definitive_non_passes = {
            "mistral_medium35_v5": 3,
            "mistral_small4_v5": 1,
            "cohere_command_a_reasoning_v5": 2,
            "gemini_3_flash_v5": 2,
            "openrouter_dots3note_v5": 2,
        }
        for provider_id, passed_cases in definitive_non_passes.items():
            with self.subTest(provider_id=provider_id):
                record = active_records[provider_id]
                self.assertEqual(record["status"], "NOT_QUALIFIED")
                self.assertEqual(record["evaluated_cases"], 4)
                self.assertEqual(record["passed_cases"], passed_cases)
                self.assertLess(record["passed_cases"], 4)

        for provider_id in (
            "openrouter_nexn2pro_v5",
            "openrouter_qwen3next80b_v5",
        ):
            with self.subTest(provider_id=provider_id):
                record = active_records[provider_id]
                self.assertEqual(record["status"], QUALIFICATION_BLOCKED_PROVIDER_UNAVAILABLE)
                self.assertEqual(record["evaluated_cases"], 4)
                self.assertEqual(record["passed_cases"], 0)
                self.assertEqual(record["failure_classification"], "PROVIDER_MODEL_UNAVAILABLE")

        self.assertFalse(
            any(item.get("status") == "MINIMUM_COMPATIBILITY_PASS" for item in active_records.values())
        )
        self.assertTrue(
            any(record.get("qualification_protocol") == 4 for record in status["providers"].values())
        )

    def test_v4_pass_cannot_be_reused_as_v5_selection(self) -> None:
        status = load_provider_status(STATUS_PATH)
        mutated = deepcopy(status)
        mutated["providers"]["synthetic_v4_pass"] = {
            "provider": "fixture",
            "model": "fixture-model",
            "status": "MINIMUM_COMPATIBILITY_PASS",
            "qualification_protocol": 4,
            "evaluated_cases": 4,
            "passed_cases": 4,
        }
        mutated["qualification_contract_status"] = "QUALIFIED_PROVIDER_SELECTED"
        mutated["provider_inventory_status"] = "ELIGIBLE_CANDIDATE_AVAILABLE"
        mutated["selected_event_understanding_provider"] = "synthetic_v4_pass"
        with self.assertRaisesRegex(Exception, "stale protocol"):
            validate_provider_status(mutated)

    def test_v5_does_not_open_migration_gate(self) -> None:
        gate = json.loads(MIGRATION_GATE_PATH.read_text(encoding="utf-8"))
        self.assertFalse(gate["production_rewire_allowed"])
        self.assertEqual(len(gate["runtime_blockers"]), 3)
        self.assertTrue(all(item["active"] for item in gate["runtime_blockers"].values()))


if __name__ == "__main__":
    unittest.main()
