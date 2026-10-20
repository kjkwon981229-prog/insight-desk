from __future__ import annotations

from dataclasses import dataclass
from html import escape, unescape
from typing import Mapping
from urllib.parse import urlsplit

from insight_desk.core import RenderMode, RenderedBriefing, VerifiedPublication
from insight_desk.publication_identity_v2 import (
    PublicationIdentityManifest,
    manifest_from_mapping,
)


_TOPIC_DISPLAY_LABELS = {
    "ai_tech": "AI 테크",
    "AI·테크": "AI 테크",
    "economy": "경제",
    "경제·투자": "경제",
    "kpop": "K-POP",
    "엔터·음악·K-POP": "K-POP",
    "kbo_hanwha": "한화 이글스",
    "KBO·한화 이글스": "한화 이글스",
    "psat_recruitment": "공무원 시험",
    "PSAT·공채 일정": "공무원 시험",
    "baseball_sabermetrics": "야구 분석",
    "야구 세이버매트릭스": "야구 분석",
    "design_color_type": "디자인",
    "디자인·색·글꼴": "디자인",
    "contest_benefits": "공모전·혜택",
}

CORE_LINE_COUNT = 3

# One quiet tone per displayed topic (the CSS owns the colours); unknown labels fall back to tone 0.
_TOPIC_TONES = {
    "AI 테크": 0,
    "경제": 1,
    "K-POP": 2,
    "한화 이글스": 3,
    "공무원 시험": 4,
    "야구 분석": 5,
    "디자인": 6,
    "공모전·혜택": 7,
}


def _topic_tone(label: str) -> int:
    return _TOPIC_TONES.get(label, 0)


def _source_host(url: str | None) -> str:
    if not url:
        return ""
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


_WEEKDAYS = ("월", "화", "수", "목", "금", "토", "일")


def _date_title(briefing_id: str, fallback: str) -> tuple[str, str]:
    """('10월 19일 월요일', '07:00 갱신') from the briefing identity; the stored label if unparseable."""

    import re
    from datetime import datetime

    match = re.fullmatch(r"daily-(\d{8})T(\d{2})(\d{2})\d{2}[+-]\d{4}", briefing_id)
    if match is None:
        return fallback, ""
    try:
        day = datetime.strptime(match.group(1), "%Y%m%d")
    except ValueError:
        return fallback, ""
    weekday = _WEEKDAYS[day.weekday()]
    return f"{day.month}월 {day.day}일 {weekday}요일", f"{match.group(2)}:{match.group(3)} 갱신"


def _topic_display_label(topic: str) -> str:
    """Keep stable internal topic identifiers out of user-facing copy."""

    return _TOPIC_DISPLAY_LABELS.get(topic, topic)


@dataclass(frozen=True, slots=True)
class StoryViewModel:
    index: int
    event_id: str
    headline: str
    summary: str
    render_mode: RenderMode
    topic: str | None = None
    source_url: str | None = None
    selection_reason: str = ""
    core_lines: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.core_lines and (
            len(self.core_lines) != CORE_LINE_COUNT
            or any(not line.strip() for line in self.core_lines)
        ):
            raise ValueError(f"story core_lines must be exactly {CORE_LINE_COUNT} non-empty lines")
        if self.index < 1:
            raise ValueError("story index must be >= 1")
        if not self.event_id.strip():
            raise ValueError("story event_id must be non-empty")
        if not self.headline.strip():
            raise ValueError("story headline must be non-empty")
        if not self.summary.strip():
            raise ValueError("story summary must be non-empty")
        if self.topic is not None and not self.topic.strip():
            raise ValueError("story topic must be non-empty when provided")
        if self.source_url is not None:
            value = self.source_url.strip()
            parsed = urlsplit(value)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username is not None
                or parsed.password is not None
            ):
                raise ValueError("story source_url must be an HTTP(S) URL without credentials")
            object.__setattr__(self, "source_url", value)


@dataclass(frozen=True, slots=True)
class BriefingViewModel:
    briefing_id: str
    generated_label: str
    stories: tuple[StoryViewModel, ...]
    publication_manifest: PublicationIdentityManifest | None = None

    def __post_init__(self) -> None:
        if not self.briefing_id.strip():
            raise ValueError("briefing_id must be non-empty")
        if not self.generated_label.strip():
            raise ValueError("generated_label must be non-empty")
        event_ids = tuple(story.event_id for story in self.stories)
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("view model must not contain duplicate event ids")
        if self.publication_manifest is not None:
            if self.publication_manifest.briefing_id != self.briefing_id:
                raise ValueError("publication manifest belongs to another briefing")
            manifest_event_ids = tuple(
                publication.event_id
                for publication in self.publication_manifest.publications
            )
            if manifest_event_ids != event_ids:
                raise ValueError("publication manifest order/identity differs from PWA stories")


@dataclass(frozen=True, slots=True)
class PwaRuntimeConfig:
    push_worker_url: str | None = None

    def __post_init__(self) -> None:
        if self.push_worker_url is None:
            return
        value = self.push_worker_url.strip().rstrip("/")
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("push_worker_url must be an HTTPS origin/path without credentials, query, or fragment")
        object.__setattr__(self, "push_worker_url", value)


def _display_title(raw: str | None, fallback: str) -> str:
    if not raw:
        return fallback
    title = " ".join(unescape(raw).split())
    # 끝에 붙은 매체 이름(" - 매체", " | 매체")만 뗀다.
    for sep in (" - ", " | ", " — "):
        head, found, tail = title.rpartition(sep)
        if found and head and len(tail) <= 15:
            title = head.strip()
            break
    if not 8 <= len(title) <= 100:
        return fallback
    return title


def build_briefing_view_model(
    briefing: RenderedBriefing,
    *,
    topic_by_event: Mapping[str, str] | None = None,
    source_by_event: Mapping[str, str] | None = None,
    publication_by_event: Mapping[str, VerifiedPublication] | None = None,
    card_by_event: Mapping[str, tuple[str, tuple[str, ...]]] | None = None,
    title_by_event: Mapping[str, str] | None = None,
) -> BriefingViewModel:
    """Build UI data from verified fields without re-interpreting news meaning.

    Canonical V2 production supplies ``publication_by_event``. The resulting manifest preserves
    publication/event/source/verification/parent/time/authority identity in machine-readable PWA
    data while the visible card remains the already-verified headline, summary, topic, and source
    link. Legacy callers may omit the manifest.
    """

    topics = topic_by_event or {}
    sources = source_by_event or {}
    cards = card_by_event or {}
    titles = title_by_event or {}
    stories = tuple(
        StoryViewModel(
            index=index,
            event_id=entry.event_id,
            # 본문 중간 문장 대신 기사 원제를 보여 준다(원제가 없거나 너무 길면 검증된 헤드라인).
            headline=_display_title(titles.get(entry.event_id), entry.headline),
            summary=entry.summary,
            render_mode=entry.render_mode,
            topic=topics.get(entry.event_id),
            source_url=sources.get(entry.event_id),
            selection_reason=cards.get(entry.event_id, ("", ()))[0],
            core_lines=tuple(cards.get(entry.event_id, ("", ()))[1]),
        )
        for index, entry in enumerate(briefing.entries, start=1)
    )
    manifest = None
    if publication_by_event is not None:
        manifest = manifest_from_mapping(
            briefing.briefing_id,
            tuple(entry.event_id for entry in briefing.entries),
            publication_by_event,
        )
    return BriefingViewModel(
        briefing_id=briefing.briefing_id,
        generated_label=briefing.generated_at.strftime("%Y. %m. %d %H:%M"),
        stories=stories,
        publication_manifest=manifest,
    )


def _story_html(story: StoryViewModel) -> str:
    topic = (
        f'<span class="story-topic">{escape(_topic_display_label(story.topic))}</span>'
        if story.topic is not None
        else ""
    )
    tone = _topic_tone(_topic_display_label(story.topic)) if story.topic is not None else 0
    host = _source_host(story.source_url)
    host_html = f'<span class="story-host">{escape(host)}</span>' if host else ""
    metadata = f'<div class="story-meta" data-tone="{tone}">{topic}{host_html}</div>' if topic else ""
    source = (
        f'<a class="story-source" href="{escape(story.source_url, quote=True)}" '
        'target="_blank" rel="noopener noreferrer">원문</a>'
        if story.source_url is not None
        else ""
    )
    summary_matches_headline = story.summary.strip() == story.headline.strip()
    has_core_lines = bool(story.core_lines)
    if has_core_lines:
        # The verified headline/summary stay in the contract; the card shows the grounded core lines.
        summary = ""
        summary_elision = ' data-summary-elision="core-lines"'
    elif summary_matches_headline:
        summary = ""
        summary_elision = ' data-summary-elision="headline-collision"'
    else:
        summary = f'<p class="story-summary">{escape(story.summary)}</p>'
        summary_elision = ""
    reason = (
        f'<p class="story-reason">{escape(story.selection_reason)}</p>'
        if story.selection_reason
        else ""
    )
    core = (
        '<ul class="story-core">'
        + "".join(f"<li>{escape(line)}</li>" for line in story.core_lines)
        + "</ul>"
        if has_core_lines
        else ""
    )
    event_attr = escape(story.event_id, quote=True)
    actions = (
        '<div class="story-actions">'
        f'<button type="button" class="btn-good" data-action="good" data-event-id="{event_attr}">좋다</button>'
        f'<button type="button" class="btn-bad" data-action="bad" data-event-id="{event_attr}">별로다</button>'
        f'{source}'
        '</div>'
    )
    return (
        f'<article class="story-row" data-event-id="{event_attr}"'
        f'{summary_elision}>'
        f'<div class="story-index">{story.index:02d}</div>'
        '<div class="story-main">'
        f'{metadata}'
        f'<h3>{escape(story.headline)}</h3>'
        f'{reason}'
        f'{summary}'
        f'{core}'
        f'{actions}'
        '</div></article>'
    )


def _publication_contract_html(view: BriefingViewModel) -> str:
    manifest = view.publication_manifest
    if manifest is None:
        return ""
    # Prevent a source URL or identifier from terminating the JSON script element. JSON semantics
    # are preserved because these are standard Unicode escapes.
    payload = (
        manifest.canonical_json()
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
    return (
        '<script id="insight-desk-publication-contract" type="application/json" '
        f'data-publication-digest="{escape(manifest.sha256, quote=True)}">'
        f'{payload}</script>'
    )


def _push_html(config: PwaRuntimeConfig) -> tuple[str, str, str]:
    if config.push_worker_url is None:
        return "", "", ""
    worker_url = escape(config.push_worker_url, quote=True)
    head_meta = f'<meta name="insight-desk-push-worker-url" content="{worker_url}">'
    section = '''<section class="push-settings" data-push-settings data-push-service-worker-url="push-sw.js">
    <div>
      <span class="eyebrow">알림</span>
      <h2>새 브리핑 알림</h2>
      <p>새 브리핑이 준비되면 알려드립니다.</p>
    </div>
    <div class="push-actions">
      <button type="button" data-push-enable>알림 켜기</button>
      <button type="button" data-push-disable>알림 끄기</button>
    </div>
    <p class="push-status" data-push-status aria-live="polite">알림 상태를 확인 중입니다.</p>
  </section>'''
    script = '<script src="assets/js/push.js" defer></script>'
    return head_meta, section, script


def render_briefing_html(
    view: BriefingViewModel,
    *,
    runtime: PwaRuntimeConfig | None = None,
) -> str:
    """Render a production briefing using locked assets without manufacturing missing UI facts.

    The PWA manifest is always linked. Push controls are emitted only when an explicit HTTPS Worker
    URL is configured; otherwise no broken or misleading notification UI is shown. Canonical V2
    identity, when supplied, is emitted as inert JSON rather than inferred visible copy.
    """

    runtime_config = runtime or PwaRuntimeConfig()
    push_meta, push_section, push_script = _push_html(runtime_config)
    publication_contract = _publication_contract_html(view)
    story_count = len(view.stories)
    date_title, updated_label = _date_title(view.briefing_id, view.generated_label)
    if view.stories:
        stories = "".join(
            _story_html(story).replace(
                '<article class="story-row"',
                f'<article id="story-{story.index}" class="story-row"',
                1,
            )
            for story in view.stories
        )
        empty = ""
    else:
        stories = ""
        empty = '<p class="overview-empty">오늘 보여드릴 뉴스가 없습니다.</p>'

    return f'''<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#c35b78">
  {push_meta}
  <title>Insight Desk</title>
  <link rel="preload" href="assets/fonts/nanum-myeongjo-800.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="assets/fonts/gowun-batang-400.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="manifest" href="manifest.webmanifest">
  <link rel="stylesheet" href="assets/css/style.css">
</head>
<body>
<main class="shell" data-briefing-id="{escape(view.briefing_id, quote=True)}">
  <header class="site-header">
    <div class="brand-row">
      <a class="brand" href="#today">INSIGHT DESK</a>
      <div class="header-meta"><span>{escape(updated_label or view.generated_label)}</span></div>
    </div>
  </header>
  <section class="briefing-overview" id="today">
    <h1>{escape(date_title)}</h1>
    <p class="overview-status"><span class="overview-lede">오늘 알아둘 뉴스를 모았습니다.</span> <strong>{story_count}</strong>건</p>
    {empty}
  </section>
  <section class="content-section" id="stories" aria-label="오늘 볼 뉴스">
    <div class="story-list">{stories}</div>
  </section>
  <section class="content-section" id="collection" aria-label="모아보기">
    <div class="section-heading">
      <div><span class="section-index">02 / 모아보기</span><h2>좋다고 한 카드</h2></div>
    </div>
    <p class="overview-empty" id="collection-empty">좋다를 누른 카드가 여기에 모입니다. 이 기기에만 저장됩니다.</p>
    <div class="story-list" id="collection-list"></div>
  </section>
  <section class="content-section" id="settings" aria-label="설정">
    <div class="section-heading">
      <div><span class="section-index">03 / 설정</span><h2>설정</h2></div>
    </div>
    {push_section}
    <div class="data-settings">
      <p>좋다/별로다 기록과 모아본 카드는 이 기기에만 저장됩니다.</p>
      <button type="button" id="clear-saved">저장한 카드 모두 지우기</button>
    </div>
  </section>
  <footer>Insight Desk</footer>
</main>
<nav class="tabbar" aria-label="화면 이동">
  <a href="#today" data-view="today" aria-current="page">오늘</a>
  <a href="#collection" data-view="collection">모아보기</a>
  <a href="#settings" data-view="settings">설정</a>
</nav>
{publication_contract}
<script src="assets/js/feedback.js" defer></script>
{push_script}
</body>
</html>
'''
