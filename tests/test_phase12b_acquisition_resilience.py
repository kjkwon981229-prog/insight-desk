from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.acquisition import (
    AcquisitionPipeline,
    ArticleCandidate,
    ArticleMainTextExtractor,
    ExtractedArticle,
    ExtractionQualityPolicy,
    FetchedPage,
)


NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)


class Fetcher:
    method_id = "http"

    def __init__(self, html: str) -> None:
        self.html = html

    def fetch(self, url: str) -> FetchedPage:
        return FetchedPage(url=url, html=self.html, fetched_at=NOW, content_type="text/html")


class PrimaryExtractor:
    method_id = "trafilatura"

    def __init__(self, mapping: dict[str, str]) -> None:
        self.mapping = mapping
        self.calls: list[str] = []

    def extract(self, html: str, *, url: str) -> ExtractedArticle:
        self.calls.append(html)
        return ExtractedArticle(body=self.mapping.get(html, ""), page_title="원문 제목")


class Renderer:
    method_id = "playwright"

    def __init__(self, html: str) -> None:
        self.html = html
        self.calls = 0

    def render(self, url: str) -> FetchedPage:
        self.calls += 1
        return FetchedPage(url=url, html=self.html, fetched_at=NOW, content_type="text/html")


def candidate() -> ArticleCandidate:
    return ArticleCandidate(
        candidate_id="article-phase12b-acquisition",
        url="https://news.example.com/story",
        search_title="검색 제목",
        source_name="news.example.com",
        published_at=NOW,
        topic_ids=("ai_tech",),
        query="AI",
    )


def article_html(repeat: int = 30) -> str:
    body = "정부는 9월 3일부터 새 제도를 시행한다고 밝혔다. " * repeat
    return (
        "<html><head><title>테스트 기사</title></head><body>"
        "<nav>홈 뉴스 로그인 메뉴</nav>"
        f"<article><h1>테스트 기사</h1><p>{body}</p>"
        "<aside>관련기사 광고</aside></article>"
        "<footer>회사소개</footer></body></html>"
    )


class Phase12BAcquisitionResilienceTests(unittest.TestCase):
    def test_article_main_extractor_keeps_article_text_and_excludes_navigation(self) -> None:
        result = ArticleMainTextExtractor().extract(article_html(), url=candidate().url)
        self.assertIn("9월 3일부터", result.body)
        self.assertNotIn("로그인 메뉴", result.body)
        self.assertNotIn("관련기사 광고", result.body)
        self.assertEqual(result.page_title, "테스트 기사")

    def test_static_article_main_fallback_avoids_playwright(self) -> None:
        raw = article_html()
        primary = PrimaryExtractor({raw: "짧음"})
        renderer = Renderer("unused")
        pipeline = AcquisitionPipeline(
            fetcher=Fetcher(raw),
            primary_extractor=primary,
            fallback_renderer=renderer,
            quality_policy=ExtractionQualityPolicy(min_non_whitespace_chars=100),
        )

        result = pipeline.acquire(candidate())

        self.assertEqual(renderer.calls, 0)
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.extraction_method, "http+html-article-main")
        self.assertIn("9월 3일부터", result.article.body)

    def test_rendered_article_main_is_last_fallback_after_primary_rejects(self) -> None:
        raw = "<html><body>로그인</body></html>"
        rendered = article_html()
        primary = PrimaryExtractor({raw: "짧음", rendered: "여전히 짧음"})
        renderer = Renderer(rendered)
        pipeline = AcquisitionPipeline(
            fetcher=Fetcher(raw),
            primary_extractor=primary,
            fallback_renderer=renderer,
            quality_policy=ExtractionQualityPolicy(min_non_whitespace_chars=100),
        )

        result = pipeline.acquire(candidate())

        self.assertEqual(renderer.calls, 1)
        self.assertEqual(primary.calls, [raw, rendered])
        self.assertEqual(result.extraction_method, "playwright+html-article-main")
        self.assertIn("9월 3일부터", result.article.body)


if __name__ == "__main__":
    unittest.main()
