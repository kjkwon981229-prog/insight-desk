from __future__ import annotations

import json
import unittest
from dataclasses import replace

from insight_desk.collectors.enrichment import MetadataEnricher, parse_html_metadata
from insight_desk.collectors.transport import HttpResponse
from insight_desk.domain.models import EvidenceType, NewsItem, Topic
from insight_desk.pipeline.selection import topic_diverse_enrichment_candidates
from insight_desk.pipeline.clustering import StoryCluster


class MetadataTransport:
    def __init__(self, responses: dict[str, HttpResponse | Exception]) -> None:
        self.responses = responses

    def request(self, method, url, headers, body=None, timeout=20.0):
        response = self.responses[url]
        if isinstance(response, Exception):
            raise response
        return response


def _item(url: str = "https://publisher.test/story") -> NewsItem:
    return NewsItem(
        "N001",
        "topic",
        "query",
        "검색 결과 제목",
        "검색 결과 요약",
        url,
        "https://n.news.naver.com/story",
        url,
        None,
        "publisher.test",
        "digest",
        10.0,
    )


class EnrichmentTests(unittest.TestCase):
    def test_selection_aware_targets_preliminary_winner_before_round_robin_fill(self) -> None:
        topics = (
            Topic("a", "A", True, False, 50, ("A",), intent_anchors=("A",), event_terms=("출시",)),
            Topic("b", "B", True, False, 50, ("B",), intent_anchors=("B",), event_terms=("출시",)),
        )
        a = replace(_item("https://publisher.test/a"), evidence_id="a", topic_id="a", query="A", title="A 모델 출시 발표")
        b = replace(_item("https://publisher.test/b"), evidence_id="b", topic_id="b", query="B", title="B 모델 출시 발표")
        targets = topic_diverse_enrichment_candidates(
            (a, b),
            topics,
            limit=1,
            priority_clusters=(StoryCluster("b", (b,)),),
        )
        self.assertEqual(tuple(item.evidence_id for item in targets), ("b",))

    def test_metadata_parser_extracts_public_fields_and_canonical(self) -> None:
        body = """
        <html><head>
          <title>문서 제목</title>
          <meta property="og:title" content="공개 제목">
          <meta property="og:description" content="공개 설명">
          <meta property="og:site_name" content="공식 매체">
          <meta property="article:published_time" content="2026-08-09T08:00:00Z">
          <link rel="canonical" href="https://publisher.test/story?utm_source=feed">
        </head><body>본문은 저장하지 않는다.</body></html>
        """.encode("utf-8")
        result = parse_html_metadata(body, url="https://publisher.test/story")
        self.assertTrue(result.success)
        self.assertEqual(result.title, "공개 제목")
        self.assertEqual(result.description, "공개 설명")
        self.assertEqual(result.publisher, "공식 매체")
        self.assertEqual(result.canonical_url, "https://publisher.test/story")
        self.assertIn("+09:00", result.published_at or "")

    def test_document_title_is_a_safe_fallback_when_og_is_missing(self) -> None:
        result = parse_html_metadata(
            "<html><head><title>문서 제목</title></head><body>".encode("utf-8"),
            url="https://publisher.test/story",
        )
        self.assertTrue(result.success)
        self.assertEqual(result.title, "문서 제목")

    def test_success_adds_provenance_without_replacing_search_evidence(self) -> None:
        url = "https://publisher.test/story"
        transport = MetadataTransport(
            {
                url: HttpResponse(
                    200,
                    '<meta property="og:title" content="보강 제목"><meta property="og:site_name" content="매체">'.encode("utf-8"),
                    {"Content-Type": "text/html; charset=utf-8"},
                )
            }
        )
        enriched, report = MetadataEnricher(transport=transport).enrich((_item(url),), limit=5)
        self.assertEqual((report.attempted, report.succeeded, report.failed), (1, 1, 0))
        self.assertEqual(enriched[0].title, "검색 결과 제목")
        self.assertEqual(enriched[0].metadata_title, "보강 제목")
        self.assertEqual(enriched[0].publisher, "매체")
        self.assertEqual(enriched[0].provenance, (EvidenceType.SEARCH_SNIPPET, EvidenceType.ENRICHED_METADATA))

    def test_403_timeout_and_empty_html_fall_back_without_failure(self) -> None:
        urls = {
            "https://publisher.test/403": HttpResponse(403, b"blocked", {}),
            "https://publisher.test/timeout": TimeoutError("slow"),
            "https://publisher.test/empty": HttpResponse(200, b"<html><body>no metadata</body></html>", {}),
        }
        items = tuple(_item(url) for url in urls)
        enriched, report = MetadataEnricher(transport=MetadataTransport(urls)).enrich(items, limit=5)
        self.assertEqual((report.attempted, report.succeeded, report.failed), (3, 0, 3))
        self.assertEqual([item.title for item in enriched], [item.title for item in items])
        self.assertTrue(all(item.provenance == (EvidenceType.SEARCH_SNIPPET,) for item in enriched))
        self.assertNotIn("본문은", json.dumps([item.__dict__ for item in enriched], ensure_ascii=False))

    def test_top_n_is_bounded_and_duplicate_urls_are_fetched_once(self) -> None:
        url = "https://publisher.test/story"
        class CountingTransport(MetadataTransport):
            def __init__(self) -> None:
                super().__init__({url: HttpResponse(200, "<title>보강</title>".encode("utf-8"), {})})
                self.calls = 0

            def request(self, method, requested_url, headers, body=None, timeout=20.0):
                self.calls += 1
                return super().request(method, requested_url, headers, body, timeout)

        transport = CountingTransport()
        items = tuple(_item(url) for _ in range(3))
        _, report = MetadataEnricher(transport=transport).enrich(items, limit=1)
        self.assertEqual(transport.calls, 1)
        self.assertEqual(report.attempted, 1)


if __name__ == "__main__":
    unittest.main()
