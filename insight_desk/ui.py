from __future__ import annotations

from dataclasses import dataclass
from html import escape
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
}


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


def build_briefing_view_model(
    briefing: RenderedBriefing,
    *,
    topic_by_event: Mapping[str, str] | None = None,
    source_by_event: Mapping[str, str] | None = None,
    publication_by_event: Mapping[str, VerifiedPublication] | None = None,
) -> BriefingViewModel:
    """Build UI data from verified fields without re-interpreting news meaning.

    Canonical V2 production supplies ``publication_by_event``. The resulting manifest preserves
    publication/event/source/verification/parent/time/authority identity in machine-readable PWA
    data while the visible card remains the already-verified headline, summary, topic, and source
    link. Legacy callers may omit the manifest.
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
    metadata = f'<div class="story-meta">{topic}</div>' if topic else ""
    source = (
        f'<a class="story-source" href="{escape(story.source_url, quote=True)}" '
        'target="_blank" rel="noopener noreferrer">원문 보기</a>'
        if story.source_url is not None
        else ""
    )
    summary = (
        ""
        if story.summary.strip() == story.headline.strip()
        else f'<p class="story-summary">{escape(story.summary)}</p>'
    )
    return (
        f'<article class="story-row" data-event-id="{escape(story.event_id, quote=True)}">'
        f'<div class="story-index">{story.index:02d}</div>'
        '<div class="story-main">'
        f'{metadata}'
        f'<h3>{escape(story.headline)}</h3>'
        f'{summary}'
        f'{source}'
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
    if view.stories:
        lead_items = "".join(
            '<li class="lead-signal">'
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
        empty = '<p class="overview-empty">오늘 보여드릴 뉴스가 없습니다.</p>'

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
      <div class="header-meta"><span>{escape(view.generated_label)}</span></div>
    </div>
    <nav class="site-nav" aria-label="브리핑 탐색">
      <a href="#today" aria-current="page">오늘</a>
      <a href="#stories">오늘 볼 뉴스</a>
    </nav>
  </header>
  <section class="briefing-overview" id="today">
    <span class="eyebrow">오늘의 개인 브리핑</span>
    <h1>오늘의 브리핑</h1>
    <p class="overview-lede">오늘 알아둘 뉴스를 모았습니다.</p>
    <p class="overview-status"><strong>{story_count}</strong>건</p>
    {lead_block}
    {empty}
  </section>
  {push_section}
  <section class="content-section" id="stories">
    <div class="section-heading">
      <div><span class="section-index">01 / 오늘의 변화</span><h2>오늘 볼 뉴스</h2></div>
    </div>
    <div class="story-list">{stories}</div>
  </section>
  <footer>Insight Desk</footer>
</main>
{publication_contract}
{push_script}
</body>
</html>
'''
