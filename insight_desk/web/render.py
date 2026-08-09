from __future__ import annotations

import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

from ..domain.models import Briefing, RunStatus, TrendMetric, to_jsonable

CSS = """
:root {
  color-scheme: light dark;
  --bg: #f7f1ee;
  --surface: #fffaf8;
  --surface-strong: #f0e3e1;
  --text: #24202a;
  --muted: #6f6670;
  --line: #ded2d2;
  --navy: #263449;
  --pink: #b85d83;
  --pink-soft: #f2d6df;
  --blue: #547899;
  --danger: #8d3845;
  --shadow: 0 8px 26px rgba(38, 52, 73, .08);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #191820;
    --surface: #24222c;
    --surface-strong: #302b38;
    --text: #f4edf0;
    --muted: #b9aeb6;
    --line: #494150;
    --navy: #b9c8db;
    --pink: #e08bab;
    --pink-soft: #543747;
    --blue: #8db2d2;
    --danger: #ff9da8;
    --shadow: 0 8px 26px rgba(0, 0, 0, .22);
  }
}
* { box-sizing: border-box; }
html { overflow-x: hidden; }
body { margin: 0; background: var(--bg); color: var(--text); font: 16px/1.6 system-ui, -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans KR", sans-serif; overflow-wrap: anywhere; }
a { color: var(--blue); }
.wrap { width: min(100% - 28px, 960px); margin: 0 auto; }
header { padding: 34px 0 20px; }
.eyebrow { color: var(--pink); font-size: .78rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
h1, h2, h3 { color: var(--navy); line-height: 1.25; margin: 0 0 10px; }
h1 { font-size: clamp(1.7rem, 6vw, 2.7rem); letter-spacing: -.04em; }
h2 { font-size: 1.35rem; margin-top: 24px; }
h3 { font-size: 1.08rem; }
p { margin: 8px 0; }
.meta { color: var(--muted); font-size: .88rem; }
.nav { display: flex; flex-wrap: wrap; gap: 8px; margin: 18px 0 24px; }
.nav a { background: var(--surface); border: 1px solid var(--line); border-radius: 999px; min-height: 42px; padding: 8px 14px; text-decoration: none; }
.hero, .card, .metric { background: var(--surface); border: 1px solid var(--line); border-radius: 18px; box-shadow: var(--shadow); }
.hero { padding: 20px; }
.grid { display: grid; gap: 14px; }
.summary-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.summary { background: var(--surface-strong); border-radius: 14px; padding: 14px; }
.card { padding: 18px; }
.story-head { display: flex; gap: 10px; align-items: flex-start; justify-content: space-between; }
.story-head h3 { flex: 1; }
.badge { display: inline-flex; align-items: center; border-radius: 999px; border: 1px solid currentColor; font-size: .74rem; font-weight: 800; padding: 3px 8px; white-space: nowrap; }
.badge.complete { color: #2d7656; }
.badge.partial, .badge.news-only, .badge.trends-only { color: var(--pink); }
.badge.failure { color: var(--danger); }
.fact { border-left: 3px solid var(--pink); padding-left: 12px; }
.label { color: var(--muted); font-size: .78rem; font-weight: 800; letter-spacing: .03em; }
.metric-list { display: grid; gap: 10px; }
.metric { padding: 14px; box-shadow: none; }
.metric-top { display: flex; justify-content: space-between; gap: 12px; }
.metric-value { color: var(--pink); font-weight: 800; }
.spark { width: 100%; height: 52px; display: block; margin-top: 8px; }
.spark polyline { fill: none; stroke: var(--pink); stroke-width: 3; vector-effect: non-scaling-stroke; }
.spark line { stroke: var(--line); stroke-width: 1; vector-effect: non-scaling-stroke; }
.source-list, .archive-list { padding-left: 20px; }
.source-list li, .archive-list li { margin: 7px 0; }
.warning { color: var(--danger); }
footer { color: var(--muted); font-size: .82rem; padding: 30px 0 42px; }
code { overflow-wrap: anywhere; }
@media (max-width: 680px) {
  .summary-grid { grid-template-columns: 1fr; }
  .story-head { display: block; }
  .story-head .badge { margin-bottom: 8px; }
  .wrap { width: min(100% - 22px, 960px); }
  header { padding-top: 24px; }
}
""".strip() + "\n"


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _status_class(status: RunStatus) -> str:
    if status in {RunStatus.COMPLETE}:
        return "complete"
    if status in {RunStatus.PARTIAL, RunStatus.NEWS_ONLY, RunStatus.TRENDS_ONLY}:
        return "partial"
    return "failure"


def _status_label(status: RunStatus) -> str:
    return {
        RunStatus.COMPLETE: "정상 완료",
        RunStatus.NEWS_ONLY: "뉴스만 게시",
        RunStatus.TRENDS_ONLY: "트렌드만 게시",
        RunStatus.PARTIAL: "부분 성공",
        RunStatus.TOTAL_FAILURE: "전체 실패",
        RunStatus.RENDER_FAILURE: "렌더링 실패",
        RunStatus.VALIDATION_FAILURE: "검증 실패",
    }[status]


def _sparkline(metric: TrendMetric) -> str:
    values = [point.ratio for point in metric.points]
    if len(values) < 2:
        return "<p class=\"meta\">시계열 데이터 부족</p>"
    low, high = min(values), max(values)
    span = high - low or 1.0
    coords = []
    for index, value in enumerate(values):
        x = index / (len(values) - 1) * 100
        y = 46 - ((value - low) / span * 38)
        coords.append(f"{x:.1f},{y:.1f}")
    return f'<svg class="spark" viewBox="0 0 100 52" role="img" aria-label="{_esc(metric.group_name)} 상대 검색지수 그룹 내부 추이"><line x1="0" y1="46" x2="100" y2="46"/><polyline points="{" ".join(coords)}"/></svg>'


def _metric_card(metric: TrendMetric) -> str:
    change = "비교 기준 부족"
    if metric.change_percent is not None:
        change = f"직전 구간 대비 {metric.change_percent:+.1f}%"
    elif metric.delta is not None:
        change = f"직전 구간 대비 {metric.delta:+.2f}"
    return (
        '<article class="metric">'
        f'<div class="metric-top"><strong>{_esc(metric.group_name)}</strong><span class="metric-value">{_esc(metric.interpretation)}</span></div>'
        f'<div class="meta">{_esc(change)} · 축: 상대 검색지수 · 그룹 내부 흐름만 표시</div>'
        f"{_sparkline(metric)}"
        "</article>"
    )


def _story_card(story: object) -> str:
    return (
        '<article class="card">'
        '<div class="story-head">'
        f'<h3>{_esc(story.title)}</h3><span class="badge complete">확인된 기사 내용</span>'
        '</div>'
        f'<p class="meta">{_esc(story.topic_name)} · {story.source_count}개 출처 · 근거 {_esc(", ".join(story.evidence_ids))}</p>'
        f'<p class="fact">{_esc(story.summary)}</p>'
        f'<p><span class="label">왜 보나</span><br>{_esc(story.why_it_matters)}</p>'
        f'<p><span class="label">관심도와의 관계</span><br>{_esc(story.trend_relationship)}</p>'
        f'<p><span class="label">산업·투자 판단</span><br>{_esc(story.industry_impact)} { _esc(story.investment_relevance)}</p>'
        f'<p><span class="label">다음 확인</span><br>{_esc(" · ".join(story.watch_next))}</p>'
        '</article>'
    )


def _source_list(briefing: Briefing) -> str:
    unique: dict[str, object] = {}
    for item in briefing.news:
        url = item.original_url or item.naver_url
        if url:
            unique.setdefault(url, item)
    if not unique:
        return '<p class="meta">표시할 원문 링크가 없다.</p>'
    return '<ul class="source-list">' + "".join(
        f'<li><a href="{_esc(url)}" rel="noreferrer" target="_blank">{_esc(item.title)}</a><span class="meta"> · {_esc(item.source_domain)}</span></li>'
        for url, item in list(unique.items())[:30]
    ) + "</ul>"


def _document(briefing: Briefing, *, title: str, asset_prefix: str, nav_prefix: str) -> str:
    state = briefing.state
    status_class = _status_class(state.status)
    warning_html = "".join(f'<p class="warning">· {_esc(value)}</p>' for value in (*state.warnings, *state.errors))
    trend_html = "".join(_metric_card(metric) for metric in briefing.trend_metrics)
    story_html = "".join(_story_card(story) for story in briefing.stories)
    return f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="Insight Desk 모바일 뉴스·검색 관심도 브리핑"><title>{_esc(title)}</title>
<link rel="stylesheet" href="{_esc(asset_prefix)}assets/css/style.css"></head>
<body><main class="wrap">
<header><div class="eyebrow">Insight Desk · mobile briefing</div><h1>오늘의 관심사 브리핑</h1>
<p class="meta">기준 시각 {_esc(state.generated_at)} · 데이터 기준 {_esc(state.data_cutoff)} · 자동 분석은 결정론적 규칙만 사용</p>
<nav class="nav"><a href="{_esc(nav_prefix)}index.html">최신</a><a href="{_esc(nav_prefix)}archive/index.html">아카이브</a><a href="{_esc(nav_prefix)}data/latest.json">데이터 JSON</a></nav></header>
<section class="hero" aria-labelledby="state-heading"><div class="story-head"><h2 id="state-heading">실행 상태</h2><span class="badge {status_class}">{_esc(_status_label(state.status))}</span></div>
<p>{_esc(_state_sentence(state.status))}</p>{warning_html}</section>
<section aria-labelledby="summary-heading"><h2 id="summary-heading">오늘의 3줄 요약</h2><div class="grid summary-grid">{''.join(f'<p class="summary">{_esc(line)}</p>' for line in briefing.three_line_summary)}</div></section>
<section aria-labelledby="news-heading"><h2 id="news-heading">핵심 뉴스</h2><div class="grid">{story_html or '<p class="card">표시할 뉴스가 없다.</p>'}</div></section>
<section aria-labelledby="trend-heading"><h2 id="trend-heading">관심도 변화</h2><p class="meta">Search Trend의 ratio는 실제 검색 횟수가 아닌 상대 검색지수다. 서로 다른 API 배치의 절대값을 비교하지 않는다.</p><div class="metric-list">{trend_html or '<p class="card">표시할 트렌드 자료가 없다.</p>'}</div></section>
<section aria-labelledby="source-heading"><h2 id="source-heading">출처</h2><div class="card">{_source_list(briefing)}</div></section>
<section aria-labelledby="limit-heading"><h2 id="limit-heading">데이터 기준과 한계</h2><div class="card">{''.join(f'<p>· {_esc(item)}</p>' for item in briefing.limitations)}</div></section>
<footer>뉴스 전문을 복제하지 않고 제목·검색 요약·원문 링크만 사용한다. 투자 판단을 대신하지 않는다.</footer>
</main></body></html>'''


def _state_sentence(status: RunStatus) -> str:
    return {
        RunStatus.COMPLETE: "뉴스와 검색어 트렌드가 모두 성공해 최신 브리핑을 게시했다.",
        RunStatus.NEWS_ONLY: "뉴스는 게시했지만 검색어 트렌드 조회가 실패했다.",
        RunStatus.TRENDS_ONLY: "검색어 트렌드는 게시했지만 뉴스 조회가 실패했다.",
        RunStatus.PARTIAL: "일부 관심사 또는 배치가 실패해 성공한 데이터만 게시했다.",
        RunStatus.TOTAL_FAILURE: "새 데이터가 없어 이번 실행에서는 게시하지 않았다.",
        RunStatus.RENDER_FAILURE: "렌더링 오류로 새 결과를 게시하지 않았다.",
        RunStatus.VALIDATION_FAILURE: "산출물 검증 오류로 새 결과를 게시하지 않았다.",
    }[status]


def _archive_metadata(site_dir: Path) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for path in sorted((site_dir / "archive").glob("20??-??-??/data.json"), reverse=True):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(record, dict) and isinstance(record.get("date"), str):
            records.append({key: str(value) for key, value in record.items() if key in {"date", "status", "generated_at"}})
    return records


def render_site(briefing: Briefing, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "assets/css").mkdir(parents=True, exist_ok=True)
    (output_dir / "latest").mkdir(exist_ok=True)
    (output_dir / "archive").mkdir(exist_ok=True)
    (output_dir / "data").mkdir(exist_ok=True)
    (output_dir / "assets/css/style.css").write_text(CSS, encoding="utf-8")

    date_value = briefing.state.generated_at[:10]
    date_dir = output_dir / "archive" / date_value
    date_dir.mkdir(parents=True, exist_ok=True)
    payload = to_jsonable(briefing)
    payload_text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    (output_dir / "data/latest.json").write_text(payload_text, encoding="utf-8")
    (output_dir / "latest/data.json").write_text(payload_text, encoding="utf-8")
    (date_dir / "data.json").write_text(
        json.dumps(
            {"date": date_value, "status": briefing.state.status.value, "generated_at": briefing.state.generated_at},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "index.html").write_text(
        _document(briefing, title="Insight Desk · 최신 브리핑", asset_prefix="", nav_prefix=""), encoding="utf-8"
    )
    (output_dir / "latest/index.html").write_text(
        _document(briefing, title="Insight Desk · 최신 브리핑", asset_prefix="../", nav_prefix="../"), encoding="utf-8"
    )
    (date_dir / "index.html").write_text(
        _document(briefing, title=f"Insight Desk · {date_value}", asset_prefix="../../", nav_prefix="../../"), encoding="utf-8"
    )

    records = _archive_metadata(output_dir)
    (output_dir / "data/archives.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    archive_links = "".join(
        f'<li><a href="{_esc(record["date"])}/index.html">{_esc(record["date"])}</a> · {_esc(record.get("status", ""))} · {_esc(record.get("generated_at", ""))}</li>'
        for record in records
    )
    archive_html = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Insight Desk · 아카이브</title><link rel="stylesheet" href="../assets/css/style.css"></head><body><main class="wrap"><header><div class="eyebrow">Insight Desk · archive</div><h1>브리핑 아카이브</h1><nav class="nav"><a href="../index.html">최신</a><a href="../latest/index.html">최신 상세</a></nav></header><section class="card"><ul class="archive-list">{archive_links or '<li>저장된 브리핑이 없다.</li>'}</ul></section><footer>각 날짜 페이지는 해당 실행에서 게시된 정적 결과다.</footer></main></body></html>'''
    (output_dir / "archive/index.html").write_text(archive_html, encoding="utf-8")
