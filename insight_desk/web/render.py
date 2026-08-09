from __future__ import annotations

import html
import json
import re
from datetime import datetime
from pathlib import Path

from ..domain.models import Briefing, RunStatus, TrendMetric, to_jsonable

CSS = """
:root {
  color-scheme: light;
  --bg: #fbf7f8;
  --surface: #fffdfd;
  --surface-soft: #fcf1f4;
  --surface-strong: #f3e3e9;
  --text: #25232b;
  --muted: #716a73;
  --line: #e6dce2;
  --navy: #293244;
  --accent: #b24d77;
  --accent-dark: #843451;
  --accent-soft: #f1d6e0;
  --blue: #476c8e;
  --success: #2f7658;
  --warning: #8b5d2e;
  --danger: #a03f4c;
  --hero-text: #fff8fa;
  --shadow-soft: 0 12px 34px rgba(41, 50, 68, .08);
  --radius-sm: 10px;
  --radius-md: 16px;
  --radius-lg: 22px;
  --space-1: 6px;
  --space-2: 10px;
  --space-3: 14px;
  --space-4: 18px;
  --space-5: 24px;
  --space-6: 32px;
}
@media (prefers-color-scheme: dark) {
  :root {
    color-scheme: dark;
    --bg: #191820;
    --surface: #24232c;
    --surface-soft: #30252e;
    --surface-strong: #342a34;
    --text: #f6eef1;
    --muted: #bdb0b8;
    --line: #4a414c;
    --navy: #f2e9ed;
    --accent: #df86a7;
    --accent-dark: #f0a2ba;
    --accent-soft: #543745;
    --blue: #a9c8e1;
    --success: #83c7a5;
    --warning: #e1b77f;
    --danger: #ffabb4;
    --hero-text: #fff8fa;
    --shadow-soft: 0 12px 34px rgba(0, 0, 0, .24);
  }
}
* { box-sizing: border-box; }
html { overflow-x: hidden; }
body { margin: 0; background: var(--bg); color: var(--text); font: 16px/1.6 system-ui, -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans KR", sans-serif; overflow-wrap: anywhere; word-break: break-word; }
a { color: var(--blue); }
a:focus-visible, summary:focus-visible { outline: 3px solid var(--accent); outline-offset: 3px; }
.wrap { width: min(calc(100% - 28px), 940px); margin: 0 auto; }
header { padding: 30px 0 18px; }
.masthead { display: flex; align-items: baseline; justify-content: space-between; gap: var(--space-3); }
.eyebrow { color: var(--accent); font-size: .75rem; font-weight: 850; letter-spacing: .1em; text-transform: uppercase; }
h1, h2, h3 { color: var(--navy); line-height: 1.25; margin: 0 0 10px; min-width: 0; }
h1 { font-size: clamp(1.8rem, 7vw, 3.1rem); letter-spacing: -.05em; }
h2 { font-size: 1.35rem; letter-spacing: -.02em; margin-top: var(--space-6); }
h3 { font-size: 1.12rem; }
p { margin: 8px 0; }
.meta { color: var(--muted); font-size: .86rem; }
.nav { display: flex; flex-wrap: wrap; gap: 8px; margin: var(--space-4) 0 var(--space-3); }
.nav a { display: inline-flex; align-items: center; background: var(--surface); border: 1px solid var(--line); border-radius: 999px; min-height: 44px; padding: 8px 14px; text-decoration: none; }
.hero, .card, .metric { min-width: 0; background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius-lg); box-shadow: var(--shadow-soft); }
.hero { background: var(--navy); border-color: var(--navy); color: var(--hero-text); padding: clamp(20px, 5vw, 34px); position: relative; overflow: hidden; }
.hero::after { content: ""; position: absolute; width: 150px; height: 150px; right: -65px; top: -65px; border: 1px solid rgba(255, 255, 255, .18); border-radius: 50%; }
.hero h1, .hero h2 { color: var(--hero-text); }
.hero .eyebrow { color: var(--accent-dark); background: var(--accent-soft); display: inline-flex; border-radius: 999px; padding: 3px 9px; letter-spacing: .07em; }
.hero .meta { color: rgba(255, 248, 250, .72); }
.hero .story-head { position: relative; z-index: 1; }
.hero-copy { max-width: 700px; position: relative; z-index: 1; }
.hero-lede { font-size: clamp(1.25rem, 5vw, 2rem); font-weight: 780; letter-spacing: -.035em; line-height: 1.3; margin: 18px 0 12px; }
.hero-summary { display: grid; gap: 8px; margin: 18px 0 0; padding: 0; list-style: none; color: rgba(255, 248, 250, .86); }
.hero-summary li { border-left: 2px solid var(--accent-dark); padding-left: 10px; }
.grid { display: grid; gap: var(--space-3); }
.summary-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.summary { min-width: 0; background: var(--surface-soft); border: 1px solid var(--line); border-radius: var(--radius-md); padding: var(--space-4); }
.summary .label { display: block; margin-bottom: 5px; }
.summary-value { color: var(--navy); font-size: 1.02rem; font-weight: 760; }
.card { padding: clamp(16px, 4vw, 22px); }
.section-head { align-items: end; display: flex; justify-content: space-between; gap: var(--space-3); }
.section-head h2 { margin-bottom: 4px; }
.story-grid { display: grid; gap: var(--space-3); }
.story-card { border-top: 4px solid var(--accent); }
.story-head { display: flex; gap: var(--space-3); align-items: flex-start; justify-content: space-between; }
.story-head h3 { flex: 1; }
.story-kicker { color: var(--accent); font-size: .76rem; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; }
.badge { display: inline-flex; align-items: center; border-radius: 999px; border: 1px solid currentColor; font-size: .74rem; font-weight: 800; line-height: 1.2; padding: 4px 9px; white-space: nowrap; }
.badge.complete { color: var(--success); }
.badge.partial, .badge.news-only, .badge.trends-only { color: var(--accent-dark); }
.badge.failure { color: var(--danger); }
.fact { border-left: 3px solid var(--accent); padding-left: 12px; font-size: 1.02rem; }
.label { color: var(--muted); font-size: .76rem; font-weight: 850; letter-spacing: .04em; text-transform: uppercase; }
.evidence-rail { display: flex; flex-wrap: wrap; gap: 7px; margin: 14px 0 2px; }
.evidence-chip { background: var(--surface-soft); border: 1px solid var(--line); border-radius: 999px; color: var(--text); font-size: .77rem; padding: 4px 9px; }
.evidence-chip strong { color: var(--accent-dark); }
.story-details { border-top: 1px solid var(--line); margin-top: 16px; padding-top: 2px; }
.story-details summary { color: var(--accent-dark); cursor: pointer; font-weight: 750; min-height: 44px; padding: 9px 0; }
.metric-list { display: grid; gap: var(--space-2); }
.metric { border-radius: var(--radius-md); box-shadow: none; padding: 16px; }
.metric-top { align-items: start; display: flex; justify-content: space-between; gap: 12px; }
.metric-top strong { min-width: 0; }
.metric-value { color: var(--accent-dark); font-weight: 850; text-align: right; }
.metric .meta { margin-top: 5px; }
.spark { width: 100%; max-width: 100%; height: 52px; display: block; margin-top: 8px; }
.spark polyline { fill: none; stroke: var(--accent); stroke-width: 3; vector-effect: non-scaling-stroke; }
.spark line { stroke: var(--line); stroke-width: 1; vector-effect: non-scaling-stroke; }
.source-list, .archive-list { list-style: none; margin: 0; padding: 0; }
.source-list li { border-bottom: 1px solid var(--line); padding: 10px 0; }
.source-list li:last-child { border-bottom: 0; }
.method { background: var(--surface-soft); border: 1px solid var(--line); border-radius: var(--radius-lg); padding: 0 var(--space-4); }
.method summary { cursor: pointer; font-size: 1.05rem; font-weight: 800; min-height: 52px; padding: 13px 0; }
.method-grid { display: grid; gap: var(--space-2); grid-template-columns: repeat(2, minmax(0, 1fr)); padding: 0 0 var(--space-4); }
.method-card { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius-sm); padding: 12px; }
.method-card p { margin: 4px 0 0; }
.warning { color: var(--danger); }
.archive-list { display: grid; gap: 10px; }
.archive-item { align-items: center; background: var(--surface-soft); border: 1px solid var(--line); border-radius: var(--radius-md); display: flex; justify-content: space-between; gap: 12px; min-height: 56px; padding: 10px 14px; }
.archive-item a { font-weight: 800; }
footer { color: var(--muted); font-size: .82rem; padding: 30px 0 42px; }
code { overflow-wrap: anywhere; }
@media (max-width: 680px) {
  .summary-grid, .method-grid { grid-template-columns: 1fr; }
  .story-head, .section-head { display: block; }
  .story-head .badge { margin-top: 8px; }
  .wrap { width: min(calc(100% - 22px), 940px); }
  header { padding-top: 24px; }
  .masthead { align-items: flex-start; display: block; }
  .metric-top { display: block; }
  .metric-value { display: block; margin-top: 4px; text-align: left; }
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
        f'<div class="meta">{_esc(change)} · 상대 관심지수 · 동일 그룹 내부 흐름</div>'
        f"{_sparkline(metric)}"
        "</article>"
    )


def _provenance_label(value: object) -> str:
    raw = getattr(value, "value", value)
    return {
        "SEARCH_SNIPPET": "검색 결과 근거",
        "ENRICHED_METADATA": "원문 metadata 보강",
        "OFFICIAL_SOURCE": "공식 출처",
    }.get(str(raw), str(raw))


def _story_card(story: object, news_by_id: dict[str, object]) -> str:
    provenance = tuple(getattr(story, "provenance", ()))
    chips = [
        f'<span class="evidence-chip">{_esc(story.source_count)}개 출처</span>',
        *(
            f'<span class="evidence-chip">{_esc(_provenance_label(value))}</span>'
            for value in provenance
        ),
    ]
    enriched_items = [
        news_by_id[evidence_id]
        for evidence_id in getattr(story, "evidence_ids", ())
        if evidence_id in news_by_id
        and "ENRICHED_METADATA" in {
            str(getattr(value, "value", value)) for value in getattr(news_by_id[evidence_id], "provenance", ())
        }
    ]
    metadata_html = ""
    if enriched_items:
        item = enriched_items[0]
        metadata_title = getattr(item, "metadata_title", "")
        publisher = getattr(item, "publisher", "")
        metadata_description = getattr(item, "metadata_description", "")
        detail = metadata_title or metadata_description
        if detail:
            publisher_html = f'<span class="meta"> · {_esc(publisher)}</span>' if publisher else ""
            metadata_html = (
                '<div class="fact"><span class="label">원문 metadata 보강</span>'
                f'<p>{_esc(detail)}{publisher_html}</p></div>'
            )
    if not metadata_html:
        metadata_html = '<p class="meta">기본 근거: NAVER 검색 결과의 제목·요약·링크</p>'
    return (
        '<article class="card story-card">'
        f'<div class="story-kicker">{_esc(story.topic_name)} · evidence brief</div>'
        '<div class="story-head">'
        f'<h3>{_esc(story.title)}</h3><span class="badge partial">검색 근거</span>'
        '</div>'
        f'<p class="meta">근거 ID {_esc(", ".join(story.evidence_ids))}</p>'
        f'<div class="evidence-rail">{"".join(chips)}</div>'
        f'<p class="fact">{_esc(story.summary)}</p>'
        f'{metadata_html}'
        '<details class="story-details"><summary>왜 중요한지와 다음 확인</summary>'
        f'<p><span class="label">왜 보나</span><br>{_esc(story.why_it_matters)}</p>'
        f'<p><span class="label">관심도와의 관계</span><br>{_esc(story.trend_relationship)}</p>'
        f'<p><span class="label">산업·투자 판단</span><br>{_esc(story.industry_impact)} {_esc(story.investment_relevance)}</p>'
        f'<p><span class="label">다음 확인</span><br>{_esc(" · ".join(story.watch_next))}</p>'
        '</details>'
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
    news_by_id = {item.evidence_id: item for item in briefing.news}
    story_html = "".join(_story_card(story, news_by_id) for story in briefing.stories)
    focal_line = briefing.three_line_summary[0] if briefing.three_line_summary else "선택한 관심사에서 표시할 결과가 없다."
    story_count = f"{len(briefing.stories)}개 사건" if briefing.stories else "뉴스 없음"
    trend_count = f"{len(briefing.trend_metrics)}개 그룹" if briefing.trend_metrics else "트렌드 없음"
    enrichment_value = (
        f"{briefing.enrichment_succeeded}/{briefing.enrichment_attempted}건 보강"
        if briefing.enrichment_attempted
        else "선택적 보강 대기"
    )
    limitation_html = "".join(f'<p>· {_esc(item)}</p>' for item in briefing.limitations)
    return f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="Insight Desk 모바일 뉴스·검색 관심도 브리핑"><title>{_esc(title)}</title>
<link rel="stylesheet" href="{_esc(asset_prefix)}assets/css/style.css"></head>
<body><main class="wrap">
<header><div class="masthead"><div class="eyebrow">Insight Desk · mobile briefing</div><span class="meta">EDITORIAL INTELLIGENCE</span></div><h1>오늘의 관심사 브리핑</h1>
<p class="meta">데이터 기준 {_esc(state.data_cutoff)} · 생성 {_esc(state.generated_at)} · 규칙 기반 분석</p>
<nav class="nav"><a href="{_esc(nav_prefix)}index.html">최신</a><a href="{_esc(nav_prefix)}archive/index.html">아카이브</a><a href="{_esc(nav_prefix)}data/latest.json">데이터 JSON</a></nav></header>
<section class="hero" aria-labelledby="state-heading"><div class="hero-copy"><div class="eyebrow">TODAY'S SIGNAL</div><div class="story-head"><h2 id="state-heading">오늘의 핵심 판단</h2><span class="badge {status_class}">{_esc(_status_label(state.status))}</span></div>
<p class="hero-lede">{_esc(focal_line)}</p><ul class="hero-summary">{''.join(f'<li>{_esc(line)}</li>' for line in briefing.three_line_summary[1:])}</ul>
<p class="meta">{_esc(_state_sentence(state.status))}</p>{warning_html}</div></section>
<section aria-labelledby="signal-heading"><div class="section-head"><div><h2 id="signal-heading">핵심 신호</h2><p class="meta">이번 실행에서 바로 확인할 수 있는 범위</p></div></div><div class="grid summary-grid">
<div class="summary"><span class="label">핵심 뉴스</span><div class="summary-value">{_esc(story_count)}</div></div>
<div class="summary"><span class="label">관심도 흐름</span><div class="summary-value">{_esc(trend_count)}</div></div>
<div class="summary"><span class="label">근거 보강</span><div class="summary-value">{_esc(enrichment_value)}</div></div>
</div></section>
<section aria-labelledby="news-heading"><div class="section-head"><div><h2 id="news-heading">핵심 뉴스</h2><p class="meta">검색 결과를 출발점으로 사건·근거·다음 확인을 묶었다.</p></div></div><div class="story-grid">{story_html or '<p class="card">표시할 뉴스가 없다.</p>'}</div></section>
<section aria-labelledby="trend-heading"><div class="section-head"><div><h2 id="trend-heading">관심도 변화</h2><p class="meta">상대 관심지수 · 동일 키워드 그룹 내부에서 직전 구간과 비교</p></div></div><div class="metric-list">{trend_html or '<p class="card">표시할 트렌드 자료가 없다.</p>'}</div></section>
<section aria-labelledby="source-heading"><h2 id="source-heading">출처</h2><div class="card">{_source_list(briefing)}</div></section>
<section aria-labelledby="method-heading"><h2 id="method-heading">데이터 기준</h2><details class="method"><summary>수집 범위와 방법론 보기</summary><div class="method-grid">
<div class="method-card"><span class="label">기준 시각</span><p>{_esc(state.generated_at)}<br><span class="meta">대상 기간 기준일 {_esc(state.data_cutoff)}</span></p></div>
<div class="method-card"><span class="label">뉴스 근거</span><p>제목·검색 요약·원문 링크<br><span class="meta">상위 기사 공개 metadata 선택 보강: {_esc(enrichment_value)}</span></p></div>
<div class="method-card"><span class="label">Trend 의미</span><p>원시 검색량이 아닌 상대 관심지수<br><span class="meta">서로 다른 그룹·배치의 절대값은 비교하지 않음</span></p></div>
<div class="method-card"><span class="label">시간 해석</span><p>게시 시각과 사건 시각을 구분<br><span class="meta">게시 시각이 사건 발생 시각을 뜻하지는 않음</span></p></div>
</div><div class="card">{limitation_html}</div></details></section>
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
        f'<li class="archive-item"><a href="{_esc(record["date"])}/index.html">{_esc(record["date"])}</a><span class="meta">{_esc(record.get("status", ""))} · {_esc(record.get("generated_at", ""))}</span></li>'
        for record in records
    )
    archive_html = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><meta name="description" content="Insight Desk 날짜별 브리핑 아카이브"><title>Insight Desk · 아카이브</title><link rel="stylesheet" href="../assets/css/style.css"></head><body><main class="wrap"><header><div class="masthead"><div class="eyebrow">Insight Desk · archive</div><span class="meta">REFERENCE INDEX</span></div><h1>브리핑 아카이브</h1><p class="meta">날짜별로 저장된 정적 리포트를 다시 확인합니다.</p><nav class="nav"><a href="../index.html">최신</a><a href="../latest/index.html">최신 상세</a></nav></header><section aria-labelledby="archive-heading"><h2 id="archive-heading">날짜별 보고서</h2><div class="card"><ul class="archive-list">{archive_links or '<li>저장된 브리핑이 없다.</li>'}</ul></div></section><footer>각 날짜 페이지는 해당 실행에서 게시된 정적 결과다.</footer></main></body></html>'''
    (output_dir / "archive/index.html").write_text(archive_html, encoding="utf-8")
