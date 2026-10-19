from __future__ import annotations

import unittest
from pathlib import Path

from insight_desk.core import RenderMode
from insight_desk.ui import (
    BriefingViewModel,
    StoryViewModel,
    _source_host,
    _topic_tone,
    render_briefing_html,
)

ROOT = Path(__file__).resolve().parents[1]


def _view() -> BriefingViewModel:
    story = StoryViewModel(
        index=1,
        event_id="e1",
        headline="제목",
        summary="요약",
        render_mode=RenderMode.GENERATED,
        topic="economy",
        source_url="https://www.example.co.kr/a?b=1",
    )
    return BriefingViewModel(briefing_id="daily-20261019T070000+0900", generated_label="2026. 10. 19 07:00", stories=(story,))


class ToneAndHostTests(unittest.TestCase):
    def test_source_host_drops_www_and_path(self) -> None:
        self.assertEqual(_source_host("https://www.example.co.kr/a?b=1"), "example.co.kr")
        self.assertEqual(_source_host(None), "")

    def test_each_displayed_topic_has_its_own_tone_and_unknown_falls_back(self) -> None:
        self.assertNotEqual(_topic_tone("경제"), _topic_tone("AI 테크"))
        self.assertEqual(_topic_tone("처음 보는 분야"), 0)

    def test_card_shows_topic_tone_and_source_host(self) -> None:
        html = render_briefing_html(_view())
        self.assertIn('data-tone="1"', html)
        self.assertIn('<span class="story-host">example.co.kr</span>', html)


class FeedbackStaysOnDeviceTests(unittest.TestCase):
    def test_feedback_script_sends_nothing_over_the_network(self) -> None:
        script = (ROOT / "assets" / "js" / "feedback.js").read_text(encoding="utf-8")
        for call in ("fetch(", "XMLHttpRequest", "sendBeacon", "workerUrl"):
            self.assertNotIn(call, script)

    def test_page_says_records_stay_on_this_device(self) -> None:
        self.assertIn("이 기기에만 저장됩니다", render_briefing_html(_view()))


class SelfHostedFontTests(unittest.TestCase):
    def test_page_makes_no_external_font_request(self) -> None:
        html = render_briefing_html(_view())
        self.assertNotIn("fonts.googleapis.com", html)
        self.assertNotIn("fonts.gstatic.com", html)

    def test_every_font_face_points_at_a_shipped_file(self) -> None:
        css = (ROOT / "assets" / "css" / "style.css").read_text(encoding="utf-8")
        for name in ("nanum-myeongjo-800", "gowun-batang-400", "gowun-batang-700", "gowun-dodum-400"):
            self.assertIn(f"../fonts/{name}.woff2", css)
            self.assertGreater((ROOT / "assets" / "fonts" / f"{name}.woff2").stat().st_size, 50_000)


if __name__ == "__main__":
    unittest.main()
