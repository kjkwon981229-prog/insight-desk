from __future__ import annotations

import unittest
from datetime import datetime, timezone

from insight_desk.acquisition import (
    AcquisitionError,
    AcquisitionPipeline,
    ArticleCandidate,
    ExtractedArticle,
    ExtractionQualityPolicy,
    FetchedPage,
    normalize_naver_items,
)
from insight_desk.core import FailureKind


NOW = datetime(2026, 8, 23, 1, 0, tzinfo=timezone.utc)


class FakeFetcher:
    method_id = "http"

    def __init__(self, html: str) -> None:
        self.html = html
        self.calls = 0

    def fetch(self, url: str) -> FetchedPage:
        self.calls += 1
        return FetchedPage(url=url, html=self.html, fetched_at=NOW, content_type="text/html")


class FakeExtractor:
    method_id = "trafilatura"

    def __init__(self, mapping: dict[str, ExtractedArticle]) -> None:
        self.mapping = mapping
        self.calls: list[str] = []

    def extract(self, html: str, *, url: str) -> ExtractedArticle:
        self.calls.append(html)
        return self.mapping[html]


class FakeRenderer:
    method_id = "playwright"

    def __init__(self, rendered_html: str) -> None:
        self.rendered_html = rendered_html
        self.calls = 0

    def render(self, url: str) -> FetchedPage:
        self.calls += 1
        return FetchedPage(url=url, html=self.rendered_html, fetched_at=NOW, content_type="text/html")


def candidate() -> ArticleCandidate:
    return ArticleCandidate(
        candidate_id="article-1",
        url="https://news.example.com/a1",
        search_title="검색 결과 제목",
        source_name="news.example.com",
        published_at=NOW,
        topic_ids=("ai_tech",),
        query="AI 규제",
    )


class NaverNormalizationTests(unittest.TestCase):
    def test_originallink_is_preferred_and_duplicates_are_removed(self) -> None:
        payload = {
            "items": [
                {
                    "title": "<b>SK하이닉스</b> 9월 발표",
                    "originallink": "https://press.example.com/story/1",
                    "link": "https://n.news.naver.com/story/1",
                    "description": "검색 스니펫은 본문이 아니다.",
                    "pubDate": "Sun, 23 Aug 2026 01:00:00 +0900",
                },
                {
                    "title": "중복",
                    "originallink": "https://press.example.com/story/1",
                    "link": "https://n.news.naver.com/story/1b",
                    "pubDate": "Sun, 23 Aug 2026 01:00:00 +0900",
                },
            ]
        }
        result = normalize_naver_items(payload, topic_id="ai_tech", query="반도체")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].url, "https://press.example.com/story/1")
        self.assertEqual(result[0].search_title, "SK하이닉스 9월 발표")
        self.assertEqual(result[0].source_name, "press.example.com")
        self.assertEqual(result[0].published_at.isoformat(), "2026-08-23T01:00:00+09:00")

    def test_search_description_is_never_promoted_to_article_body(self) -> None:
        payload = {
            "items": [
                {
                    "title": "기사 제목",
                    "originallink": "https://press.example.com/story/2",
                    "description": "이 문장은 검색 스니펫이다.",
                }
            ]
        }
        item = normalize_naver_items(payload, topic_id="economy", query="금리")[0]
        self.assertFalse(hasattr(item, "body"))
        self.assertNotIn("스니펫", item.search_title)


class AcquisitionPipelineTests(unittest.TestCase):
    def test_primary_extraction_preserves_protected_literals_exactly(self) -> None:
        body = (
            "SK하이닉스는 9월 3일 신규 계획을 발표했다. "
            "회사 측은 “영업이익률은 13.6%”라고 밝혔다. "
            "317억 달러와 1,050만 명이라는 수치도 원문에 그대로 있다. "
            "이 문장은 품질 기준을 넘기기 위한 사실 중립적 반복 설명이며 실제 테스트에서는 "
            "추출기가 반환한 텍스트를 파이프라인이 재작성하지 않는지만 확인한다. "
            "숫자와 날짜, 고유명사와 직접 인용은 후속 EvidenceSpan의 원재료이므로 그대로 남아야 한다."
        )
        fetcher = FakeFetcher("<html>raw source</html>")
        extractor = FakeExtractor(
            {"<html>raw source</html>": ExtractedArticle(body=body, page_title="SK하이닉스 신규 계획 발표")}
        )
        pipeline = AcquisitionPipeline(fetcher=fetcher, primary_extractor=extractor)
        result = pipeline.acquire(candidate())

        self.assertEqual(result.article.body, body)
        for literal in ("SK하이닉스", "9월 3일", "13.6%", "317억 달러", "1,050만 명", "“영업이익률은 13.6%”"):
            self.assertIn(literal, result.article.body)
        self.assertEqual(result.article.title, "SK하이닉스 신규 계획 발표")
        self.assertEqual(result.article.provenance.url, candidate().url)
        self.assertEqual(result.article.provenance.published_at, NOW)
        self.assertEqual(result.extraction_method, "http+trafilatura")
        self.assertFalse(result.fallback_used)

    def test_short_primary_uses_playwright_then_reextracts(self) -> None:
        long_body = "실제 기사 본문입니다. " * 40
        fetcher = FakeFetcher("raw")
        renderer = FakeRenderer("rendered")
        extractor = FakeExtractor(
            {
                "raw": ExtractedArticle(body="로그인 메뉴 홈"),
                "rendered": ExtractedArticle(body=long_body, page_title="렌더링된 원문 제목"),
            }
        )
        pipeline = AcquisitionPipeline(
            fetcher=fetcher,
            primary_extractor=extractor,
            fallback_renderer=renderer,
            quality_policy=ExtractionQualityPolicy(min_non_whitespace_chars=100),
        )
        result = pipeline.acquire(candidate())
        self.assertTrue(result.fallback_used)
        self.assertEqual(renderer.calls, 1)
        self.assertEqual(extractor.calls, ["raw", "rendered"])
        self.assertEqual(result.article.body, long_body.strip())
        self.assertEqual(result.article.title, "렌더링된 원문 제목")
        self.assertEqual(result.extraction_method, "playwright+trafilatura")

    def test_bad_fallback_fails_closed(self) -> None:
        fetcher = FakeFetcher("raw")
        renderer = FakeRenderer("rendered")
        extractor = FakeExtractor(
            {
                "raw": ExtractedArticle(body="짧음"),
                "rendered": ExtractedArticle(body="여전히 짧음"),
            }
        )
        pipeline = AcquisitionPipeline(
            fetcher=fetcher,
            primary_extractor=extractor,
            fallback_renderer=renderer,
            quality_policy=ExtractionQualityPolicy(min_non_whitespace_chars=100),
        )
        with self.assertRaises(AcquisitionError) as caught:
            pipeline.acquire(candidate())
        self.assertIs(caught.exception.failure_kind, FailureKind.EXTRACTION_EMPTY)

    def test_repetitive_navigation_like_text_is_rejected(self) -> None:
        policy = ExtractionQualityPolicy(min_non_whitespace_chars=10, max_duplicate_line_ratio=0.30)
        text = "홈\n뉴스\n홈\n뉴스\n홈\n뉴스\n홈\n뉴스"
        result = policy.assess(text)
        self.assertFalse(result.acceptable)
        self.assertIn("repetitive_navigation_like_text", result.reasons)

    def test_page_title_falls_back_to_search_title_without_invention(self) -> None:
        body = "원문 본문 " * 50
        pipeline = AcquisitionPipeline(
            fetcher=FakeFetcher("raw"),
            primary_extractor=FakeExtractor({"raw": ExtractedArticle(body=body)}),
        )
        result = pipeline.acquire(candidate())
        self.assertEqual(result.article.title, "검색 결과 제목")


if __name__ == "__main__":
    unittest.main()
