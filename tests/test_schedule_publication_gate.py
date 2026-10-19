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


class TwoEditionGateTests(unittest.TestCase):
    from scripts.schedule_publication_gate import Edition as _Edition

    EDITIONS = (
        _Edition(not_before=__import__("datetime").time(7, 30), starts=__import__("datetime").time(0, 0)),
        _Edition(not_before=__import__("datetime").time(18, 0), starts=__import__("datetime").time(15, 0)),
    )

    def _decide(self, kst_now: str, deployed: str):
        return decide_schedule_publication(
            now=datetime.fromisoformat(kst_now + "+09:00"),
            deployed_briefing_id=deployed,
            editions=self.EDITIONS,
        )

    def test_morning_edition_behaves_like_the_single_daily_gate(self) -> None:
        self.assertTrue(self._decide("2026-10-20T07:45:00", "daily-20261019T184000+0900").should_run)
        done = self._decide("2026-10-20T09:00:00", "daily-20261020T074000+0900")
        self.assertFalse(done.should_run)
        self.assertEqual(done.reason, "ALREADY_PUBLISHED_TODAY")

    def test_evening_edition_is_due_after_1800_when_only_the_morning_one_is_out(self) -> None:
        decision = self._decide("2026-10-20T18:05:00", "daily-20261020T074000+0900")
        self.assertTrue(decision.should_run)
        self.assertEqual(decision.reason, "EDITION_DUE")

    def test_evening_edition_is_not_repeated_once_published(self) -> None:
        decision = self._decide("2026-10-20T19:30:00", "daily-20261020T180900+0900")
        self.assertFalse(decision.should_run)
        self.assertEqual(decision.reason, "ALREADY_PUBLISHED_TODAY")

    def test_before_1800_the_evening_edition_is_not_due(self) -> None:
        self.assertFalse(self._decide("2026-10-20T17:59:00", "daily-20261020T074000+0900").should_run)

    def test_evening_trigger_with_yesterdays_page_still_publishes(self) -> None:
        self.assertTrue(self._decide("2026-10-20T18:05:00", "daily-20261019T184000+0900").should_run)

    def test_future_deployment_still_fails_closed(self) -> None:
        decision = self._decide("2026-10-20T18:05:00", "daily-20261021T074000+0900")
        self.assertEqual(decision.reason, "FUTURE_DEPLOYMENT_STATE")

    def test_shipped_edition_config_loads(self) -> None:
        from scripts.schedule_publication_gate import load_editions

        editions = load_editions(ROOT / "config" / "editions.json")
        self.assertEqual(len(editions), 2)


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
