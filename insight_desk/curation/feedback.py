from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable, Mapping

from .config import CurationConfig

GOOD_WEIGHT = 0.5
BAD_WEIGHT = -1.0


def adjust_by_topic(
    summary: Mapping[str, Any],
    label_to_topic_id: Mapping[str, str],
    cfg: CurationConfig,
) -> dict[str, float]:
    """Turn the worker's last-7-day vote counts into a per-topic score nudge (좋다 +0.5, 별로다 -1)."""
    topics = summary.get("topics") if isinstance(summary, Mapping) else None
    if not isinstance(topics, Mapping):
        return {}
    result: dict[str, float] = {}
    for label, counts in topics.items():
        topic_id = label_to_topic_id.get(str(label))
        if topic_id is None or not isinstance(counts, Mapping):
            continue
        good = counts.get("good")
        bad = counts.get("bad")
        if not (isinstance(good, int) and isinstance(bad, int)) or good < 0 or bad < 0:
            continue
        raw = good * GOOD_WEIGHT + bad * BAD_WEIGHT
        result[topic_id] = max(cfg.feedback_min, min(cfg.feedback_max, raw))
    return result


def fetch_feedback_summary(
    worker_url: str | None,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
    timeout: float = 8.0,
) -> dict[str, Any]:
    """Read vote counts from the push worker. Any failure means no feedback today, never a failed run."""
    if not worker_url or not worker_url.startswith("https://"):
        return {}
    request = urllib.request.Request(
        worker_url.rstrip("/") + "/feedback/summary",
        headers={"Accept": "application/json", "User-Agent": "InsightDesk/1.0"},
    )
    try:
        with opener(request, timeout=timeout) as response:
            payload = json.loads(response.read(200_000).decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError, UnicodeError):
        return {}
    return payload if isinstance(payload, dict) else {}
