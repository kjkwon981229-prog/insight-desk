from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from insight_desk.domain.models import (  # noqa: E402
    CollectorStatus,
    EvidenceType,
    NewsItem,
    RunState,
    RunStatus,
    Topic,
    TrendMetric,
    TrendPoint,
)
from insight_desk.pipeline.analysis import build_briefing  # noqa: E402
from insight_desk.pipeline.clustering import cluster_news  # noqa: E402
from insight_desk.pipeline.scoring import score_news  # noqa: E402
from insight_desk.web.render import render_site  # noqa: E402


def _item(case_id: str, index: int, raw: dict[str, object]) -> NewsItem:
    domain = str(raw["domain"])
    provenance = [EvidenceType.SEARCH_SNIPPET]
    if raw.get("official"):
        provenance.append(EvidenceType.OFFICIAL_SOURCE)
    evidence_id = f"{case_id}-{index}"
    return NewsItem(
        evidence_id=evidence_id,
        topic_id=case_id,
        query=str(raw["title"]),
        title=str(raw["title"]),
        summary=str(raw.get("summary", "")),
        original_url=f"https://{domain}/story/{evidence_id}",
        naver_url="",
        canonical_url=f"https://{domain}/story/{evidence_id}",
        published_at="2026-08-09T08:00:00+09:00",
        source_domain=domain,
        content_hash=evidence_id,
        score=10.0,
        provenance=tuple(provenance),
    )


def main() -> int:
    cases = json.loads((ROOT / "fixtures/synthesis_cases.json").read_text(encoding="utf-8"))
    topics = tuple(
        Topic(case_id, str(case["topic"]), True, False, 50, (str(case["topic"]),))
        for case_id, case in cases.items()
    )
    news = tuple(
        item
        for case_id, case in cases.items()
        for index, raw in enumerate(case["items"], 1)
        for item in (_item(case_id, index, raw),)
    )
    scored = score_news(news, topics, now=datetime.fromisoformat("2026-08-09T09:00:00+09:00"))
    points = (
        TrendPoint("fixture-rise", "AI 관심", "D_trend_rise", "2026-08-08", 40, "fixture"),
        TrendPoint("fixture-rise", "AI 관심", "D_trend_rise", "2026-08-09", 68, "fixture"),
        TrendPoint("fixture-flat", "K-POP 관심", "E_trend_flat", "2026-08-08", 50, "fixture"),
        TrendPoint("fixture-flat", "K-POP 관심", "E_trend_flat", "2026-08-09", 50, "fixture"),
    )
    trend_metrics = (
        TrendMetric("fixture-rise", "AI 관심", "D_trend_rise", "fixture", 68, 40, 50, 28, 70, 1, "상승", points[:2]),
        TrendMetric("fixture-flat", "K-POP 관심", "E_trend_flat", "fixture", 50, 50, 50, 0, 0, 0, "유지", points[2:]),
    )
    collection = CollectorStatus(len(news), len(news), 0, False, len(news))
    state = RunState(
        RunStatus.COMPLETE,
        True,
        "2026-08-09T09:00:00+09:00",
        "2026-08-09",
        "synthesis-fixture",
        collection,
        CollectorStatus(2, 2, 0, False, 2),
    )
    briefing = build_briefing(
        state=state,
        topics=topics,
        news=scored,
        clusters=cluster_news(scored),
        trend_metrics=trend_metrics,
        generated_at=datetime.fromisoformat("2026-08-09T09:00:00+09:00"),
    )
    output = ROOT / "build/synthesis-fixture-site"
    render_site(briefing, output)
    print(f"{briefing.state.status.value} {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
