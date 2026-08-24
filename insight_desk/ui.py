from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Mapping
from urllib.parse import urlsplit

from insight_desk.core import RenderMode, RenderedBriefing


@dataclass(frozen=True, slots=True)
class StoryViewModel:
    index: int
    event_id: str
    headline: str
    summary: str
    render_mode: RenderMode
    topic: str | None = None
    source_url: str | None = None

    def __post_init__(self) -> None:
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

    def __post_init__(self) -> None:
        if not self.briefing_id.strip():
            raise ValueError("briefing_id must be non-empty")
        if not self.generated_label.strip():
            raise ValueError("generated_label must be non-empty")
        event_ids = tuple(story.event_id for story in self.stories)
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("view model must not contain duplicate event ids")


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


def build_briefing_view_model(
    briefing: RenderedBriefing,
    *,
    topic_by_event: Mapping[str, str] | None = None,
    source_by_event: Mapping[str, str] | None = None,
) -> BriefingViewModel:
    """Build UI data using only verified fields plus explicitly supplied topics and source URLs.

    No topic, confidence, key fact, trend, history, source label, or next-signal text is inferred.
    Missing optional UI data stays absent so the HTML renderer can omit that slot entirely.
    """

    topics = topic_by_event or {}
    sources = source_by_event or {}
    stories = tuple(
        StoryViewModel(
            index=index,
            event_id=entry.event_id,
            headline=entry.headline,
            summary=entry.summary,
            render_mode=entry.render_mode,
            topic=topics.get(entry.event_id),
            source_url=sources.get(entry.event_id),
        )
        for index, entry in enumerate(briefing.entries, start=1)
    )
    return BriefingViewModel(
        briefing_id=briefing.briefing_id,
        generated_label=briefing.generated_at.strftime("%Y. %m. %d %H:%M"),
        stories=stories,
    )


def _story_html(story: StoryViewModel) -> str:
    topic = (
        f'<span class="story-topic">{escape(story.topic)}</span>'
        if story.topic is not None
        else ""
    )
    mode_label = (
        "원문 보존"
        if story.render_mode is RenderMode.EXTRACTIVE_FALLBACK
        else "검증된 재구성"
    )
    metadata = "".join(
        part
        for part in (
            topic,
            f'<span>{escape(mode_label)}</span>',
        )
        if part
    )
    source = (
        f'<a class="story-source" href="{escape(story.source_url, quote=True)}" '
        'target="_blank" rel="noopener noreferrer">원문 보기</a>'
        if story.source_url is not None
        else ""
    )
    return (
        f'<article class="story-row" data-event-id="{escape(story.event_id, quote=True)}">'
        f'<div class="story-index">{story.index:02d}</div>'
        '<div class="story-main">'
        f'<div class="story-meta">{metadata}</div>'
        f'<h3>{escape(story.headline)}</h3>'
        f'<p class="story-summary">{escape(story.summary)}</p>'
        f'{source}'
        '</div></article>'
    )


def _push_html(config: PwaRuntimeConfig) -> tuple[str, str, str]:
    if config.push_worker_url is None:
        return "", "", ""
    worker_url = escape(config.push_worker_url, quote=True)
    head_meta = f'<meta name="insight-desk-push-worker-url" content="{worker_url}">'
    section = '''<section class="push-settings" data-push-settings data-push-service-worker-url="push-sw.js">
    <div>
      <span class="eyebrow">웹 알림</span>
      <h2>브리핑 상태 알림</h2>
      <p>홈 화면에 추가한 앱에서 브리핑 준비 완료 또는 업데이트 실패 상태만 알립니다.</p>
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
    URL is configured; otherwise no broken or misleading notification UI is shown. The notification
    service worker is served from the Pages root so its `./` scope is valid without special headers.
    """

    runtime_config = runtime or PwaRuntimeConfig()
    push_meta, push_section, push_script = _push_html(runtime_config)
    story_count = len(view.stories)
    if view.stories:
        lead_items = "".join(
            '<li class="lead-signal">'
            '<span class="label">검증 뉴스</span>'
            f'<a href="#story-{story.index}">{escape(story.headline)}</a>'
            '</li>'
            for story in view.stories[:3]
        )
        lead_block = f'<ul class="lead-signals">{lead_items}</ul>'
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
        lead_block = ""
        stories = ""
        empty = '<p class="overview-empty">게시 가능한 검증 뉴스가 없습니다.</p>'

    return f'''<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#c35b78">
  {push_meta}
  <title>Insight Desk</title>
  <link rel="manifest" href="manifest.webmanifest">
  <link rel="stylesheet" href="assets/css/style.css">
</head>
<body>
<main class="shell" data-briefing-id="{escape(view.briefing_id, quote=True)}">
  <header class="site-header">
    <div class="brand-row">
      <a class="brand" href="#today">INSIGHT DESK</a>
      <div class="header-meta"><span>{escape(view.generated_label)}</span><span>VERIFIED</span></div>
    </div>
    <nav class="site-nav" aria-label="브리핑 탐색">
      <a href="#today" aria-current="page">오늘</a>
      <a href="#stories">오늘 볼 뉴스</a>
    </nav>
  </header>
  <section class="briefing-overview" id="today">
    <span class="eyebrow">오늘의 개인 브리핑</span>
    <h1>오늘의 브리핑</h1>
    <p class="overview-lede">검증을 통과한 뉴스만 표시합니다.</p>
    <p class="overview-status"><strong>{story_count}</strong>건 게시 가능</p>
    {lead_block}
    {empty}
  </section>
  {push_section}
  <section class="signal-strip" aria-label="브리핑 범위">
    <div class="signal-cell">
      <span class="label">게시 항목</span>
      <div class="signal-value">{story_count}</div>
      <span class="signal-label">검증 완료 뉴스</span>
      <span class="signal-note">SUPPORTED headline + summary only</span>
    </div>
  </section>
  <section class="content-section" id="stories">
    <div class="section-heading">
      <div><span class="section-index">01 / 오늘의 변화</span><h2>오늘 볼 뉴스</h2></div>
      <p class="meta">검증된 항목만 표시</p>
    </div>
    <div class="story-list">{stories}</div>
  </section>
  <footer>Insight Desk</footer>
</main>
{push_script}
</body>
</html>
'''
