from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.core import RenderMode, RenderedBriefing, RenderedEntry
from insight_desk.ui import build_briefing_view_model, render_briefing_html


def briefing(*entries: RenderedEntry) -> RenderedBriefing:
    return RenderedBriefing(
        briefing_id="briefing:ui",
        generated_at=datetime(2026, 8, 23, 4, 10, tzinfo=timezone.utc),
        entries=tuple(entries),
    )


def entry(
    event_id: str = "event:ui",
    *,
    headline: str = "AI 공장 15억달러 수주",
    summary: str = "네오팩토리가 AI 공장 구축 사업을 15억달러에 수주했다.",
    render_mode: RenderMode = RenderMode.GENERATED,
) -> RenderedEntry:
    return RenderedEntry(
        event_id=event_id,
        headline=headline,
        summary=summary,
        claim_ids=(f"claim:{event_id}:headline", f"claim:{event_id}:summary"),
        render_mode=render_mode,
    )


class Phase8UIViewModelTests(unittest.TestCase):
    def test_view_model_copies_only_rendered_fields_and_explicit_topic(self) -> None:
        rendered = briefing(entry())
        plain = build_briefing_view_model(rendered)
        self.assertEqual(plain.stories[0].headline, rendered.entries[0].headline)
        self.assertEqual(plain.stories[0].summary, rendered.entries[0].summary)
        self.assertIsNone(plain.stories[0].topic)

        with_topic = build_briefing_view_model(
            rendered,
            topic_by_event={"event:ui": "AI·테크"},
        )
        self.assertEqual(with_topic.stories[0].topic, "AI·테크")

    def test_html_uses_locked_assets_and_omits_unsupported_sample_slots(self) -> None:
        html = render_briefing_html(build_briefing_view_model(briefing(entry())))
        self.assertIn('href="manifest.webmanifest"', html)
        self.assertIn('href="assets/css/style.css"', html)
        self.assertIn("AI 공장 15억달러 수주", html)
        self.assertNotIn("key-fact-panel", html)
        self.assertNotIn("next-signal", html)
        self.assertNotIn("검색 관심 흐름", html)
        self.assertNotIn("대표 뉴스 제목", html)
        self.assertNotIn("UI 샘플", html)
        self.assertNotIn("관심사", html)

    def test_html_escapes_verified_text_and_ids_instead_of_interpreting_markup(self) -> None:
        hostile = entry(
            event_id='event:"x"',
            headline='<script>alert("x")</script>',
            summary="A & B < C",
        )
        html = render_briefing_html(build_briefing_view_model(briefing(hostile)))
        self.assertNotIn('<script>alert("x")</script>', html)
        self.assertIn('&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;', html)
        self.assertIn("A &amp; B &lt; C", html)
        self.assertIn('data-event-id="event:&quot;x&quot;"', html)

    def test_render_mode_is_not_exposed_as_internal_status_copy(self) -> None:
        source = "원문 그대로 유지되는 문장이다."
        html = render_briefing_html(
            build_briefing_view_model(
                briefing(entry(headline=source, summary=source, render_mode=RenderMode.EXTRACTIVE_FALLBACK))
            )
        )
        self.assertIn(source, html)
        self.assertNotIn("원문 보존", html)
        self.assertNotIn("검증된 재구성", html)

    def test_identical_headline_and_summary_are_shown_once_in_story_card(self) -> None:
        source = "한화가 홈 경기에서 승리했다."
        html = render_briefing_html(
            build_briefing_view_model(
                briefing(entry(headline=source, summary=source, render_mode=RenderMode.EXTRACTIVE_FALLBACK))
            )
        )
        story_card = html.split('<article id="story-1"', 1)[1].split("</article>", 1)[0]
        self.assertEqual(story_card.count(source), 1)
        self.assertNotIn('class="story-summary"', story_card)

    def test_html_uses_plain_korean_copy_and_localized_topic_labels(self) -> None:
        rendered = briefing(
            entry("event:ai"),
            entry("event:economy", headline="경제 뉴스", summary="경제 뉴스 본문이다."),
        )
        html = render_briefing_html(
            build_briefing_view_model(
                rendered,
                topic_by_event={"event:ai": "ai_tech", "event:economy": "economy"},
            )
        )
        self.assertIn('<span class="story-topic">AI 테크</span>', html)
        self.assertIn('<span class="story-topic">경제</span>', html)
        for internal_copy in (
            "VERIFIED",
            "검증 뉴스",
            "검증 완료 뉴스",
            "SUPPORTED headline + summary only",
            "검증을 통과한 뉴스만 표시합니다.",
            "검증된 항목만 표시",
        ):
            self.assertNotIn(internal_copy, html)
        self.assertNotIn('<span class="story-topic">ai_tech</span>', html)
        self.assertNotIn('<span class="story-topic">economy</span>', html)

    def test_empty_briefing_renders_empty_state_without_fake_story(self) -> None:
        html = render_briefing_html(build_briefing_view_model(briefing()))
        self.assertIn("오늘 보여드릴 뉴스가 없습니다.", html)
        self.assertIn("<strong>0</strong>건", html)
        self.assertNotIn('<article class="story-row"', html)

    def test_generated_label_preserves_input_clock_instead_of_runner_timezone(self) -> None:
        rendered = RenderedBriefing(
            briefing_id="briefing:offset",
            generated_at=datetime.fromisoformat("2026-08-23T13:19:00+09:00"),
            entries=(),
        )
        view = build_briefing_view_model(rendered)
        self.assertEqual(view.generated_label, "2026. 08. 23 13:19")


if __name__ == "__main__":
    unittest.main()
