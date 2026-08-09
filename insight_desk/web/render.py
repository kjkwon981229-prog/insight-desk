from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path

from ..domain.models import Briefing, EvidenceType, RunStatus, TrendMetric, to_jsonable


CSS = r"""+:root {
  color-scheme: light;
  --bg: #f5f1ef;
  --surface: #fffdfb;
  --surface-muted: #eee9e7;
  --surface-dark: #20232b;
  --text: #20232b;
  --muted: #777178;
  --muted-strong: #5f5961;
  --line: #d8d1d0;
  --line-strong: #bcb3b5;
  --accent: #c35b78;
  --accent-strong: #943c59;
  --accent-soft: #f0d9e0;
  --success: #36735c;
  --warning: #936329;
  --danger: #a34856;
  --dark-text: #fff9fa;
  --dark-muted: #c7bdc1;
  --shadow-soft: 0 10px 28px rgba(45, 35, 39, .06);
  --radius-sm: 8px;
  --radius-md: 14px;
  --space-1: 6px;
  --space-2: 10px;
  --space-3: 14px;
  --space-4: 18px;
  --space-5: 26px;
  --space-6: 38px;
  --space-7: 56px;
}
@media (prefers-color-scheme: dark) {
  :root {
    color-scheme: dark;
    --bg: #17171b;
    --surface: #202026;
    --surface-muted: #2a252b;
    --surface-dark: #29232a;
    --text: #f7eff1;
    --muted: #b9adb2;
    --muted-strong: #d0c3c8;
    --line: #40393f;
    --line-strong: #62545c;
    --accent: #d27a98;
    --accent-strong: #f0a1b9;
    --accent-soft: #4c303c;
    --success: #91c8aa;
    --warning: #e0b27b;
    --danger: #f1a0aa;
    --dark-text: #fff9fa;
    --dark-muted: #d6c7cc;
    --shadow-soft: 0 12px 32px rgba(0, 0, 0, .22);
  }
}
* { box-sizing: border-box; }
html { overflow-x: hidden; scroll-behavior: smooth; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 15px/1.62 system-ui, -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans KR", sans-serif;
  letter-spacing: -.012em;
  overflow-x: hidden;
  overflow-wrap: anywhere;
  word-break: break-word;
}
a { color: var(--accent-strong); text-decoration-thickness: 1px; text-underline-offset: 3px; }
a:hover { color: var(--accent); }
a:focus-visible, summary:focus-visible { outline: 3px solid var(--accent); outline-offset: 4px; }
.shell { width: min(calc(100% - 36px), 1120px); margin: 0 auto; }
.site-header { border-bottom: 1px solid var(--line); padding: 24px 0 14px; }
.brand-row, .header-meta, .site-nav, .section-heading, .story-meta, .evidence-line, .method-summary, .archive-link, .source-row { display: flex; align-items: center; }
.brand-row { justify-content: space-between; gap: var(--space-3); }
.brand { color: var(--text); font-size: .78rem; font-weight: 900; letter-spacing: .19em; text-decoration: none; }
.header-meta { color: var(--muted); flex-wrap: wrap; font-size: .78rem; gap: 4px 12px; justify-content: flex-end; }
.header-meta span + span::before { color: var(--line-strong); content: "·"; margin-right: 12px; }
.site-nav { flex-wrap: wrap; gap: 16px; margin-top: 18px; }
.site-nav a { color: var(--muted-strong); font-size: .83rem; min-height: 40px; padding: 8px 0; text-decoration: none; }
.site-nav a:hover, .site-nav a[aria-current="page"] { color: var(--accent-strong); }
.site-nav a[aria-current="page"] { border-bottom: 2px solid var(--accent); font-weight: 800; }
.eyebrow, .section-index, .story-index, .label, .source-kind {
  color: var(--muted);
  font-size: .72rem;
  font-weight: 850;
  letter-spacing: .11em;
  text-transform: uppercase;
}
.eyebrow { color: var(--accent-strong); }
h1, h2, h3 { color: var(--text); line-height: 1.18; margin: 0; min-width: 0; }
h1 { font-size: clamp(2rem, 6vw, 4.6rem); letter-spacing: -.065em; }
h2 { font-size: clamp(1.45rem, 3vw, 2.25rem); letter-spacing: -.045em; }
h3 { font-size: clamp(1.2rem, 2vw, 1.55rem); letter-spacing: -.035em; }
p { margin: 0; }
.meta { color: var(--muted); font-size: .82rem; }
.hero {
  display: grid;
  gap: clamp(28px, 6vw, 76px);
  grid-template-columns: minmax(0, 1.45fr) minmax(210px, .55fr);
  padding: clamp(46px, 8vw, 88px) 0 clamp(42px, 7vw, 72px);
}
.hero-main { min-width: 0; }
.hero h1 { margin-top: 12px; max-width: 880px; }
.hero-lede { font-size: clamp(1.03rem, 2vw, 1.35rem); line-height: 1.55; margin-top: 24px; max-width: 680px; }
.hero-aside { align-self: end; border-left: 2px solid var(--accent); min-width: 0; padding: 4px 0 4px 20px; }
.hero-aside p + p { margin-top: 16px; }
.hero-aside .label { display: block; margin-bottom: 5px; }
.status-line { color: var(--muted-strong); font-size: .86rem; margin-top: 26px; }
.status-line strong { color: var(--text); font-weight: 800; }
.status-line.complete strong { color: var(--success); }
.status-line.partial strong, .status-line.news-only strong, .status-line.trends-only strong { color: var(--warning); }
.status-line.failure strong { color: var(--danger); }
.notice { border-left: 2px solid var(--warning); color: var(--muted-strong); margin-top: 20px; padding-left: 14px; }
.notice summary { color: var(--warning); cursor: pointer; font-weight: 800; min-height: 40px; padding: 7px 0; }
.notice ul { margin: 4px 0 12px; padding-left: 18px; }
.signal-strip { border-bottom: 1px solid var(--line-strong); border-top: 1px solid var(--line-strong); display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); }
.signal-cell { min-width: 0; padding: 18px 20px 17px 0; }
.signal-cell + .signal-cell { border-left: 1px solid var(--line); padding-left: 20px; }
.signal-value { color: var(--text); font-size: clamp(1.7rem, 4vw, 2.5rem); font-weight: 850; letter-spacing: -.07em; line-height: 1; margin-top: 8px; }
.signal-label { color: var(--muted-strong); font-size: .84rem; font-weight: 800; margin-top: 7px; }
.signal-note { color: var(--muted); display: block; font-size: .76rem; margin-top: 2px; }
.content-section { padding-top: var(--space-7); }
.section-heading { align-items: end; border-bottom: 1px solid var(--line-strong); gap: 16px; justify-content: space-between; padding-bottom: 13px; }
.section-heading h2 { margin-top: 5px; }
.section-heading .meta { text-align: right; }
.story-list { border-bottom: 1px solid var(--line); }
.story-row { display: grid; gap: 20px; grid-template-columns: 44px minmax(0, 1fr) minmax(190px, .38fr); padding: 28px 0 30px; }
.story-row + .story-row { border-top: 1px solid var(--line); }
.story-row.lead { padding-top: 34px; }
.story-index { color: var(--accent-strong); font-size: .83rem; letter-spacing: .05em; padding-top: 4px; }
.story-main { min-width: 0; }
.story-meta { color: var(--muted); flex-wrap: wrap; font-size: .78rem; gap: 4px 10px; margin-bottom: 8px; }
.story-topic { color: var(--accent-strong); font-weight: 800; }
.story-row h3 { max-width: 690px; }
.story-row.lead h3 { font-size: clamp(1.5rem, 4vw, 2.45rem); }
.story-summary { font-size: 1rem; line-height: 1.58; margin-top: 12px; max-width: 720px; }
.evidence-line { flex-wrap: wrap; gap: 7px 12px; margin-top: 16px; }
.evidence-line span { color: var(--muted-strong); font-size: .78rem; }
.evidence-line span + span::before { color: var(--line-strong); content: "·"; margin-right: 12px; }
.evidence-line .accent-mark { color: var(--accent-strong); font-weight: 800; }
.story-aside { border-left: 1px solid var(--line); min-width: 0; padding-left: 20px; }
.story-aside .label { display: block; margin-bottom: 6px; }
.story-aside p { color: var(--muted-strong); font-size: .88rem; line-height: 1.55; }
.story-details { border-top: 1px solid var(--line); margin-top: 20px; }
.story-details summary { color: var(--accent-strong); cursor: pointer; font-size: .86rem; font-weight: 800; min-height: 46px; padding: 12px 0; }
.detail-grid { display: grid; gap: 18px 24px; grid-template-columns: repeat(2, minmax(0, 1fr)); padding: 4px 0 20px; }
.detail-block .label { display: block; margin-bottom: 5px; }
.detail-block p, .watch-list, .source-links { color: var(--muted-strong); font-size: .88rem; }
.watch-list { margin: 0; padding: 0 0 18px 18px; }
.source-links { border-top: 1px solid var(--line); list-style: none; margin: 0; padding: 0; }
.source-links li { border-bottom: 1px solid var(--line); padding: 12px 0; }
.source-links a { display: block; font-weight: 750; }
.source-links .meta { display: block; margin-top: 2px; }
.trend-overview { border-bottom: 1px solid var(--line); display: flex; flex-wrap: wrap; gap: 8px 18px; padding: 17px 0; }
.trend-overview strong { color: var(--text); }
.trend-overview span { color: var(--muted-strong); font-size: .84rem; }
.trend-list { border-bottom: 1px solid var(--line); }
.trend-row { display: grid; gap: 22px; grid-template-columns: minmax(0, 1fr) minmax(150px, .42fr); padding: 22px 0; }
.trend-row + .trend-row { border-top: 1px solid var(--line); }
.trend-copy { min-width: 0; }
.trend-topic { color: var(--muted); font-size: .8rem; }
.trend-copy h3 { font-size: 1.15rem; margin-top: 4px; }
.trend-change { color: var(--muted-strong); font-size: .84rem; margin-top: 6px; }
.trend-direction { font-weight: 850; }
.trend-direction.rise { color: var(--accent-strong); }
.trend-direction.fall { color: var(--success); }
.trend-direction.steady { color: var(--muted-strong); }
.trend-direction.unknown { color: var(--warning); }
.trend-spark { align-self: center; display: block; height: 54px; max-width: 100%; width: 100%; }
.trend-spark polyline { fill: none; stroke: var(--accent); stroke-linecap: round; stroke-linejoin: round; stroke-width: 2.8; vector-effect: non-scaling-stroke; }
.trend-spark line { stroke: var(--line-strong); stroke-width: 1; vector-effect: non-scaling-stroke; }
.source-index { border-bottom: 1px solid var(--line); list-style: none; margin: 0; padding: 0; }
.source-row { align-items: baseline; gap: 12px; justify-content: space-between; padding: 14px 0; }
.source-row + .source-row { border-top: 1px solid var(--line); }
.source-row a { min-width: 0; overflow-wrap: anywhere; }
.source-row .meta { flex: 0 0 auto; text-align: right; }
.empty-state { padding: 24px 0; }
.method-section { padding: var(--space-7) 0 0; }
.method { border-bottom: 1px solid var(--line-strong); border-top: 1px solid var(--line-strong); }
.method summary { align-items: center; color: var(--text); cursor: pointer; display: flex; font-weight: 850; justify-content: space-between; min-height: 58px; padding: 12px 0; }
.method summary span:last-child { color: var(--muted); font-size: .78rem; font-weight: 650; }
.method-body { padding: 6px 0 22px; }
.definition-list { border-top: 1px solid var(--line); margin: 0; }
.definition-row { display: grid; gap: 16px; grid-template-columns: minmax(110px, .3fr) minmax(0, 1fr); padding: 13px 0; }
.definition-row + .definition-row { border-top: 1px solid var(--line); }
.definition-row dt { color: var(--muted-strong); font-weight: 800; }
.definition-row dd { color: var(--muted-strong); margin: 0; }
.limitations { border-left: 2px solid var(--accent); margin-top: 20px; padding-left: 14px; }
.limitations p + p { margin-top: 8px; }
.archive-hero { border-bottom: 1px solid var(--line-strong); padding: 54px 0 38px; }
.archive-hero h1 { margin-top: 10px; }
.archive-hero p { color: var(--muted-strong); margin-top: 15px; max-width: 580px; }
.archive-count { color: var(--muted); font-size: .82rem; margin-top: 30px; }
.archive-index { border-bottom: 1px solid var(--line-strong); list-style: none; margin: 0; padding: 0; }
.archive-item { border-top: 1px solid var(--line); }
.archive-link { color: var(--text); gap: 16px; justify-content: space-between; min-height: 78px; padding: 14px 0; text-decoration: none; }
.archive-date { min-width: 0; }
.archive-date strong { display: block; font-size: 1.14rem; }
.archive-date span { color: var(--muted); display: block; font-size: .8rem; margin-top: 2px; }
.archive-arrow { color: var(--accent-strong); font-size: 1.25rem; }
footer { color: var(--muted); font-size: .78rem; padding: 38px 0 48px; }
@media (max-width: 760px) {
  .shell { width: min(calc(100% - 24px), 1120px); }
  .site-header { padding-top: 19px; }
  .brand-row { align-items: flex-start; display: block; }
  .header-meta { justify-content: flex-start; margin-top: 9px; }
  .site-nav { gap: 14px; margin-top: 12px; }
  .hero { display: block; padding: 42px 0 38px; }
  .hero h1 { font-size: clamp(2rem, 10vw, 2.55rem); }
  .hero-aside { margin-top: 30px; }
  .signal-cell { padding-right: 10px; }
  .signal-cell + .signal-cell { padding-left: 10px; }
  .signal-value { font-size: 1.7rem; }
  .signal-label { font-size: .78rem; }
  .signal-note { font-size: .7rem; }
  .content-section, .method-section { padding-top: 44px; }
  .section-heading { align-items: flex-start; display: block; }
  .section-heading .meta { margin-top: 7px; text-align: left; }
  .story-row { grid-template-columns: 30px minmax(0, 1fr); padding: 24px 0 27px; }
  .story-row.lead { padding-top: 28px; }
  .story-aside { border-left: 0; border-top: 1px solid var(--line); grid-column: 2; padding: 16px 0 0; }
  .story-row.lead h3 { font-size: 1.55rem; }
  .detail-grid { grid-template-columns: 1fr; }
  .trend-row { grid-template-columns: 1fr; gap: 10px; }
  .trend-spark { height: 48px; }
  .source-row { align-items: flex-start; display: block; }
  .source-row .meta { display: block; margin-top: 3px; text-align: left; }
  .definition-row { grid-template-columns: 1fr; gap: 4px; }
}
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
}
""".strip() + "\n"


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _status_class(status: RunStatus) -> str:
    if status == RunStatus.COMPLETE:
        return "complete"
    if status in {RunStatus.PARTIAL, RunStatus.NEWS_ONLY, RunStatus.TRENDS_ONLY}:
        return status.value.lower().replace("_", "-")
    return "failure"


def _status_label(status: RunStatus | str) -> str:
    raw = getattr(status, "value", status)
    return {
        "COMPLETE": "정상 확인",
        "NEWS_ONLY": "뉴스만 확인",
        "TRENDS_ONLY": "관심도만 확인",
        "PARTIAL": "일부 확인",
        "TOTAL_FAILURE": "새 결과 없음",
        "RENDER_FAILURE": "게시 보류",
        "VALIDATION_FAILURE": "게시 보류",
    }.get(str(raw), "상태 확인 필요")


def _status_sentence(status: RunStatus) -> str:
    return {
        RunStatus.COMPLETE: "뉴스와 검색 관심 흐름을 함께 확인할 수 있다.",
        RunStatus.NEWS_ONLY: "뉴스는 확인했지만 검색 관심 흐름은 이번 실행에서 빠졌다.",
        RunStatus.TRENDS_ONLY: "검색 관심 흐름은 확인했지만 뉴스는 이번 실행에서 빠졌다.",
        RunStatus.PARTIAL: "일부 관심사만 반영했다. 표시된 범위 안에서 읽는다.",
        RunStatus.TOTAL_FAILURE: "새로운 결과를 만들지 않아 이전 게시물을 유지한다.",
        RunStatus.RENDER_FAILURE: "새 결과를 게시하지 못했다.",
        RunStatus.VALIDATION_FAILURE: "새 결과를 게시하지 못했다.",
    }[status]


def _format_timestamp(value: object) -> str:
    raw = str(value or "")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return raw
    return parsed.strftime("%Y. %m. %d. %H:%M KST")


def _format_date(value: object) -> str:
    raw = str(value or "")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return raw
    return parsed.strftime("%Y. %m. %d")


def _format_published(value: object) -> str:
    raw = str(value or "")
    if not raw:
        return "게시 시각 미확인"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return raw[:16]
    return parsed.strftime("%m.%d %H:%M")


def _provenance_label(value: object) -> str:
    raw = getattr(value, "value", value)
    return {
        "SEARCH_SNIPPET": "검색 결과",
        "ENRICHED_METADATA": "원문 보강",
        "OFFICIAL_SOURCE": "공식 자료",
    }.get(str(raw), str(raw))


def _provenance_values(item: object) -> set[str]:
    return {str(getattr(value, "value", value)) for value in getattr(item, "provenance", ())}


def _sparkline(metric: TrendMetric) -> str:
    values = [point.ratio for point in metric.points]
    if len(values) < 2:
        return '<p class="meta">비교 기준 부족</p>'
    low, high = min(values), max(values)
    span = high - low or 1.0
    coords = []
    for index, value in enumerate(values):
        x = index / (len(values) - 1) * 100
        y = 46 - ((value - low) / span * 38)
        coords.append(f"{x:.1f},{y:.1f}")
    label = f"{metric.group_name} 상대 관심 흐름"
    return (
        f'<svg class="trend-spark" viewBox="0 0 100 52" role="img" aria-label="{_esc(label)}">'
        '<line x1="0" y1="46" x2="100" y2="46"/>'
        f'<polyline points="{" ".join(coords)}"/>'
        "</svg>"
    )


def _trend_direction(metric: TrendMetric) -> tuple[str, str]:
    interpretation = metric.interpretation or ""
    if "상승" in interpretation or (metric.delta is not None and metric.delta > 0):
        return "상승", "rise"
    if "하락" in interpretation or (metric.delta is not None and metric.delta < 0):
        return "하락", "fall"
    if "유지" in interpretation:
        return "유지", "steady"
    return "확인 부족", "unknown"


def _trend_change(metric: TrendMetric) -> str:
    if metric.change_percent is not None:
        return f"직전 구간 대비 {metric.change_percent:+.1f}%"
    if metric.delta is not None:
        return f"직전 구간 대비 {metric.delta:+.2f}"
    return "비교 기준 부족"


def _metric_row(metric: TrendMetric) -> str:
    direction, direction_class = _trend_direction(metric)
    return (
        '<article class="trend-row">'
        '<div class="trend-copy">'
        f'<span class="trend-topic">{_esc(metric.topic_id)}</span>'
        f'<h3>{_esc(metric.group_name)}</h3>'
        f'<p class="trend-change"><span class="trend-direction {direction_class}">{_esc(direction)}</span> · {_esc(_trend_change(metric))}</p>'
        '</div>'
        f'{_sparkline(metric)}'
        '</article>'
    )


def _story_items(story: object, news_by_id: dict[str, object]) -> list[object]:
    return [
        news_by_id[evidence_id]
        for evidence_id in getattr(story, "evidence_ids", ())
        if evidence_id in news_by_id
    ]


def _story_sources(story: object, news_by_id: dict[str, object]) -> str:
    items = _story_items(story, news_by_id)
    if not items:
        return '<p class="meta">연결된 원문 링크가 없다.</p>'
    rows: list[str] = []
    seen: set[str] = set()
    for item in items:
        url = getattr(item, "original_url", "") or getattr(item, "naver_url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        source = getattr(item, "publisher", "") or getattr(item, "source_domain", "") or "원문"
        published = _format_published(getattr(item, "metadata_published_at", None) or getattr(item, "published_at", None))
        rows.append(
            '<li>'
            f'<a href="{_esc(url)}" rel="noreferrer" target="_blank">{_esc(getattr(item, "title", "원문 열기"))}</a>'
            f'<span class="meta">{_esc(source)} · {_esc(published)}</span>'
            '</li>'
        )
    return '<ul class="source-links">' + "".join(rows) + "</ul>" if rows else '<p class="meta">연결된 원문 링크가 없다.</p>'


def _story_source_names(story: object, news_by_id: dict[str, object]) -> str:
    names: list[str] = []
    for item in _story_items(story, news_by_id):
        name = getattr(item, "publisher", "") or getattr(item, "source_domain", "")
        if name and name not in names:
            names.append(name)
    if not names:
        return "출처 미확인"
    if len(names) > 3:
        return "· ".join(names[:3]) + f" 외 {len(names) - 3}곳"
    return "· ".join(names)


def _story_evidence_line(story: object, news_by_id: dict[str, object]) -> str:
    items = _story_items(story, news_by_id)
    chips = [f'{getattr(story, "source_count", 0)}곳에서 확인']
    provenance: list[str] = []
    for item in items:
        for value in getattr(item, "provenance", ()):
            label = _provenance_label(value)
            if label not in provenance:
                provenance.append(label)
    for value in getattr(story, "provenance", ()):
        label = _provenance_label(value)
        if label not in provenance:
            provenance.append(label)
    chips.extend(provenance)
    if getattr(story, "metadata_enriched_count", 0):
        chips.append(f'원문 {getattr(story, "metadata_enriched_count")}건 보강')
    return "".join(
        f'<span class="{"accent-mark" if index == 0 else ""}">{_esc(chip)}</span>'
        for index, chip in enumerate(dict.fromkeys(chips))
    )


def _story_row(story: object, news_by_id: dict[str, object], index: int) -> str:
    items = _story_items(story, news_by_id)
    first_item = items[0] if items else None
    published = getattr(first_item, "metadata_published_at", None) or getattr(first_item, "published_at", None)
    watch_next = getattr(story, "watch_next", ())
    watch_html = "".join(f"<li>{_esc(value)}</li>" for value in watch_next)
    return (
        f'<article class="story-row {"lead" if index == 1 else ""}">'
        f'<div class="story-index">{index:02d}</div>'
        '<div class="story-main">'
        '<div class="story-meta">'
        f'<span class="story-topic">{_esc(getattr(story, "topic_name", "관심사"))}</span>'
        f'<span>{_esc(_format_published(published))}</span>'
        '</div>'
        f'<h3>{_esc(getattr(story, "title", "제목 없음"))}</h3>'
        f'<p class="story-summary">{_esc(getattr(story, "summary", ""))}</p>'
        f'<div class="evidence-line">{_story_evidence_line(story, news_by_id)}</div>'
        '<details class="story-details">'
        '<summary>근거와 확인할 것</summary>'
        '<div class="detail-grid">'
        f'<div class="detail-block"><span class="label">핵심 해석</span><p>{_esc(getattr(story, "why_it_matters", ""))}</p></div>'
        f'<div class="detail-block"><span class="label">검색 관심 흐름</span><p>{_esc(getattr(story, "trend_relationship", ""))}</p></div>'
        '</div>'
        '<span class="label">확인할 것</span>'
        f'<ul class="watch-list">{watch_html or "<li>추가 확인 항목 없음</li>"}</ul>'
        f'{_story_sources(story, news_by_id)}'
        '</details>'
        '</div>'
        '<aside class="story-aside">'
        '<span class="label">출처 범위</span>'
        f'<p>{_esc(_story_source_names(story, news_by_id))}</p>'
        '</aside>'
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
    rows = []
    for url, item in list(unique.items())[:30]:
        source = item.publisher or item.source_domain or "원문"
        rows.append(
            '<li class="source-row">'
            f'<a href="{_esc(url)}" rel="noreferrer" target="_blank">{_esc(item.title)}</a>'
            f'<span class="meta">{_esc(source)}</span>'
            '</li>'
        )
    return '<ul class="source-index">' + "".join(rows) + "</ul>"


def _signal_counts(briefing: Briefing) -> tuple[str, str, str]:
    rising = sum(1 for metric in briefing.trend_metrics if _trend_direction(metric)[0] == "상승")
    falling = sum(1 for metric in briefing.trend_metrics if _trend_direction(metric)[0] == "하락")
    trend_note = f"상승 {rising} · 하락 {falling}" if briefing.trend_metrics else "이번 실행에서 없음"
    if briefing.enrichment_attempted:
        enrichment = f"{briefing.enrichment_succeeded}/{briefing.enrichment_attempted}"
        enrichment_note = "상위 원문 선택 보강"
    else:
        enrichment = "–"
        enrichment_note = "선택 보강 없음"
    return str(len(briefing.stories)), trend_note, enrichment


def _notice_html(briefing: Briefing) -> str:
    values = tuple(dict.fromkeys((*briefing.state.warnings, *briefing.state.errors, *briefing.state.render_errors)))
    if not values:
        return ""
    items = "".join(f"<li>{_esc(value)}</li>" for value in values)
    return f'<details class="notice"><summary>이번 실행의 범위 안내</summary><ul>{items}</ul></details>'


def _methodology(briefing: Briefing, limitation_html: str) -> str:
    state = briefing.state
    enrichment = (
        f"상위 원문 {briefing.enrichment_succeeded}/{briefing.enrichment_attempted}건을 선택적으로 보강했다."
        if briefing.enrichment_attempted
        else "상위 원문 선택 보강을 실행하지 않았다."
    )
    return (
        '<details class="method">'
        '<summary><span>데이터 기준과 읽는 법</span><span>필요할 때 펼치기</span></summary>'
        '<div class="method-body">'
        '<dl class="definition-list">'
        f'<div class="definition-row"><dt>생성 시각</dt><dd>{_esc(_format_timestamp(state.generated_at))}</dd></div>'
        f'<div class="definition-row"><dt>대상 기간</dt><dd>{_esc(_format_date(state.data_cutoff))}</dd></div>'
        '<div class="definition-row"><dt>뉴스 근거</dt><dd>NAVER 검색 결과의 제목·요약·원문 링크를 기본으로 사용한다.</dd></div>'
        f'<div class="definition-row"><dt>원문 보강</dt><dd>{_esc(enrichment)} 실패해도 검색 결과를 유지한다.</dd></div>'
        '<div class="definition-row"><dt>검색 관심지수</dt><dd>원시 검색량이 아닌 상대 지수다. 같은 키워드 그룹 안에서 직전 구간과 비교한다.</dd></div>'
        '<div class="definition-row"><dt>시간 해석</dt><dd>기사 게시 시각과 사건이 발생한 시각은 서로 다를 수 있다.</dd></div>'
        '</dl>'
        f'<div class="limitations"><span class="label">추가로 알아둘 점</span>{limitation_html}</div>'
        '</div>'
        '</details>'
    )


def _document(
    briefing: Briefing,
    *,
    title: str,
    asset_prefix: str,
    nav_prefix: str,
    active_nav: str = "today",
) -> str:
    state = briefing.state
    status_class = _status_class(state.status)
    status_label = _status_label(state.status)
    news_by_id = {item.evidence_id: item for item in briefing.news}
    stories = briefing.stories
    first_story = stories[0] if stories else None
    hero_title = getattr(first_story, "title", "이번 실행에서 새 결과가 없다.")
    hero_lede = getattr(first_story, "summary", "") or _status_sentence(state.status)
    summary_line = briefing.three_line_summary[1] if len(briefing.three_line_summary) > 1 else _status_sentence(state.status)
    stories_html = "".join(_story_row(story, news_by_id, index) for index, story in enumerate(stories, 1))
    signal_stories, signal_trends, signal_enrichment = _signal_counts(briefing)
    trend_html = "".join(_metric_row(metric) for metric in briefing.trend_metrics)
    limitation_html = "".join(f"<p>· {_esc(item)}</p>" for item in briefing.limitations)
    nav_items = (
        ("today", "오늘", f"{nav_prefix}index.html#today"),
        ("stories", "핵심 뉴스", f"{nav_prefix}index.html#stories"),
        ("trends", "검색 흐름", f"{nav_prefix}index.html#trends"),
        ("archive", "아카이브", f"{nav_prefix}archive/index.html"),
    )
    nav_html = "".join(
        f'<a href="{_esc(href)}" {"aria-current=\"page\"" if key == active_nav else ""}>{_esc(label)}</a>'
        for key, label, href in nav_items
    )
    return f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="Insight Desk 모바일 뉴스·검색 관심 흐름 브리핑"><title>{_esc(title)}</title>
<link rel="stylesheet" href="{_esc(asset_prefix)}assets/css/style.css"></head>
<body><main class="shell">
<header class="site-header"><div class="brand-row"><a class="brand" href="{_esc(nav_prefix)}index.html">INSIGHT DESK</a><div class="header-meta"><span>{_esc(_format_date(state.generated_at))}</span><span>기준 {_esc(_format_date(state.data_cutoff))}</span></div></div>
<nav class="site-nav" aria-label="브리핑 탐색">{nav_html}</nav></header>
<section class="hero" id="today" aria-labelledby="hero-heading"><div class="hero-main"><div class="eyebrow">오늘의 흐름 · { _esc(getattr(first_story, "topic_name", "Insight Desk")) }</div><h1 id="hero-heading">{_esc(hero_title)}</h1><p class="hero-lede">{_esc(hero_lede)}</p><p class="status-line {status_class}"><strong>{_esc(status_label)}</strong> · {_esc(_status_sentence(state.status))}</p></div>
<aside class="hero-aside"><span class="label">함께 본 신호</span><p>{_esc(summary_line)}</p><p class="meta">뉴스와 검색 관심 흐름의 동시 관찰만 표시하며, 인과관계는 단정하지 않는다.</p></aside></section>
{_notice_html(briefing)}
<section class="signal-strip" id="signals" aria-label="핵심 신호"><div class="signal-cell"><span class="label">주요 사건</span><div class="signal-value">{_esc(signal_stories)}</div><span class="signal-label">사건 묶음</span><span class="signal-note">뉴스 {len(briefing.news)}건</span></div><div class="signal-cell"><span class="label">검색 흐름</span><div class="signal-value">{_esc(str(len(briefing.trend_metrics)))}</div><span class="signal-label">키워드 그룹</span><span class="signal-note">{_esc(signal_trends)}</span></div><div class="signal-cell"><span class="label">원문 보강</span><div class="signal-value">{_esc(signal_enrichment)}</div><span class="signal-label">선택적 metadata</span><span class="signal-note">상위 기사에 한함</span></div></section>
<section class="content-section" id="stories" aria-labelledby="stories-heading"><div class="section-heading"><div><span class="section-index">01 / signals</span><h2 id="stories-heading">핵심 뉴스</h2></div><p class="meta">사건 단위로 묶은 주요 흐름</p></div><div class="story-list">{stories_html or '<p class="meta empty-state">표시할 뉴스가 없다.</p>'}</div></section>
<section class="content-section" id="trends" aria-labelledby="trends-heading"><div class="section-heading"><div><span class="section-index">02 / movement</span><h2 id="trends-heading">검색 관심 흐름</h2></div><p class="meta">같은 그룹 안에서 직전 구간과 비교</p></div><div class="trend-overview"><span><strong>상대 관심지수</strong> · 원시 검색량이 아님</span><span>방향과 변화폭 중심으로 표시</span></div><div class="trend-list">{trend_html or '<p class="meta empty-state">이번 실행에서 검색 관심 흐름을 확인하지 못했다.</p>'}</div></section>
<section class="content-section" id="sources" aria-labelledby="sources-heading"><div class="section-heading"><div><span class="section-index">03 / sources</span><h2 id="sources-heading">확인한 출처</h2></div><p class="meta">원문 링크를 열어 자세히 보기</p></div>{_source_list(briefing)}</section>
<section class="method-section" id="method" aria-labelledby="method-heading"><div class="section-heading"><div><span class="section-index">04 / reference</span><h2 id="method-heading">데이터 기준</h2></div><p class="meta">기준 {_esc(_format_timestamp(state.generated_at))}</p></div>{_methodology(briefing, limitation_html)}</section>
<footer>Insight Desk · 정적 브리핑 · 뉴스 전문을 복제하지 않고 제목·요약·원문 링크를 사용한다.</footer>
</main></body></html>'''


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


def _archive_page(records: list[dict[str, str]]) -> str:
    rows = []
    for index, record in enumerate(records, 1):
        date_value = record.get("date", "")
        status = _status_label(record.get("status", ""))
        generated = _format_timestamp(record.get("generated_at", ""))
        rows.append(
            f'<li class="archive-item"><a class="archive-link" href="{_esc(date_value)}/index.html">'
            f'<span class="story-index">{index:02d}</span><span class="archive-date"><strong>{_esc(_format_date(date_value))}</strong><span>{_esc(status)} · {_esc(generated)}</span></span><span class="archive-arrow" aria-hidden="true">→</span>'
            '</a></li>'
        )
    links = "".join(rows) or '<li class="archive-item"><span class="meta">저장된 브리핑이 없다.</span></li>'
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><meta name="description" content="Insight Desk 날짜별 브리핑 아카이브"><title>Insight Desk · 아카이브</title><link rel="stylesheet" href="../assets/css/style.css"></head><body><main class="shell"><header class="site-header"><div class="brand-row"><a class="brand" href="../index.html">INSIGHT DESK</a><div class="header-meta"><span>REFERENCE INDEX</span></div></div><nav class="site-nav" aria-label="브리핑 탐색"><a href="../index.html">오늘</a><a href="../index.html#stories">핵심 뉴스</a><a href="../index.html#trends">검색 흐름</a><a href="index.html" aria-current="page">아카이브</a></nav></header><section class="archive-hero"><span class="eyebrow">기록 · reference index</span><h1>브리핑 아카이브</h1><p>날짜별 실행 결과를 문서처럼 다시 확인한다. 각 페이지는 해당 시점에 게시된 정적 브리핑이다.</p><p class="archive-count">{len(records)}개의 기록</p></section><section class="content-section" aria-labelledby="archive-heading"><div class="section-heading"><div><span class="section-index">01 / archive</span><h2 id="archive-heading">날짜별 기록</h2></div><p class="meta">최근 순</p></div><ol class="archive-index">{links}</ol></section><footer>Insight Desk · 정적 브리핑 기록</footer></main></body></html>'''


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
        _document(briefing, title="Insight Desk · 최신 브리핑", asset_prefix="", nav_prefix="", active_nav="today"),
        encoding="utf-8",
    )
    (output_dir / "latest/index.html").write_text(
        _document(briefing, title="Insight Desk · 최신 브리핑", asset_prefix="../", nav_prefix="../", active_nav="today"),
        encoding="utf-8",
    )
    (date_dir / "index.html").write_text(
        _document(
            briefing,
            title=f"Insight Desk · {date_value}",
            asset_prefix="../../",
            nav_prefix="../../",
            active_nav="archive",
        ),
        encoding="utf-8",
    )

    records = _archive_metadata(output_dir)
    (output_dir / "data/archives.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "archive/index.html").write_text(_archive_page(records), encoding="utf-8")
