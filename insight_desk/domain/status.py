from __future__ import annotations

from .models import CollectorStatus, RunStatus


def resolve_status(
    news: CollectorStatus,
    trends: CollectorStatus,
    *,
    render_ok: bool = True,
    validation_ok: bool = True,
) -> RunStatus:
    """The only final-status decision point in the application."""

    if not render_ok:
        return RunStatus.RENDER_FAILURE
    if not validation_ok:
        return RunStatus.VALIDATION_FAILURE

    if not news.success and not trends.success:
        return RunStatus.TOTAL_FAILURE

    if news.partial or trends.partial:
        return RunStatus.PARTIAL
    if news.success and trends.success:
        return RunStatus.COMPLETE
    if news.success:
        return RunStatus.NEWS_ONLY
    return RunStatus.TRENDS_ONLY


def is_publishable(status: RunStatus) -> bool:
    return status in {
        RunStatus.COMPLETE,
        RunStatus.NEWS_ONLY,
        RunStatus.TRENDS_ONLY,
        RunStatus.PARTIAL,
    }
