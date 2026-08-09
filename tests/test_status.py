from __future__ import annotations

import unittest

from insight_desk.domain.models import CollectorStatus, RunStatus
from insight_desk.domain.status import is_publishable, resolve_status


def status(*, succeeded: int, failed: int = 0, partial: bool = False) -> CollectorStatus:
    return CollectorStatus(succeeded, succeeded, failed, partial, 1)


class StatusMachineTests(unittest.TestCase):
    def test_all_success(self) -> None:
        self.assertEqual(resolve_status(status(succeeded=1), status(succeeded=1)), RunStatus.COMPLETE)

    def test_news_only(self) -> None:
        self.assertEqual(resolve_status(status(succeeded=1), status(succeeded=0)), RunStatus.NEWS_ONLY)

    def test_trends_only(self) -> None:
        self.assertEqual(resolve_status(status(succeeded=0), status(succeeded=1)), RunStatus.TRENDS_ONLY)

    def test_partial_overrides_directional_status(self) -> None:
        self.assertEqual(
            resolve_status(status(succeeded=1, failed=1, partial=True), status(succeeded=0)),
            RunStatus.PARTIAL,
        )

    def test_total_failure(self) -> None:
        self.assertEqual(resolve_status(status(succeeded=0), status(succeeded=0)), RunStatus.TOTAL_FAILURE)

    def test_render_and_validation_failures_are_terminal(self) -> None:
        news = status(succeeded=1)
        trends = status(succeeded=1)
        self.assertEqual(resolve_status(news, trends, render_ok=False), RunStatus.RENDER_FAILURE)
        self.assertEqual(resolve_status(news, trends, validation_ok=False), RunStatus.VALIDATION_FAILURE)
        self.assertFalse(is_publishable(RunStatus.TOTAL_FAILURE))
