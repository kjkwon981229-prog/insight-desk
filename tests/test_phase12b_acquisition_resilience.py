from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from insight_desk.acquisition import (
    AcquisitionPipeline,
    ArticleCandidate,
    ArticleMainTextExtractor,
    ExtractedArticle,
    ExtractionQualityPolicy,
    FetchedPage,
    TrafilaturaExtractor,
)


NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
HAS_ACQUISITION_RUNTIME = importlib.util.find_spec("lxml") is not None


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


def single_row_layout_article_html() -> tuple[str, str, str]:
    deck = "엔비디아 ‘베라 루빈’ 출격 임박…인도 데이터센터 GPU 도입·확장"
    lead = (
        "엔비디아의 차세대 그래픽처리장치(GPU) ‘베라 루빈(Vera Rubin)’이 올가을 "
        "출하를 앞두면서 글로벌 데이터센터 투자와 맞물려 새로운 성장 동력으로 떠오르고 있다."
    )
    detail = (
        "9월 12일 엔비디아는 베라 루빈의 출하를 올가을 시작할 예정이다. "
        "인도 데이터센터 업체 요타 서비스는 GPU 40000개를 조달할 계획이다."
    )
    html = (
        "<html><head><title>엔비디아 베라 루빈 올가을 출하</title></head><body>"
        '<table class="publisher-layout"><tbody><tr>'
        "<td><a>뉴스 홈</a></td><td><div id=\"textinput\">"
        f"<p><strong>{deck}</strong></p><p>&nbsp;</p>"
        '<table class="body-image"><tr><td><img src="image.jpg"></td></tr></table>'
        f"<p>{lead}</p><p>&nbsp;</p><p>{detail}</p>"
        f"<p>{detail}</p><p>{detail}</p>"
        "</div></td><td><a>많이 본 기사</a></td>"
        "</tr></tbody></table></body></html>"
    )
    return html, deck, lead


class Phase12BAcquisitionResilienceTests(unittest.TestCase):
    def test_article_main_extractor_keeps_article_text_and_excludes_navigation(self) -> None:
        result = ArticleMainTextExtractor().extract(article_html(), url=candidate().url)
        self.assertIn("9월 3일부터", result.body)
        self.assertNotIn("로그인 메뉴", result.body)
        self.assertNotIn("관련기사 광고", result.body)
        self.assertEqual(result.page_title, "테스트 기사")

    @unittest.skipUnless(
        HAS_ACQUISITION_RUNTIME,
        "source-block normalization requires the production acquisition runtime",
    )
    def test_multiline_article_deck_cannot_fuse_with_direct_lead_text(self) -> None:
        html = (
            "<html><head><title>구조 경계</title></head><body><article>"
            "<strong>첫 번째 요약<br>두 번째 요약</strong>"
            "연구진은 새 측정 장치를 공개했다.<br><br>"
            + "후속 설명 문단이다. " * 30
            + "</article></body></html>"
        )
        expected_boundary = "두 번째 요약\n연구진은 새 측정 장치를 공개했다."

        fallback = ArticleMainTextExtractor().extract(html, url=candidate().url)
        self.assertIn(expected_boundary, fallback.body)
        self.assertNotIn("두 번째 요약연구진", fallback.body)

        try:
            primary = TrafilaturaExtractor().extract(html, url=candidate().url)
        except Exception as exc:
            if "trafilatura dependency unavailable" in str(exc):
                self.skipTest("acquisition optional dependency not installed")
            raise
        self.assertIn(expected_boundary, primary.body)
        self.assertNotIn("두 번째 요약연구진", primary.body)

    @unittest.skipUnless(
        HAS_ACQUISITION_RUNTIME,
        "layout-table normalization requires the production acquisition runtime",
    )
    def test_single_row_layout_table_preserves_deck_and_lead_as_source_blocks(self) -> None:
        html, deck, lead = single_row_layout_article_html()
        try:
            extracted = TrafilaturaExtractor().extract(html, url=candidate().url)
        except Exception as exc:
            if "trafilatura dependency unavailable" in str(exc):
                self.skipTest("acquisition optional dependency not installed")
            raise

        lines = tuple(line.strip() for line in extracted.body.splitlines() if line.strip())
        self.assertIn(deck, lines)
        self.assertIn(lead, lines)
        self.assertNotIn(deck + "   " + lead, extracted.body)
        self.assertFalse(extracted.body.lstrip().startswith("|"))

    def test_multi_row_data_table_keeps_table_extraction_enabled(self) -> None:
        calls: list[dict[str, object]] = []

        def extract(html: str, **kwargs: object) -> str:
            del html
            calls.append(kwargs)
            return "분기별 실적 표를 공개했다. " * 20

        html = (
            "<html><body><article><p>회사는 분기별 실적을 공개했다.</p>"
            "<table><tr><th>분기</th><th>매출</th></tr>"
            "<tr><td>1분기</td><td>100</td></tr>"
            "<tr><td>2분기</td><td>120</td></tr></table>"
            "<p>회사는 수치를 감사받았다고 밝혔다.</p></article></body></html>"
        )
        with patch.dict(sys.modules, {"trafilatura": SimpleNamespace(extract=extract)}):
            TrafilaturaExtractor().extract(html, url=candidate().url)

        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0]["include_tables"], True)

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
