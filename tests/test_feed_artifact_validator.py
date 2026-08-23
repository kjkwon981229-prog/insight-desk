from __future__ import annotations

import unittest

from scripts.validate_feed_artifact import validate_html


def html_for(*stories: tuple[str, str, str, str]) -> str:
    rows = []
    for index, (event_id, topic, headline, summary) in enumerate(stories, start=1):
        rows.append(
            f'<article id="story-{index}" class="story-row" data-event-id="{event_id}">'
            '<div class="story-main">'
            f'<div class="story-meta"><span class="story-topic">{topic}</span></div>'
            f'<h3>{headline}</h3>'
            f'<p class="story-summary">{summary}</p>'
            '</div></article>'
        )
    return '<!doctype html><html><body>' + ''.join(rows) + '</body></html>'


class FeedArtifactValidatorTests(unittest.TestCase):
    def test_normal_feed_passes_with_metrics(self) -> None:
        report = validate_html(
            html_for(
                ("event:a", "AI·테크", "AI 투자 확대", "A사가 AI 투자를 확대한다고 밝혔다."),
                ("event:b", "경제·투자", "코스피 상승 마감", "코스피가 상승 마감했다."),
            )
        )
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["story_count"], 2)
        self.assertEqual(report["duplicate_content"], 0)
        self.assertEqual(report["duplicate_headlines"], 0)
        self.assertEqual(report["duplicate_summaries"], 0)

    def test_duplicate_visible_content_fails_even_when_event_ids_differ(self) -> None:
        page = html_for(
            ("event:a", "AI·테크", "같은 제목", "같은 요약"),
            ("event:b", "AI·테크", " 같은   제목 ", "같은  요약"),
        )
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_DUPLICATE_HEADLINE|FEED_QUALITY_DUPLICATE_CONTENT"):
            validate_html(page)

    def test_duplicate_normalized_headline_fails_when_summaries_differ(self) -> None:
        page = html_for(
            (
                "event:rate-a",
                "경제·투자",
                "27일 한국은행 기준금리 결정 주목",
                "오는 27일 예정된 한국은행의 기준금리 결정에 관심이 쏠리고 있습니다.",
            ),
            (
                "event:rate-b",
                "경제·투자",
                " 27일   한국은행 기준금리 결정 주목 ",
                "오는 27일 예정된 한국은행의 기준금리 결정에 관심이 쏠립니다.",
            ),
        )
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_DUPLICATE_HEADLINE"):
            validate_html(page)

    def test_duplicate_normalized_summary_fails_when_headlines_differ(self) -> None:
        page = html_for(
            (
                "event:rate-summary-a",
                "경제·투자",
                "27일 한국은행 기준금리 결정에 이목 집중",
                "오는 27일 예정된 한국은행의 기준금리 결정에 관심이 쏠립니다.",
            ),
            (
                "event:rate-summary-b",
                "경제·투자",
                "27일 한국은행 기준금리 결정에 관심",
                " 오는 27일  예정된 한국은행의 기준금리 결정에 관심이 쏠립니다. ",
            ),
        )
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_DUPLICATE_SUMMARY"):
            validate_html(page)

    def test_oversized_headline_and_summary_fail(self) -> None:
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_HEADLINE_TOO_LONG"):
            validate_html(html_for(("event:a", "AI·테크", "가" * 121, "정상 요약")))
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_SUMMARY_TOO_LONG"):
            validate_html(html_for(("event:a", "AI·테크", "정상 제목", "나" * 421)))

    def test_psat_academy_live_false_positive_fails(self) -> None:
        page = html_for(
            (
                "event:psat",
                "PSAT·공채 일정",
                "농구 유망주 미국 진출",
                "PSAT(Preparatory Student Academic) 아카데미에서 NCAA 진학을 준비한다.",
            )
        )
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_PSAT_FALSE_POSITIVE"):
            validate_html(page)

    def test_empty_feed_fails_product_gate(self) -> None:
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_NO_STORIES"):
            validate_html("<!doctype html><html><body></body></html>")


if __name__ == "__main__":
    unittest.main()
