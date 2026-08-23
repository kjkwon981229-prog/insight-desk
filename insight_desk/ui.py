from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Mapping

from insight_desk.core import RenderMode, RenderedBriefing


@dataclass(frozen=True, slots=True)
class StoryViewModel:
    index: int
    event_id: str
    headline: str
    summary: str
    render_mode: RenderMode
    topic: str | None = None

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


def build_briefing_view_model(
    briefing: RenderedBriefing,
    *,
    topic_by_event: Mapping[str, str] | None = None,
) -> BriefingViewModel:
    """Build UI data using only already-rendered, verified fields plus explicitly supplied topics.

    No topic, confidence, key fact, trend, history, source label, or next-signal text is inferred.
    Missing optional UI data stays absent so the HTML renderer can omit that slot entirely.
    """

    topics = topic_by_event or {}
    stories = tuple(
        StoryViewModel(
            index=index,
            event_id=entry.event_id,
            headline=entry.headline,
            summary=entry.summary,
            render_mode=entry.render_mode,
            topic=topics.get(entry.event_id),
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
    return (
        f'<article class="story-row" data-event-id="{escape(story.event_id, quote=True)}">'
        f'<div class="story-index">{story.index:02d}</div>'
        '<div class="story-main">'
        f'<div class="story-meta">{metadata}</div>'
        f'<h3>{escape(story.headline)}</h3>'
        f'<p class="story-summary">{escape(story.summary)}</p>'
        '</div></article>'
    )


def render_briefing_html(view: BriefingViewModel) -> str:
    """Render a production briefing using the locked CSS without manufacturing missing UI facts."""

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
</body>
</html>
'''
