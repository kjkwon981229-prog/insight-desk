from __future__ import annotations

import inspect
from pathlib import Path
import unittest

import insight_desk.feed_quality_detectors_core as detector_core
import scripts.phase11_daily_production_core as production_core


class FinalStructuralSweepContract(unittest.TestCase):
    def test_detector_core_exposes_signals_not_an_admission_composite(self) -> None:
        source = Path("insight_desk/feed_quality_detectors_core.py").read_text(encoding="utf-8")
        self.assertNotIn("def visible_story_issues(", source)
        self.assertFalse(hasattr(detector_core, "visible_story_issues"))

    def test_material_contains_no_independent_metadata_or_non_event_composite(self) -> None:
        source = Path("insight_desk/semantic/material.py").read_text(encoding="utf-8")
        self.assertNotIn("def _publisher_notice_boilerplate", source)
        self.assertNotIn("def _standalone_sports_photo_caption", source)
        self.assertIn("evaluate_story_admission(", source)
        self.assertIn("MATERIAL_PUBLISHER_NOTICE_BOILERPLATE", source)
        self.assertIn("MATERIAL_DEPICTIVE_SPORTS_CAPTION", source)

    def test_production_core_projects_shared_routing_decision(self) -> None:
        source = Path("scripts/phase11_daily_production_core.py").read_text(encoding="utf-8")
        for forbidden in (
            "_KBO_ENTERTAINMENT_ACTION_CUES",
            "_KPOP_HEADLINE_SCOPE_CUES",
            "def _hanwha_fact_directly_bound",
            "def _hanwha_fact_subject_central",
            "def _kbo_entertainment_crossover",
            "def _fact_has_configured_kbo_event_term",
        ):
            self.assertNotIn(forbidden, source)
        runtime_source = inspect.getsource(production_core.event_topic_relevant)
        self.assertIn("evaluate_story_admission(", runtime_source)
        self.assertIn("StoryAdmissionStage.ROUTING", runtime_source)
        self.assertIn("return decision.accepted", runtime_source)

    def test_generation_routes_share_one_final_admission_gate(self) -> None:
        facade = Path("insight_desk/generation.py").read_text(encoding="utf-8")
        pipeline = Path("insight_desk/generation_pipeline.py").read_text(encoding="utf-8")
        self.assertIn("def validate_story_admission", facade)
        self.assertGreaterEqual(pipeline.count("validate_story_admission("), 2)
        self.assertIn("draft = generator.generate(request)", pipeline)
        self.assertIn("draft = GeneratedDraft(", pipeline)

    def test_validator_is_consumer_not_story_policy_owner(self) -> None:
        source = Path("scripts/validate_feed_artifact.py").read_text(encoding="utf-8")
        self.assertIn("evaluate_story_admission(", source)
        for forbidden in (
            "def context_dependent_headline",
            "def context_dependent_summary",
            "def non_event_analytical_text",
            "def kbo_hanwha_comparison_only",
            "def stale_relative_period_event_text",
        ):
            self.assertNotIn(forbidden, source)

    def test_story_admission_has_no_runtime_monkeypatch_of_detector_policy(self) -> None:
        source = Path("insight_desk/story_admission.py").read_text(encoding="utf-8")
        self.assertIn("class StoryAdmissionDecision", source)
        self.assertIn("StoryAdmissionStage.ROUTING", source)
        self.assertNotIn("detectors.visible_story_issues =", source)


if __name__ == "__main__":
    unittest.main()
