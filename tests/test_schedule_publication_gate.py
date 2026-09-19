from __future__ import annotations

import unittest
from datetime import UTC, datetime
from pathlib import Path

from scripts.schedule_publication_gate import (
    briefing_date,
    decide_schedule_publication,
    parse_deployed_briefing_id,
    unavailable_decision,
)

ROOT = Path(__file__).resolve().parents[1]


class SchedulePublicationGateTests(unittest.TestCase):
    def test_extracts_exact_daily_identity_from_deployed_main(self) -> None:
        html = '<main class="shell" data-briefing-id="daily-20260919T092939+0900">'
        briefing_id = parse_deployed_briefing_id(html)
        self.assertEqual(briefing_id, "daily-20260919T092939+0900")
        self.assertEqual(briefing_date(briefing_id), "2026-09-19")

    def test_impossible_calendar_date_is_not_accepted(self) -> None:
        with self.assertRaisesRegex(ValueError, "day is out of range"):
            briefing_date("daily-20260231T073000+0900")

    def test_redundant_early_trigger_cannot_publish_before_0730_kst(self) -> None:
        decision = decide_schedule_publication(
            now=datetime.fromisoformat("2026-09-18T22:29:59+00:00"),
            deployed_briefing_id="daily-20260918T093000+0900",
        )
        self.assertFalse(decision.should_run)
        self.assertEqual(decision.reason, "BEFORE_PUBLICATION_WINDOW")

    def test_first_due_trigger_can_publish_after_0730_kst(self) -> None:
        decision = decide_schedule_publication(
            now=datetime.fromisoformat("2026-09-18T22:30:00+00:00"),
            deployed_briefing_id="daily-20260918T093000+0900",
        )
        self.assertTrue(decision.should_run)
        self.assertEqual(decision.reason, "PUBLICATION_DUE")
        self.assertEqual(decision.local_date, "2026-09-19")

    def test_later_redundant_trigger_skips_after_same_day_deployment(self) -> None:
        decision = decide_schedule_publication(
            now=datetime.fromisoformat("2026-09-19T00:15:00+00:00"),
            deployed_briefing_id="daily-20260919T073800+0900",
        )
        self.assertFalse(decision.should_run)
        self.assertEqual(decision.reason, "ALREADY_PUBLISHED_TODAY")

    def test_future_deployment_identity_fails_closed(self) -> None:
        decision = decide_schedule_publication(
            now=datetime.fromisoformat("2026-09-19T00:15:00+00:00"),
            deployed_briefing_id="daily-20260920T073000+0900",
        )
        self.assertFalse(decision.should_run)
        self.assertEqual(decision.reason, "FUTURE_DEPLOYMENT_STATE")

    def test_unverified_pages_state_waits_for_next_redundant_trigger(self) -> None:
        decision = unavailable_decision(now=datetime(2026, 9, 19, 0, 15, tzinfo=UTC))
        self.assertFalse(decision.should_run)
        self.assertEqual(decision.reason, "DEPLOYED_STATE_UNVERIFIED")
        self.assertIsNone(decision.deployed_date)
        self.assertIsNone(decision.error_kind)

    def test_workflows_keep_a_fallback_and_double_duplicate_gate(self) -> None:
        production = (ROOT / ".github/workflows/insight-desk-production.yml").read_text(
            encoding="utf-8"
        )
        scheduler = (ROOT / ".github/workflows/insight-desk-scheduler.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn('timezone: "Asia/Seoul"', scheduler)
        self.assertIn('cron: "30 7 * * *"', scheduler)
        self.assertIn("actions: write", scheduler)
        self.assertIn("group: insight-desk-reliable-scheduler", scheduler)
        self.assertIn("cancel-in-progress: false", scheduler)
        self.assertIn("insight-desk-production.yml/dispatches", scheduler)
        self.assertIn('"200" && "$http_status" != "204"', scheduler)
        self.assertIn("scheduled_resilience", scheduler)
        self.assertIn("scripts/schedule_publication_gate.py", scheduler)
        self.assertIn("scripts/schedule_publication_gate.py", production)
        self.assertIn('cron: "17 8 * * *"', production)
        self.assertIn('timezone: "Asia/Seoul"', production)
        self.assertIn("needs.schedule_gate.result == 'skipped'", production)
        self.assertIn("github.event_name == 'pull_request'", production)
        self.assertIn(
            "cancel-in-progress: ${{ github.event_name == 'pull_request' }}",
            production,
        )


if __name__ == "__main__":
    unittest.main()
