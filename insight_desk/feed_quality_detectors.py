from __future__ import annotations

import re

# Keep the accumulated low-level detector implementation byte-for-byte intact.
# This public façade adds only measured live-surface regressions; admission policy
# composition remains exclusively in story_admission.py.
from insight_desk._feed_quality_detectors_impl import *  # noqa: F401,F403
from insight_desk import _feed_quality_detectors_impl as _impl


_ORPHANED_REFERENTIAL_EVENT_RE = re.compile(
    r"^[가-힣A-Za-z0-9·&() ._-]{2,48}(?:은|는|,)?\s*이번\s+행사(?:에서|에는|에)(?:\s|$)"
)
_SUBJECTLESS_MARKET_HEADLINE_RE = re.compile(
    r"^장\s+(?:초반|중반|후반)\s+\d+(?:\.\d+)?%\s+(?:넘게\s+)?"
    r"(?:떨어지|오르|하락|상승)"
)
_MALFORMED_KBO_LEAGUE_YEAR_RE = re.compile(
    r"(?<!\d)\d{3}\s+신한(?:은행)?\s+(?:SOL(?:\s+Bank)?\s+)?KBO리그"
)
_GENERIC_LABOR_MANAGEMENT_RE = re.compile(r"^노사(?:는|가|의|,|\s)")
_REFERENTIAL_REPORT_LEAD_RE = re.compile(r"^(?:같은\s+)?보도(?:는|가)(?:\s|$)")


def _orphaned_referential_event(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    return _ORPHANED_REFERENTIAL_EVENT_RE.search(normalized) is not None


def _orphaned_visible_actor(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    return (
        _GENERIC_LABOR_MANAGEMENT_RE.search(normalized) is not None
        or _REFERENTIAL_REPORT_LEAD_RE.search(normalized) is not None
    )


def context_dependent_headline(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    return (
        _impl.context_dependent_headline(normalized)
        or _orphaned_referential_event(normalized)
        or _orphaned_visible_actor(normalized)
        or _SUBJECTLESS_MARKET_HEADLINE_RE.search(normalized) is not None
    )


def context_dependent_summary(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    return (
        _impl.context_dependent_summary(normalized)
        or _orphaned_referential_event(normalized)
        or _orphaned_visible_actor(normalized)
    )


def malformed_visible_text(value: str) -> bool:
    normalized = " ".join(value.split()).strip()
    return (
        _impl.malformed_visible_text(normalized)
        or _MALFORMED_KBO_LEAGUE_YEAR_RE.search(normalized) is not None
    )
