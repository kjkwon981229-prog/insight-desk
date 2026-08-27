from __future__ import annotations

import json
from pathlib import Path
import unittest

from insight_desk.core import FailureKind
from insight_desk.providers.mistral import MISTRAL_LARGE_3
from insight_desk.providers.openrouter import OPENROUTER_NEMOTRON_3_SUPER_FREE
from insight_desk.providers.transport import ProviderTransportError
from scripts.qualify_event_understanding_provider import PROVIDER_CHOICES, _transport_failures


ROOT = Path(__file__).resolve().parents[1]


class EventUnderstandingQualificationV1Tests(unittest.TestCase):
    def test_semantic_scope_config_covers_all_current_topics_without_keyword_lists(self) -> None:
        semantic = json.loads((ROOT / "config/semantic_topics_v2.json").read_text(encoding="utf-8"))
        legacy = json.loads((ROOT / "config/topics.json").read_text(encoding="utf-8"))
        semantic_by_id = {item["id"]: item for item in semantic["topics"]}
        enabled_ids = {item["id"] for item in legacy["topics"] if item.get("enabled") is True}
        self.assertEqual(set(semantic_by_id), enabled_ids)
        for item in semantic_by_id.values():
            self.assertTrue(item["semantic_scope"].strip())
            self.assertNotIn("intent_anchors", item)
            self.assertNotIn("required_intent_terms", item)
            self.assertNotIn("event_terms", item)

    def test_qualification_uses_only_recoverable_historical_exact_source_cases(self) -> None:
        qualification = json.loads(
            (ROOT / "tests/fixtures/event_understanding_qualification_v1.json").read_text(
                encoding="utf-8"
            )
        )
        source = json.loads(
            (ROOT / qualification["source_fixture"]).read_text(encoding="utf-8")
        )
        self.assertEqual(source["phase5_status"], "PARTIAL")
        self.assertFalse(source["raw_article_body_complete"])
        source_ids = {case["case_id"] for case in source["cases"]}
        qualification_ids = {case["case_id"] for case in qualification["cases"]}
        self.assertEqual(len(qualification_ids), 4)
        self.assertTrue(qualification_ids.issubset(source_ids))
        self.assertEqual(qualification["status"], "MINIMUM_PROVIDER_QUALIFICATION_ONLY")
        self.assertTrue(qualification["acceptance"]["no_fresh_news"])
        self.assertTrue(qualification["acceptance"]["no_production_wiring"])

    def test_bok_multi_child_case_requires_structure_before_identity(self) -> None:
        qualification = json.loads(
            (ROOT / "tests/fixtures/event_understanding_qualification_v1.json").read_text(
                encoding="utf-8"
            )
        )
        case = next(
            item
            for item in qualification["cases"]
            if item["case_id"] == "run413-bok-kmib-outlook-child"
        )
        self.assertGreaterEqual(case["event_drafts_min"], 2)
        self.assertGreaterEqual(case["parent_hint_min"], 2)
        self.assertIn("수정 경제전망", case["required_structured_literals"])
        self.assertIn("점도표", case["required_structured_literals"])

    def test_candidate_provider_set_is_explicit_and_does_not_include_groq_120b(self) -> None:
        self.assertEqual(
            PROVIDER_CHOICES,
            (
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
            ),
        )
        self.assertNotIn("groq_120b", PROVIDER_CHOICES)
        self.assertEqual(MISTRAL_LARGE_3, "mistral-large-2512")
        self.assertEqual(
            OPENROUTER_NEMOTRON_3_SUPER_FREE,
            "nvidia/nemotron-3-super-120b-a12b:free",
        )

    def test_transport_failure_report_uses_only_safe_classification_metadata(self) -> None:
        exc = ProviderTransportError(
            failure_kind=FailureKind.RATE_LIMITED,
            status_code=429,
            detail="do not serialize provider body",
        )
        failures = _transport_failures(exc)
        self.assertEqual(failures, ["provider_transport:rate_limited", "http_status:429"])
        self.assertNotIn("provider body", "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
