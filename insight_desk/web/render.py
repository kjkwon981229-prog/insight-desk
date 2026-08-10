from __future__ import annotations

import html
import json
import os
import shutil
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from ..domain.models import Briefing, RunStatus, TrendMetric, to_jsonable
from ..pipeline.synthesis import clean_headline
from ..pipeline.trend_metrics import effective_trend_state

CSS = r""":root {
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
  --accent-ink: #7d3049;
  --success: #36735c;
  --warning: #936329;
  --danger: #a34856;
  --dark-text: #fff9fa;
  --dark-muted: #c7bdc1;
  --shadow-soft: none;
  --radius-sm: 4px;
  --radius-md: 8px;
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
    --accent-ink: #f0a1b9;
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
.shell { width: min(calc(100% - 36px), 1120px); margin: 0 auto; padding-left: env(safe-area-inset-left); padding-right: env(safe-area-inset-right); }
.site-header { border-bottom: 1px solid var(--line); padding: max(24px, env(safe-area-inset-top)) 0 14px; }
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
.briefing-overview { border-bottom: 1px solid var(--line-strong); padding: clamp(34px, 7vw, 70px) 0 30px; }
.briefing-overview h1 { font-size: clamp(2.1rem, 8vw, 4rem); margin-top: 10px; }
.overview-lede { font-size: clamp(1rem, 2vw, 1.24rem); line-height: 1.5; margin-top: 15px; max-width: 720px; }
.overview-status { color: var(--muted-strong); font-size: .86rem; margin-top: 16px; }
.overview-status strong { color: var(--accent-strong); }
.freshness-banner { background: var(--accent-soft); border-left: 2px solid var(--accent); color: var(--muted-strong); font-size: .84rem; margin-top: 17px; padding: 9px 12px; }
.freshness-banner[hidden] { display: none; }
.lead-signals { display: grid; gap: 1px; grid-template-columns: repeat(3, minmax(0, 1fr)); list-style: none; margin: 28px 0 0; padding: 0; }
.lead-signal { border-left: 1px solid var(--line); min-width: 0; padding: 5px 18px 2px; }
.lead-signal:first-child { border-left: 2px solid var(--accent); padding-left: 17px; }
.lead-signal .label { color: var(--accent-strong); display: block; }
.lead-signal a { color: var(--text); display: block; font-size: .98rem; font-weight: 780; line-height: 1.35; margin-top: 5px; text-decoration: none; }
.lead-signal a:hover { color: var(--accent-strong); }
.overview-empty { color: var(--muted-strong); margin-top: 20px; }
.hero {
  display: grid;
  gap: clamp(28px, 6vw, 76px);
  grid-template-columns: minmax(0, 1.45fr) minmax(210px, .55fr);
  padding: clamp(46px, 8vw, 88px) 0 clamp(42px, 7vw, 72px);
}
.hero-main { background: var(--surface-dark); color: var(--dark-text); min-width: 0; padding: clamp(26px, 5vw, 54px); }
.hero-main h1 { color: var(--dark-text); }
.hero-main .hero-lede { color: var(--dark-text); }
.hero-main .status-line { color: var(--dark-muted); }
.hero-main .status-line strong { color: var(--dark-text); }
.hero-main .status-line.complete strong { color: var(--success); }
.hero-main .status-line.partial strong, .hero-main .status-line.news-only strong, .hero-main .status-line.trends-only strong { color: var(--warning); }
.hero-main .status-line.failure strong { color: var(--danger); }
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
.push-settings { border-bottom: 1px solid var(--line-strong); display: grid; gap: 18px; grid-template-columns: minmax(0, 1fr) auto; padding: 22px 0; }
.push-settings h2 { font-size: 1.08rem; margin-top: 4px; }
.push-settings p { color: var(--muted-strong); font-size: .86rem; margin-top: 6px; max-width: 650px; }
.push-actions { align-items: center; display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }
.push-actions button { background: var(--surface); border: 1px solid var(--line-strong); border-radius: var(--radius-sm); color: var(--text); cursor: pointer; font: inherit; font-size: .84rem; font-weight: 800; min-height: 44px; padding: 8px 13px; }
.push-actions button:first-child { background: var(--accent-soft); border-color: var(--accent); color: var(--accent-ink); }
.push-actions button:disabled { cursor: not-allowed; opacity: .48; }
.push-actions button:focus-visible { outline: 3px solid var(--accent); outline-offset: 3px; }
.push-status { grid-column: 1 / -1; margin-top: -7px !important; }
.push-status[data-tone="success"] { color: var(--success); font-weight: 800; }
.push-status[data-tone="warning"] { color: var(--warning); }
.signal-strip { border-bottom: 1px solid var(--line-strong); border-top: 1px solid var(--line-strong); display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
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
.story-row { display: grid; gap: 20px; grid-template-columns: 44px minmax(0, 1fr); padding: 28px 0 30px; }
.story-row + .story-row { border-top: 1px solid var(--line); }
.story-row.lead { padding-top: 28px; }
.story-index { color: var(--accent-strong); font-size: .83rem; letter-spacing: .05em; padding-top: 4px; }
.story-main { min-width: 0; }
.story-meta { color: var(--muted); flex-wrap: wrap; font-size: .78rem; gap: 4px 10px; margin-bottom: 8px; }
.story-topic { color: var(--accent-strong); font-weight: 800; }
.story-row h3 { max-width: 690px; }
.story-row.lead h3 { font-size: clamp(1.2rem, 2vw, 1.55rem); }
.story-summary { font-size: 1rem; line-height: 1.58; margin-top: 12px; max-width: 720px; }
.key-fact-panel { background: var(--accent-soft); border: 1px solid var(--line); border-left: 3px solid var(--accent); border-radius: var(--radius-sm); display: grid; gap: 12px; grid-template-columns: repeat(3, minmax(0, 1fr)); margin-top: 17px; max-width: 720px; padding: 12px 14px; }
.key-fact { min-width: 0; }
.key-fact + .key-fact { border-left: 1px solid var(--line); padding-left: 12px; }
.key-fact strong { color: var(--text); display: block; font-size: clamp(1.1rem, 3vw, 1.45rem); letter-spacing: -.04em; line-height: 1.2; margin-top: 4px; overflow-wrap: anywhere; }
.key-fact .fact-value { color: var(--muted-strong); display: block; font-size: .86rem; line-height: 1.4; margin-top: 4px; }
.evidence-line { border-bottom: 1px solid var(--line); border-top: 1px solid var(--line); flex-wrap: wrap; gap: 7px 12px; margin-top: 17px; padding: 10px 0; }
.evidence-line span { color: var(--muted-strong); font-size: .78rem; }
.evidence-line span + span::before { color: var(--line-strong); content: "·"; margin-right: 12px; }
.evidence-line .accent-mark { color: var(--accent-strong); font-weight: 800; }
.next-signal { background: var(--surface-muted); border-left: 2px solid var(--accent); border-radius: var(--radius-sm); margin-top: 15px; max-width: 720px; padding: 10px 13px; }
.next-signal .label { color: var(--accent-strong); display: block; }
.next-signal p { color: var(--muted-strong); font-size: .9rem; margin-top: 3px; }
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
footer { color: var(--muted); font-size: .78rem; padding: 38px 0 max(48px, env(safe-area-inset-bottom)); }
@media (max-width: 760px) {
  .shell { width: min(calc(100% - 24px), 1120px); }
  .site-header { padding-top: max(19px, env(safe-area-inset-top)); }
  .brand-row { align-items: flex-start; display: block; }
  .header-meta { justify-content: flex-start; margin-top: 9px; }
  .site-nav { gap: 14px; margin-top: 12px; }
  .briefing-overview { padding-top: 36px; }
  .briefing-overview h1 { font-size: clamp(2.05rem, 11vw, 3rem); }
  .lead-signals { grid-template-columns: 1fr; margin-top: 24px; }
  .lead-signal, .lead-signal:first-child { border-left: 0; border-top: 1px solid var(--line); padding: 12px 0 10px; }
  .lead-signal:first-child { border-left: 2px solid var(--accent); padding-left: 10px; }
  .signal-cell { padding-right: 10px; }
  .signal-cell + .signal-cell { padding-left: 10px; }
  .signal-value { font-size: 1.7rem; }
  .signal-label { font-size: .78rem; }
  .signal-note { font-size: .7rem; }
  .push-settings { grid-template-columns: 1fr; }
  .push-actions { justify-content: flex-start; }
  .push-status { grid-column: auto; }
  .content-section, .method-section { padding-top: 44px; }
  .section-heading { align-items: flex-start; display: block; }
  .section-heading .meta { margin-top: 7px; text-align: left; }
  .story-row { grid-template-columns: 30px minmax(0, 1fr); padding: 24px 0 27px; }
  .story-row.lead { padding-top: 28px; }
  .story-row.lead h3 { font-size: 1.2rem; }
  .key-fact-panel { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .key-fact:nth-child(3) { border-left: 0; grid-column: 1 / -1; padding-left: 0; padding-top: 8px; }
  .key-fact:nth-child(3) strong { font-size: 1rem; }
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

MANIFEST = {
    "name": "Insight Desk",
    "short_name": "Insight Desk",
    "start_url": ".",
    "scope": ".",
    "display": "standalone",
    "theme_color": "#c35b78",
    "background_color": "#f5f1ef",
    "description": "관심사별 뉴스와 검색 관심 흐름을 정리하는 모바일 브리핑",
    "icons": [
        {"src": "assets/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "assets/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
    ],
    "x-icon-status": "APPROVED_CANDIDATE_5_EXTRACTED",
    "x-icon-provenance": "인사이트 데스크 아이콘 탐구 보드의 Candidate 5 시안을 그대로 추출·리사이즈",
}


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _status_class(status: RunStatus) -> str:
    if status in {RunStatus.COMPLETE, RunStatus.VALID_EMPTY_DAY}:
        return "complete"
    if status in {RunStatus.PARTIAL, RunStatus.NEWS_ONLY, RunStatus.TRENDS_ONLY}:
        return str(status.value).lower().replace("_", "-")
    return "failure"


def _status_label(status: RunStatus | str) -> str:
    raw = getattr(status, "value", status)
    return {
        "COMPLETE": "정상 확인",
        "VALID_EMPTY_DAY": "유효한 빈 결과",
        "NEWS_ONLY": "뉴스만 확인",
        "TRENDS_ONLY": "관심도만 확인",
        "PARTIAL": "일부 확인",
        "TOTAL_FAILURE": "새 결과 없음",
        "RENDER_FAILURE": "게시 보류",
        "VALIDATION_FAILURE": "게시 보류",
        "FILTER_COLLAPSE": "편집 품질 게이트 충돌",
    }.get(str(raw), "상태 확인 필요")


def _status_sentence(status: RunStatus) -> str:
    return {
        RunStatus.COMPLETE: "뉴스와 검색 관심 흐름을 함께 확인할 수 있다.",
        RunStatus.VALID_EMPTY_DAY: "편집 기준을 충족한 새 변화가 없어 빈 브리핑을 게시했다.",
        RunStatus.NEWS_ONLY: "뉴스는 확인했지만 검색 관심 흐름은 이번 실행에서 빠졌다.",
        RunStatus.TRENDS_ONLY: "검색 관심 흐름은 확인했지만 뉴스는 이번 실행에서 빠졌다.",
        RunStatus.PARTIAL: "일부 관심사만 반영했다. 표시된 범위 안에서 읽는다.",
        RunStatus.TOTAL_FAILURE: "새로운 결과를 만들지 않아 이전 게시물을 유지한다.",
        RunStatus.RENDER_FAILURE: "새 결과를 게시하지 못했다.",
        RunStatus.VALIDATION_FAILURE: "새 결과를 게시하지 못했다.",
        RunStatus.FILTER_COLLAPSE: "편집 품질 게이트가 충돌해 새 결과를 게시하지 않았다.",
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


_PUBLISHER_NAMES = {
    "joongang.co.kr": "중앙일보",
    "chosun.com": "조선일보",
    "donga.com": "동아일보",
    "hankyung.com": "한국경제",
    "mk.co.kr": "매일경제",
    "yonhapnews.co.kr": "연합뉴스",
    "newsis.com": "뉴시스",
    "joynews24.com": "조이뉴스24",
    "bok.or.kr": "한국은행",
}


def _publisher_name(item: object) -> str:
    publisher = str(getattr(item, "publisher", "") or "").strip()
    if publisher:
        return publisher
    domain = str(getattr(item, "source_domain", "") or "").lower().removeprefix("www.")
    for known_domain, name in _PUBLISHER_NAMES.items():
        if domain == known_domain or domain.endswith("." + known_domain):
            return name
    return domain or "원문"


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
    state = effective_trend_state(metric)
    if state == "RISE":
        return "상승", "rise"
    if state == "FALL":
        return "하락", "fall"
    if state == "NO_MEANINGFUL_CHANGE":
        return "유지", "steady"
    return "확인 부족", "unknown"


def _trend_change(metric: TrendMetric) -> str:
    state = effective_trend_state(metric)
    if state == "INSUFFICIENT_COMPARISON":
        return "비교 기준 부족"
    if state == "NO_MEANINGFUL_CHANGE":
        return "유의미한 변화 없음"
    if metric.change_percent is not None:
        return f"직전 구간 대비 {metric.change_percent:+.1f}%"
    if metric.delta is not None:
        return f"직전 구간 대비 {metric.delta:+.2f}"
    return "비교 기준 부족"


def _trend_overview(metrics: tuple[TrendMetric, ...]) -> str:
    if not metrics:
        return "비교 자료 부족"
    states = tuple(effective_trend_state(metric) for metric in metrics)
    rising = states.count("RISE")
    falling = states.count("FALL")
    if rising and falling:
        return "그룹별 방향 혼조"
    if rising:
        return f"{rising}개 그룹 상승"
    if falling:
        return f"{falling}개 그룹 둔화"
    return "큰 변화 없음"


def _metric_row(metric: TrendMetric, topic_names: Mapping[str, str]) -> str:
    direction, direction_class = _trend_direction(metric)
    return (
        '<article class="trend-row">'
        '<div class="trend-copy">'
        f'<span class="trend-topic">{_esc(topic_names.get(metric.topic_id, "관심사"))}</span>'
        f'<h3>{_esc(metric.group_name)}</h3>'
        f'<p class="trend-change"><span class="trend-direction {direction_class}">{_esc(direction)}</span> · {_esc(_trend_change(metric))}</p>'
        '</div>'
        f'{_sparkline(metric)}'
        '</article>'
    )


def _story_items(story: object, news_by_id: Mapping[str, object]) -> list[object]:
    return [
        news_by_id[evidence_id]
        for evidence_id in getattr(story, "evidence_ids", ())
        if evidence_id in news_by_id
    ]


def _story_sources(story: object, news_by_id: Mapping[str, object]) -> str:
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
        source = _publisher_name(item)
        published = _format_published(getattr(item, "metadata_published_at", None) or getattr(item, "published_at", None))
        rows.append(
            '<li>'
            f'<a href="{_esc(url)}" rel="noreferrer" target="_blank">{_esc(clean_headline(getattr(item, "title", "원문 열기")))}</a>'
            f'<span class="meta">{_esc(source)} · {_esc(published)}</span>'
            '</li>'
        )
        for official in getattr(item, "authoritative_evidence", ()):
            official_url = str(getattr(official, "canonical_url", "") or "").strip()
            if not official_url.startswith("https://") or any(char.isspace() for char in official_url):
                continue
            if official_url in seen:
                continue
            seen.add(official_url)
            official_title = str(getattr(official, "title", "") or "공식 자료").strip()
            official_publisher = str(getattr(official, "publisher", "") or "공식 출처").strip()
            official_published = _format_published(getattr(official, "published_at", None))
            rows.append(
                '<li class="source-row">'
                f'<a href="{_esc(official_url)}" rel="noreferrer" target="_blank">{_esc(clean_headline(official_title))}</a>'
                f'<span class="meta">{_esc(official_publisher)} · 공식 자료 · {_esc(official_published)}</span>'
                '</li>'
            )
    return '<ul class="source-links">' + "".join(rows) + "</ul>" if rows else '<p class="meta">연결된 원문 링크가 없다.</p>'


def _story_evidence_line(story: object, news_by_id: Mapping[str, object]) -> str:
    facts = getattr(story, "facts", None)
    chips = [f'근거 {getattr(story, "source_count", 0)}곳']
    trend = str(getattr(story, "trend_relationship", "") or "")
    if trend:
        chips.append(trend)
    official_link = any(
        str(getattr(evidence, "canonical_url", "") or "").startswith("https://")
        for item in _story_items(story, news_by_id)
        for evidence in getattr(item, "authoritative_evidence", ())
    )
    if getattr(facts, "official_source", "") and official_link:
        chips.append("공식 자료")
    return "".join(
        f'<span class="{"accent-mark" if index == 0 else ""}">{_esc(chip)}</span>'
        for index, chip in enumerate(dict.fromkeys(chips))
    )


def _key_fact_panel(story: object) -> str:
    facts = getattr(story, "facts", None)
    if facts is None:
        return ""
    event_type = str(getattr(facts, "event_type", "OTHER"))
    facts_to_render: list[tuple[str, str]] = []
    numbers = tuple(getattr(facts, "key_numbers", ()) or ())
    changes = tuple(getattr(facts, "key_changes", ()) or ())
    if numbers and event_type in {
        "STATISTIC",
        "MARKET",
        "MARKET_MOVE",
        "EARNINGS",
        "AWARD_CHART",
        "INDUSTRY_CHANGE",
        "REGULATION",
    }:
        facts_to_render.append(("핵심 수치", numbers[0]))
        if changes:
            value = " ".join(str(changes[0]).split())
            if "..." in value or "…" in value or "··" in value:
                value = ""
            if len(value) > 30:
                value = ""
            if value and value != numbers[0] and value not in {"기록", "발표", "공개", "확인"}:
                facts_to_render.append(("변화", value))
    elif event_type in {
        "SCHEDULED_EVENT",
        "SPORTS_EVENT",
        "SPORTS_RESULT",
        "SPORTS_INTERRUPTION",
        "ROSTER_PERSONNEL",
        "ENTERTAINMENT_EVENT",
        "POLICY",
    }:
        if getattr(facts, "date", ""):
            facts_to_render.append(("일정", str(facts.date)))
        if getattr(facts, "location", ""):
            facts_to_render.append(("장소", str(facts.location)))
        if getattr(facts, "action", "") not in {"발표", "공개", "확인"} and (
            getattr(facts, "date", "") or getattr(facts, "location", "")
        ):
            facts_to_render.append(("내용", str(facts.action)))
    if not facts_to_render:
        return ""
    cells = "".join(
        f'<div class="key-fact"><span class="label">{_esc(label)}</span><strong>{_esc(value)}</strong></div>'
        for label, value in facts_to_render[:3]
    )
    return f'<div class="key-fact-panel" aria-label="핵심 사실">{cells}</div>'


def _next_signal_panel(story: object) -> str:
    watch_next = tuple(getattr(story, "watch_next", ()) or ())
    if not watch_next:
        return ""
    value = " · ".join(str(item) for item in watch_next)
    return f'<div class="next-signal"><span class="label">다음 신호</span><p>{_esc(value)}</p></div>'


def _story_row(story: object, news_by_id: Mapping[str, object], index: int) -> str:
    items = _story_items(story, news_by_id)
    first_item = items[0] if items else None
    published = getattr(first_item, "metadata_published_at", None) or getattr(first_item, "published_at", None)
    facts = getattr(story, "facts", None)
    uncertainty = str(getattr(facts, "uncertainty", "") or "")
    detail_blocks = [
        f'<div class="detail-block"><span class="label">확인된 내용</span><p>{_esc(getattr(story, "why_it_matters", ""))}</p></div>'
    ]
    if uncertainty:
        detail_blocks.append(
            f'<div class="detail-block"><span class="label">추가 확인</span><p>{_esc(uncertainty)}</p></div>'
        )
    details = (
        '<details class="story-details">'
        '<summary>전체 근거 보기</summary>'
        f'<div class="detail-grid">{"".join(detail_blocks)}</div>'
        f'{_story_sources(story, news_by_id)}'
        '</details>'
    )
    return (
        f'<article class="story-row" id="story-{index}">'
        f'<div class="story-index">{index:02d}</div>'
        '<div class="story-main">'
        '<div class="story-meta">'
        f'<span class="story-topic">{_esc(getattr(story, "topic_name", "관심사"))}</span>'
        f'<span>{_esc(_format_published(published))}</span>'
        '</div>'
        f'<h3>{_esc(getattr(story, "title", "제목 없음"))}</h3>'
        f'<p class="story-summary">{_esc(getattr(story, "summary", ""))}</p>'
        f'{_key_fact_panel(story)}'
        f'<div class="evidence-line">{_story_evidence_line(story, news_by_id)}</div>'
        f'{_next_signal_panel(story)}'
        f'{details}'
        '</div>'
        '</article>'
    )


def _signal_counts(briefing: Briefing) -> tuple[str, str, str]:
    rising = sum(1 for metric in briefing.trend_metrics if _trend_direction(metric)[0] == "상승")
    falling = sum(1 for metric in briefing.trend_metrics if _trend_direction(metric)[0] == "하락")
    trend_note = f"상승 {rising} · 하락 {falling}" if briefing.trend_metrics else "이번 실행에서 없음"
    if briefing.enrichment_attempted:
        enrichment = f"{briefing.enrichment_succeeded}/{briefing.enrichment_attempted}"
    else:
        enrichment = "–"
    return str(len(briefing.stories)), trend_note, enrichment


def _notice_html(briefing: Briefing) -> str:
    status = briefing.state.status
    messages = {
        RunStatus.NEWS_ONLY: "뉴스는 업데이트됐습니다. 검색 관심 데이터는 이번 브리핑에서 제외했습니다.",
        RunStatus.TRENDS_ONLY: "검색 관심 흐름은 업데이트됐습니다. 뉴스는 이번 브리핑에서 제외했습니다.",
        RunStatus.PARTIAL: "일부 관심사 또는 검색 요청이 지연되어 확인된 범위만 표시합니다.",
    }
    message = messages.get(status)
    if not message:
        return ""
    return f'<div class="notice" role="status">{_esc(message)}</div>'


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


def _nav_link(key: str, label: str, href: str, active_nav: str) -> str:
    current = ' aria-current="page"' if key == active_nav else ""
    return f'<a href="{_esc(href)}"{current}>{_esc(label)}</a>'


def _topic_names(briefing: Briefing) -> dict[str, str]:
    return {topic.id: topic.name for topic in briefing.topics}


def _represented_topics(briefing: Briefing) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            topic_id
            for story in briefing.stories
            for topic_id in (story.matched_topic_ids or (story.topic_id,))
        )
    )


def _lead_signals(briefing: Briefing, nav_prefix: str) -> str:
    names = _topic_names(briefing)
    rows: list[str] = []
    seen: set[str] = set()
    for index, story in enumerate(briefing.stories, 1):
        topic_id = story.topic_id
        if topic_id in seen:
            continue
        seen.add(topic_id)
        rows.append(
            '<li class="lead-signal">'
            f'<span class="label">{_esc(names.get(topic_id, story.topic_name))}</span>'
            f'<a href="{_esc(nav_prefix)}index.html#story-{index}">{_esc(story.title)}</a>'
            '</li>'
        )
        if len(rows) >= 3:
            break
    return "".join(rows) or '<li class="overview-empty">오늘은 표시 기준을 넘은 변화가 없다.</li>'


def _freshness_script() -> str:
    return """<script>
(function () {
  var banner = document.getElementById('freshness-banner');
  var page = document.querySelector('[data-latest-briefing]');
  if (!banner || !page) return;
  var generated = page.getAttribute('data-generated-date') || '';
  var dateParts = new Intl.DateTimeFormat('en-US', {timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit'}).formatToParts(new Date());
  var year = '', month = '', day = '';
  dateParts.forEach(function (part) { if (part.type === 'year') year = part.value; if (part.type === 'month') month = part.value; if (part.type === 'day') day = part.value; });
  var today = year + '-' + month + '-' + day;
  if (generated && generated < today) {
    banner.textContent = '최신 브리핑 · ' + generated.replace(/-/g, '.') + ' — 오늘 업데이트는 아직 완료되지 않았습니다.';
    banner.hidden = false;
  }
}());
</script>"""


def _push_worker_url() -> str:
    return os.environ.get("PUSH_WORKER_URL", "").strip()


def _pwa_head(asset_prefix: str) -> str:
    return (
        f'<link rel="manifest" href="{_esc(asset_prefix)}manifest.webmanifest">'
        f'<link rel="icon" type="image/png" sizes="32x32" href="{_esc(asset_prefix)}assets/icons/favicon.png">'
        f'<link rel="apple-touch-icon" sizes="180x180" href="{_esc(asset_prefix)}assets/icons/apple-touch-icon.png">'
        '<meta name="theme-color" content="#c35b78">'
        '<meta name="apple-mobile-web-app-capable" content="yes">'
        '<meta name="apple-mobile-web-app-status-bar-style" content="default">'
        '<meta name="apple-mobile-web-app-title" content="Insight Desk">'
        f'<meta name="insight-desk-push-worker-url" content="{_esc(_push_worker_url())}">'
    )


def _push_settings(asset_prefix: str) -> str:
    return (
        '<section class="push-settings" id="notifications" aria-labelledby="notifications-heading" '
        'data-push-settings '
        f'data-push-service-worker-url="{_esc(asset_prefix)}push-sw.js">'
        '<div><span class="section-index">알림 · 하루 한 번</span>'
        '<h2 id="notifications-heading">브리핑 상태 알림</h2>'
        '<p>오늘 브리핑이 준비됐거나 마지막 정상본을 유지할 때만 알려드립니다.</p></div>'
        '<div class="push-actions">'
        '<button type="button" data-push-enable>알림 켜기</button>'
        '<button type="button" data-push-disable>알림 끄기</button>'
        '</div>'
        '<p class="push-status" data-push-status role="status" aria-live="polite">알림 상태 확인 중…</p>'
        f'<script defer src="{_esc(asset_prefix)}assets/js/push.js"></script>'
        '</section>'
    )


def _document(
    briefing: Briefing,
    *,
    title: str,
    asset_prefix: str,
    nav_prefix: str,
    active_nav: str = "today",
    is_latest: bool = True,
) -> str:
    state = briefing.state
    status_class = _status_class(state.status)
    status_label = _status_label(state.status)
    news_by_id: Mapping[str, object] = {item.evidence_id: item for item in briefing.news}
    stories = briefing.stories
    stories_html = "".join(_story_row(story, news_by_id, index) for index, story in enumerate(stories, 1))
    represented = _represented_topics(briefing)
    topic_names = _topic_names(briefing)
    trend_html = "".join(_metric_row(metric, topic_names) for metric in briefing.trend_metrics)
    trend_note = _trend_overview(briefing.trend_metrics)
    limitation_html = "".join(f"<p>· {_esc(item)}</p>" for item in briefing.limitations)
    nav_items = (
        ("today", "오늘", f"{nav_prefix}index.html#today"),
        ("stories", "오늘 볼 뉴스", f"{nav_prefix}index.html#stories"),
        ("trends", "검색 흐름", f"{nav_prefix}index.html#trends"),
        ("archive", "아카이브", f"{nav_prefix}archive/index.html"),
    )
    nav_html = "".join(_nav_link(key, label, href, active_nav) for key, label, href in nav_items)
    latest_attrs = f' data-latest-briefing="true" data-generated-date="{_esc(state.generated_at[:10])}"' if is_latest else ""
    freshness_html = _freshness_script() if is_latest else ""
    push_html = _push_settings(asset_prefix) if is_latest else ""
    return f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="Insight Desk 모바일 뉴스·검색 관심 흐름 브리핑"><title>{_esc(title)}</title>
{_pwa_head(asset_prefix)}<link rel="stylesheet" href="{_esc(asset_prefix)}assets/css/style.css"></head>
<body><main class="shell"{latest_attrs}>
<header class="site-header"><div class="brand-row"><a class="brand" href="{_esc(nav_prefix)}index.html">INSIGHT DESK</a><div class="header-meta"><span>{_esc(_format_date(state.generated_at))}</span><span>기준 {_esc(_format_date(state.data_cutoff))}</span></div></div>
<nav class="site-nav" aria-label="브리핑 탐색">{nav_html}</nav></header>
<section class="briefing-overview" id="today" aria-labelledby="briefing-heading"><span class="eyebrow">오늘의 개인 브리핑 · {_esc(_format_date(state.generated_at))}</span><h1 id="briefing-heading">오늘의 브리핑</h1><p class="overview-lede">{_esc(briefing.three_line_summary[0] if briefing.three_line_summary else _status_sentence(state.status))}</p><p class="overview-status {status_class}"><strong>{_esc(status_label)}</strong> · {_esc(_status_sentence(state.status))}</p><div class="freshness-banner" id="freshness-banner" hidden role="status"></div><ul class="lead-signals" aria-label="관심사별 주요 신호">{_lead_signals(briefing, nav_prefix)}</ul></section>
{freshness_html}
{push_html}
{_notice_html(briefing)}
<section class="signal-strip" id="signals" aria-label="브리핑 범위"><div class="signal-cell"><span class="label">오늘의 범위</span><div class="signal-value">{_esc(str(len(stories)))}</div><span class="signal-label">주요 변화</span><span class="signal-note">{_esc(str(len(represented)))}개 관심사에서 확인</span></div><div class="signal-cell"><span class="label">검색 흐름</span><div class="signal-value">{_esc("있음" if briefing.trend_metrics else "없음")}</div><span class="signal-label">상대 관심지수</span><span class="signal-note">{_esc(trend_note)}</span></div></section>
<section class="content-section" id="stories" aria-labelledby="stories-heading"><div class="section-heading"><div><span class="section-index">01 / 오늘의 변화</span><h2 id="stories-heading">오늘 볼 뉴스</h2></div><p class="meta">관심사별로 고른 사건 단위 요약</p></div><div class="story-list">{stories_html or '<p class="meta empty-state">표시할 뉴스가 없다.</p>'}</div></section>
<section class="content-section" id="trends" aria-labelledby="trends-heading"><div class="section-heading"><div><span class="section-index">02 / 관심 변화</span><h2 id="trends-heading">검색 관심 흐름</h2></div><p class="meta">같은 그룹 안에서 직전 구간과 비교</p></div><div class="trend-overview"><span><strong>상대 관심지수</strong> · 원시 검색량이 아님</span><span>방향과 변화폭 중심으로 표시</span></div><div class="trend-list">{trend_html or '<p class="meta empty-state">이번 실행에서 검색 관심 흐름을 확인하지 못했다.</p>'}</div></section>
<section class="method-section" id="method" aria-labelledby="method-heading"><div class="section-heading"><div><span class="section-index">03 / 기준과 방법</span><h2 id="method-heading">데이터 기준</h2></div><p class="meta">기준 {_esc(_format_timestamp(state.generated_at))}</p></div>{_methodology(briefing, limitation_html)}</section>
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
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><meta name="description" content="Insight Desk 날짜별 브리핑 아카이브"><title>Insight Desk · 아카이브</title>{_pwa_head("../")}<link rel="stylesheet" href="../assets/css/style.css"></head><body><main class="shell"><header class="site-header"><div class="brand-row"><a class="brand" href="../index.html">INSIGHT DESK</a><div class="header-meta"><span>날짜별 목록</span></div></div><nav class="site-nav" aria-label="브리핑 탐색"><a href="../index.html">오늘</a><a href="../index.html#stories">오늘 볼 뉴스</a><a href="../index.html#trends">검색 흐름</a><a href="index.html" aria-current="page">아카이브</a></nav></header><section class="archive-hero"><span class="eyebrow">기록 · 날짜별 목록</span><h1>브리핑 아카이브</h1><p>날짜별 실행 결과를 문서처럼 다시 확인한다. 각 페이지는 해당 시점에 게시된 정적 브리핑이다.</p><p class="archive-count">{len(records)}개의 기록</p></section><section class="content-section" aria-labelledby="archive-heading"><div class="section-heading"><div><span class="section-index">01 / 날짜별 기록</span><h2 id="archive-heading">날짜별 기록</h2></div><p class="meta">최근 순</p></div><ol class="archive-index">{links}</ol></section><footer>Insight Desk · 정적 브리핑 기록</footer></main></body></html>'''


def _public_facts(facts: object) -> dict[str, object]:
    """Return only facts that are meaningful to a public reader."""

    fields = (
        "subject",
        "action",
        "object",
        "event_type",
        "date",
        "time",
        "location",
        "key_numbers",
        "key_changes",
        "official_source",
        "trend_state",
        "next_known_event",
        "uncertainty",
    )
    return {field: to_jsonable(getattr(facts, field, "")) for field in fields}


def _public_payload(briefing: Briefing) -> dict[str, object]:
    """Build the public data contract without exposing selection internals."""

    topics = [
        {"name": topic.name, "enabled": topic.enabled, "conditional": topic.conditional}
        for topic in briefing.topics
    ]
    stories = []
    for story in briefing.stories:
        stories.append(
            {
                "topic_name": story.topic_name,
                "title": story.title,
                "summary": story.summary,
                "why_it_matters": story.why_it_matters,
                "trend_relationship": story.trend_relationship,
                "industry_impact": story.industry_impact,
                "investment_relevance": story.investment_relevance,
                "watch_next": list(story.watch_next),
                "certainty": to_jsonable(story.certainty),
                "source_count": story.source_count,
                "provenance": to_jsonable(story.provenance),
                "facts": _public_facts(story.facts),
                "novelty": story.novelty,
            }
        )
    selected_evidence_ids = {
        evidence_id
        for story in briefing.stories
        for evidence_id in story.evidence_ids
    }
    news = []
    for item in briefing.news:
        # Public data is a story payload, not a rejected-candidate dump.  A
        # zero-story run therefore exposes no news objects at all.
        if item.evidence_id not in selected_evidence_ids:
            continue
        news.append(
            {
                "title": item.title,
                "summary": item.summary,
                "original_url": item.original_url,
                "naver_url": item.naver_url,
                "canonical_url": item.canonical_url,
                "published_at": item.published_at,
                "source_domain": item.source_domain,
                "metadata_title": item.metadata_title,
                "metadata_description": item.metadata_description,
                "metadata_canonical_url": item.metadata_canonical_url,
                "publisher": item.publisher,
                "metadata_published_at": item.metadata_published_at,
                "metadata_modified_at": item.metadata_modified_at,
                "provenance": to_jsonable(item.provenance),
            }
        )
    topic_names = {topic.id: topic.name for topic in briefing.topics}
    trend_metrics = []
    for metric in briefing.trend_metrics:
        trend_metrics.append(
            {
                "group_name": metric.group_name,
                "topic_name": topic_names.get(metric.topic_id, ""),
                "current_ratio": metric.current_ratio,
                "previous_ratio": metric.previous_ratio,
                "delta": metric.delta,
                "change_percent": metric.change_percent,
                "state": effective_trend_state(metric),
                "interpretation": metric.interpretation,
                "points": [{"period": point.period, "ratio": point.ratio} for point in metric.points],
            }
        )
    return {
        "state": to_jsonable(briefing.state),
        "topics": topics,
        "three_line_summary": list(briefing.three_line_summary),
        "stories": stories,
        "news": news,
        "trend_metrics": trend_metrics,
        "limitations": list(briefing.limitations),
    }


def render_site(briefing: Briefing, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "assets/css").mkdir(parents=True, exist_ok=True)
    (output_dir / "latest").mkdir(exist_ok=True)
    (output_dir / "archive").mkdir(exist_ok=True)
    (output_dir / "data").mkdir(exist_ok=True)
    (output_dir / "assets/css/style.css").write_text(CSS, encoding="utf-8")
    icon_source_dir = Path(__file__).resolve().parents[2] / "assets/icons"
    icon_output_dir = output_dir / "assets/icons"
    icon_output_dir.mkdir(parents=True, exist_ok=True)
    for icon_name in ("icon-192.png", "icon-512.png", "apple-touch-icon.png", "favicon.png"):
        shutil.copyfile(icon_source_dir / icon_name, icon_output_dir / icon_name)
    static_source_dir = Path(__file__).resolve().parents[2] / "assets"
    static_output_dir = output_dir / "assets/js"
    static_output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(static_source_dir / "js/push.js", static_output_dir / "push.js")
    shutil.copyfile(static_source_dir / "push-sw.js", output_dir / "push-sw.js")
    (output_dir / "manifest.webmanifest").write_text(
        json.dumps(MANIFEST, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    date_value = briefing.state.generated_at[:10]
    date_dir = output_dir / "archive" / date_value
    date_dir.mkdir(parents=True, exist_ok=True)
    payload = _public_payload(briefing)
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
            is_latest=False,
        ),
        encoding="utf-8",
    )

    records = _archive_metadata(output_dir)
    (output_dir / "data/archives.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "archive/index.html").write_text(_archive_page(records), encoding="utf-8")
