"""Decide whether a delayed or redundant scheduler may publish today's briefing.

The gate is intentionally deterministic and fail-closed.  A scheduled trigger may proceed only
after the configured local publication time and only when the currently deployed Pages briefing
belongs to an earlier Korea-calendar date.  Network or contract ambiguity is left for the next
redundant trigger instead of risking a duplicate publication and notification.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, time, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import TextIO

KST = timezone(timedelta(hours=9))
DEFAULT_NOT_BEFORE = time(hour=7, minute=30)
_BRIEFING_ID_PATTERN = re.compile(r"^daily-(\d{8})T\d{6}[+-]\d{4}$")


class _BriefingIdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.briefing_id: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "main" or self.briefing_id is not None:
            return
        values = dict(attrs)
        candidate = values.get("data-briefing-id")
        if candidate:
            self.briefing_id = candidate.strip()


@dataclass(frozen=True, slots=True)
class SchedulePublicationDecision:
    should_run: bool
    reason: str
    local_date: str
    local_time: str
    not_before: str
    deployed_briefing_id: str | None
    deployed_date: str | None
    error_kind: str | None


def parse_deployed_briefing_id(html: str) -> str:
    parser = _BriefingIdParser()
    parser.feed(html)
    briefing_id = parser.briefing_id
    if briefing_id is None or _BRIEFING_ID_PATTERN.fullmatch(briefing_id) is None:
        raise ValueError("deployed page has no valid daily briefing identity")
    return briefing_id


def briefing_date(briefing_id: str) -> str:
    match = _BRIEFING_ID_PATTERN.fullmatch(briefing_id)
    if match is None:
        raise ValueError("invalid daily briefing identity")
    value = match.group(1)
    return datetime.strptime(value, "%Y%m%d").date().isoformat()


def decide_schedule_publication(
    *,
    now: datetime,
    deployed_briefing_id: str,
    not_before: time = DEFAULT_NOT_BEFORE,
) -> SchedulePublicationDecision:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    local_now = now.astimezone(KST)
    local_date = local_now.date().isoformat()
    local_clock = local_now.time().replace(tzinfo=None)
    deployed_date = briefing_date(deployed_briefing_id)

    common = {
        "local_date": local_date,
        "local_time": local_clock.isoformat(timespec="seconds"),
        "not_before": not_before.isoformat(timespec="minutes"),
        "deployed_briefing_id": deployed_briefing_id,
        "deployed_date": deployed_date,
        "error_kind": None,
    }
    if local_clock < not_before:
        return SchedulePublicationDecision(
            should_run=False,
            reason="BEFORE_PUBLICATION_WINDOW",
            **common,
        )
    if deployed_date == local_date:
        return SchedulePublicationDecision(
            should_run=False,
            reason="ALREADY_PUBLISHED_TODAY",
            **common,
        )
    if deployed_date > local_date:
        return SchedulePublicationDecision(
            should_run=False,
            reason="FUTURE_DEPLOYMENT_STATE",
            **common,
        )
    return SchedulePublicationDecision(
        should_run=True,
        reason="PUBLICATION_DUE",
        **common,
    )


def unavailable_decision(
    *,
    now: datetime,
    reason: str = "DEPLOYED_STATE_UNVERIFIED",
    not_before: time = DEFAULT_NOT_BEFORE,
    error_kind: str | None = None,
) -> SchedulePublicationDecision:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    local_now = now.astimezone(KST)
    return SchedulePublicationDecision(
        should_run=False,
        reason=reason,
        local_date=local_now.date().isoformat(),
        local_time=local_now.time().replace(tzinfo=None).isoformat(timespec="seconds"),
        not_before=not_before.isoformat(timespec="minutes"),
        deployed_briefing_id=None,
        deployed_date=None,
        error_kind=error_kind,
    )


def fetch_deployed_briefing_id(site_url: str, *, timeout_seconds: float = 15.0) -> str:
    request = urllib.request.Request(
        site_url,
        headers={
            "Accept": "text/html",
            "Cache-Control": "no-cache",
            "User-Agent": "InsightDesk-ScheduleGate/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        body = response.read(1_048_577)
    if len(body) > 1_048_576:
        raise ValueError("deployed page exceeds the bounded gate size")
    html = body.decode("utf-8")
    return parse_deployed_briefing_id(html)


def _write_github_outputs(handle: TextIO, decision: SchedulePublicationDecision) -> None:
    values = {
        "should_run": "true" if decision.should_run else "false",
        "reason": decision.reason,
        "local_date": decision.local_date,
        "deployed_date": decision.deployed_date or "unknown",
        "error_kind": decision.error_kind or "none",
    }
    for name, value in values.items():
        handle.write(f"{name}={value}\n")


def _parse_now(value: str | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("--now must include a UTC offset")
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-url", required=True)
    parser.add_argument("--output", default="build/schedule-publication-gate.json")
    parser.add_argument("--now", default=None)
    args = parser.parse_args()

    now = _parse_now(args.now)
    try:
        deployed_id = fetch_deployed_briefing_id(args.site_url)
        decision = decide_schedule_publication(now=now, deployed_briefing_id=deployed_id)
    except (ValueError, UnicodeError, urllib.error.URLError, TimeoutError, OSError) as exc:
        decision = unavailable_decision(now=now, error_kind=type(exc).__name__)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(asdict(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    github_output = os.environ.get("GITHUB_OUTPUT", "").strip()
    if github_output:
        with Path(github_output).open("a", encoding="utf-8") as handle:
            _write_github_outputs(handle, decision)

    print(
        "SCHEDULE_PUBLICATION_GATE "
        f"should_run={str(decision.should_run).lower()} "
        f"reason={decision.reason} "
        f"local_date={decision.local_date} "
        f"local_time={decision.local_time} "
        f"deployed_date={decision.deployed_date or 'unknown'} "
        f"error_kind={decision.error_kind or 'none'}"
    )


if __name__ == "__main__":
    main()
