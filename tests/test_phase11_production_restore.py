from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from scripts.phase11_daily_production import load_topics, stage_site, topic_relevant


class Phase11ProductionRestoreTests(unittest.TestCase):
    def test_enabled_topics_load_in_priority_order(self) -> None:
        topics = load_topics(Path("config/topics.json"))
        self.assertEqual(
            [topic.topic_id for topic in topics],
            ["ai_tech", "economy", "kpop", "kbo_hanwha", "psat_recruitment"],
        )
        self.assertTrue(all(topic.news_queries for topic in topics))
        self.assertTrue(all(topic.selection_cap >= 1 for topic in topics))

    def test_ascii_anchor_uses_token_boundary_not_incidental_substring(self) -> None:
        topic = next(topic for topic in load_topics(Path("config/topics.json")) if topic.topic_id == "ai_tech")
        self.assertTrue(topic_relevant(title="AI 투자 발표", body="기업이 AI 투자를 발표했다.", topic=topic))
        self.assertFalse(topic_relevant(title="Daily briefing", body="The company said it would invest.", topic=topic))

    def test_conditional_topic_requires_configured_intent_term(self) -> None:
        topic = next(topic for topic in load_topics(Path("config/topics.json")) if topic.topic_id == "psat_recruitment")
        self.assertFalse(topic_relevant(title="채용 일정 발표", body="기업 채용 일정이 공개됐다.", topic=topic))
        self.assertTrue(topic_relevant(title="국가공무원 채용 일정", body="인사혁신처가 5급 공채 일정을 발표했다.", topic=topic))

    def test_staged_site_contains_locked_pwa_assets_and_root_worker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "site"
            stage_site(output, "<!doctype html><html><body>verified</body></html>")
            self.assertTrue((output / "index.html").is_file())
            self.assertTrue((output / "manifest.webmanifest").is_file())
            self.assertTrue((output / "push-sw.js").is_file())
            self.assertTrue((output / "assets" / "css" / "style.css").is_file())
            self.assertTrue((output / "assets" / "js" / "push.js").is_file())
            self.assertEqual(
                (output / "push-sw.js").read_text(encoding="utf-8"),
                Path("push-sw.js").read_text(encoding="utf-8"),
            )

    def test_production_runner_does_not_restore_legacy_cli(self) -> None:
        source = Path("scripts/phase11_daily_production.py").read_text(encoding="utf-8")
        self.assertNotIn("insight_desk.cli", source)
        self.assertNotIn("validate_live_acceptance.py", source)
        self.assertNotIn("validate_artifact.py", source)
        for required in (
            "SemanticPipeline",
            "KiwiDeterministicFactExtractor",
            "Phase6EventEngine",
            "produce_phase7_entry_candidate",
            "build_rendered_briefing",
            "render_briefing_html",
            "ContractBundle",
        ):
            self.assertIn(required, source)

    def test_workflow_restores_schedule_pages_and_push_without_legacy_engine(self) -> None:
        workflow = Path(".github/workflows/insight-desk-production.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "30 22 * * *"', workflow)
        self.assertIn("branches: [main]", workflow)
        self.assertIn("actions/upload-pages-artifact@v4", workflow)
        self.assertIn("actions/deploy-pages@v4", workflow)
        self.assertIn("needs: [build, deploy]", workflow)
        self.assertIn("PUSH_WORKER_URL: ${{ vars.PUSH_WORKER_URL }}", workflow)
        self.assertIn("PUSH_SEND_TOKEN: ${{ secrets.PUSH_SEND_TOKEN }}", workflow)
        self.assertIn('notification_type="READY"', workflow)
        self.assertIn('notification_type="FAILURE"', workflow)
        self.assertIn("github.event_name != 'pull_request'", workflow)
        self.assertNotIn("python -m insight_desk.cli", workflow)
        self.assertNotIn("validate_live_acceptance.py", workflow)
        self.assertNotIn("validate_artifact.py", workflow)


if __name__ == "__main__":
    unittest.main()
