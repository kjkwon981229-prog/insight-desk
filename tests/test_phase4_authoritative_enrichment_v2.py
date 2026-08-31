from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import unittest

from insight_desk.api import EcosClient, HttpResponse
from insight_desk.authoritative_enrichment_v2 import AuthoritativeEnricher
from insight_desk.core import CanonicalEvent, CanonicalPublicationBundle, SourceDocument
from insight_desk.production_orchestrator_v2 import ProductionV2Registry


NOW = datetime(2026, 8, 27, 3, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]


def source(*, body: str = "원문에는 기준금리라는 단어가 있을 수 있다.") -> SourceDocument:
    return SourceDocument(
        source_id="source-document:article-1",
        candidate_ids=("article-1",),
        publisher="example.com",
        url="https://example.com/article-1",
        title="기사",
        body=body,
        fetched_at=NOW,
        publication_time=NOW,
        retrieved_via="fixture",
        content_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
    )


def event(
    *,
    event_id: str = "event-1",
    topic: str = "economy",
    actor: str = "한국은행 금융통화위원회",
    action: str = "기준금리를 결정했다",
    object_: str | None = "기준금리",
    participants: tuple[str, ...] = ("한국은행",),
) -> CanonicalEvent:
    return CanonicalEvent(
        event_id=event_id,
        topic=topic,
        actor=actor,
        action=action,
        object=object_,
        event_type="news_event",
        source_ids=("source-document:article-1",),
        event_time="2026-08-27",
        publication_time=NOW,
        participants=participants,
    )


BASE_CONFIG = {
    "ecos": {
        "enabled": True,
        "max_requests": 1,
        "datasets": [
            {
                "id": "bank_of_korea_base_rate",
                "label": "한국은행 기준금리",
                "stat_code": "722Y001",
                "item_code": "0101000",
                "cycle": "M",
                "keywords": ["기준금리", "한국은행 기준금리"],
                "expected_unit": "연%",
                "max_periods": 2,
            }
        ],
    },
    "kosis": {
        "enabled": True,
        "max_requests": 2,
        "datasets": [
            {
                "id": "consumer_price_index",
                "label": "소비자물가지수",
                "org_id": "101",
                "tbl_id": "DT_1J22001",
                "obj_l1": "T10",
                "obj_l2": "0",
                "itm_id": "T",
                "prd_se": "M",
                "keywords": ["물가", "소비자물가지수", "CPI"],
                "expected_unit": "2020=100",
                "max_periods": 2,
            }
        ],
    },
    "open_dart": {
        "enabled": True,
        "lookback_days": 7,
        "page_count": 50,
        "disclosure_type": "B",
        "max_requests": 2,
        "entities": [
            {
                "id": "samsung_electronics",
                "aliases": ["삼성전자", "Samsung Electronics"],
                "topic_ids": ["economy", "ai_tech"],
                "corp_code": "00126380",
            }
        ],
    },
}


class FakeEcos:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self.error = error

    def statistic_search(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return {
            "StatisticSearch": {
                "row": [
                    {
                        "STAT_CODE": "722Y001",
                        "STAT_NAME": "한국은행 기준금리",
                        "ITEM_CODE1": "0101000",
                        "TIME": "202607",
                        "DATA_VALUE": "2.50",
                        "UNIT_NAME": "%",
                    },
                    {
                        "STAT_CODE": "722Y001",
                        "STAT_NAME": "한국은행 기준금리",
                        "ITEM_CODE1": "0101000",
                        "TIME": "202608",
                        "DATA_VALUE": "2.75",
                        "UNIT_NAME": "%",
                    },
                    {
                        "STAT_CODE": "722Y001",
                        "STAT_NAME": "다른 항목",
                        "ITEM_CODE1": "9999999",
                        "TIME": "202608",
                        "DATA_VALUE": "999",
                        "UNIT_NAME": "%",
                    },
                ]
            }
        }


class FakeKosis:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def statistics(self, **kwargs):
        self.calls.append(kwargs)
        return [
            {"PRD_DE": "202607", "ITM_NM": "소비자물가지수", "C1_NM": "전국", "DT": "116.8"},
            {"PRD_DE": "202608", "ITM_NM": "소비자물가지수", "C1_NM": "전국", "DT": "117.1"},
        ]


class FakeDart:
    def __init__(self, report_name: str = "주요사항보고서(유상증자결정)") -> None:
        self.calls: list[dict[str, object]] = []
        self.report_name = report_name

    def list_filings(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "status": "000",
            "list": [
                {
                    "corp_code": "00126380",
                    "corp_name": "삼성전자",
                    "report_nm": self.report_name,
                    "rcept_no": "20260827000123",
                    "rcept_dt": "20260827",
                }
            ],
        }


class RecordingTransport:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def request(self, method, url, headers, body=None, timeout=20.0):
        self.urls.append(url)
        return HttpResponse(
            status=200,
            body=b'{"StatisticSearch":{"row":[]}}',
            headers={},
        )


class AuthoritativeEnrichmentTests(unittest.TestCase):
    def test_ecos_matches_canonical_event_and_binds_latest_configured_item(self) -> None:
        ecos = FakeEcos()
        enricher = AuthoritativeEnricher(BASE_CONFIG, ecos_client=ecos)
        facts = enricher.enrich(event(), source())

        self.assertEqual(len(ecos.calls), 1)
        self.assertEqual(ecos.calls[0]["stat_code"], "722Y001")
        self.assertEqual(ecos.calls[0]["item_code"], "0101000")
        self.assertEqual(ecos.calls[0]["start_period"], "202607")
        self.assertEqual(ecos.calls[0]["end_period"], "202608")
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0].provider_id, "ecos")
        self.assertEqual(facts[0].value, "2.75")
        self.assertEqual(facts[0].effective_time, "202608")
        self.assertEqual(facts[0].source_url, "https://ecos.bok.or.kr/")

        registry = ProductionV2Registry()
        registry.sources_by_article["article-1"] = source()
        registry.events_by_id["event-1"] = event()
        registry.bind_authoritative_facts("event-1", facts)
        bound = registry.canonical_event("event-1")
        self.assertEqual(bound.authoritative_fact_ids, (facts[0].fact_id,))
        CanonicalPublicationBundle(
            sources=(source(),),
            authoritative_facts=facts,
            events=(bound,),
        ).validate()

    def test_provider_failure_is_fail_soft_and_does_not_delete_or_rewrite_event(self) -> None:
        original = event()
        ecos = FakeEcos(error=RuntimeError("provider unavailable"))
        enricher = AuthoritativeEnricher(BASE_CONFIG, ecos_client=ecos)
        facts = enricher.enrich(original, source())
        self.assertEqual(facts, ())
        self.assertEqual(original.authoritative_fact_ids, ())
        stats = enricher.audit_stats["ecos"]
        self.assertEqual(stats["calls"], 1)
        self.assertEqual(stats["errors"], 1)
        self.assertEqual(stats["facts"], 0)

    def test_article_body_keyword_alone_cannot_trigger_authoritative_route(self) -> None:
        ecos = FakeEcos()
        unrelated = event(
            actor="국회",
            action="법안을 논의했다",
            object_="정책",
            participants=("국회",),
        )
        enricher = AuthoritativeEnricher(BASE_CONFIG, ecos_client=ecos)
        self.assertEqual(enricher.enrich(unrelated, source(body="기준금리 기준금리 기준금리")), ())
        self.assertEqual(ecos.calls, [])

    def test_kosis_attaches_latest_official_statistic_only(self) -> None:
        kosis = FakeKosis()
        cpi_event = event(
            actor="통계청",
            action="소비자물가지수를 발표했다",
            object_="소비자물가지수",
            participants=("통계청",),
        )
        enricher = AuthoritativeEnricher(BASE_CONFIG, kosis_client=kosis)
        facts = enricher.enrich(cpi_event, source())
        self.assertEqual(len(kosis.calls), 1)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0].provider_id, "kosis")
        self.assertEqual(facts[0].value, "117.1")
        self.assertEqual(facts[0].effective_time, "202608")
        self.assertIn("orgId=101", facts[0].source_url)
        self.assertNotIn("apiKey", facts[0].source_url)

    def test_opendart_requires_company_and_filing_type_match(self) -> None:
        dart = FakeDart()
        disclosure_event = event(
            actor="삼성전자",
            action="유상증자를 결정하고 공시했다",
            object_="유상증자",
            participants=("삼성전자",),
        )
        enricher = AuthoritativeEnricher(BASE_CONFIG, opendart_client=dart)
        facts = enricher.enrich(disclosure_event, source())
        self.assertEqual(len(dart.calls), 1)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0].provider_id, "opendart")
        self.assertEqual(facts[0].predicate, "공시")
        self.assertEqual(facts[0].value, "주요사항보고서(유상증자결정)")
        self.assertIn("rcpNo=20260827000123", facts[0].source_url)

        unrelated_dart = FakeDart("주요사항보고서(자기주식취득결정)")
        unrelated_enricher = AuthoritativeEnricher(BASE_CONFIG, opendart_client=unrelated_dart)
        self.assertEqual(unrelated_enricher.enrich(disclosure_event, source()), ())

    def test_same_ecos_dataset_is_cached_across_matching_events(self) -> None:
        ecos = FakeEcos()
        enricher = AuthoritativeEnricher(BASE_CONFIG, ecos_client=ecos)
        first = enricher.enrich(event(event_id="event-1"), source())
        second = enricher.enrich(event(event_id="event-2"), source())
        self.assertEqual(first, second)
        self.assertEqual(len(ecos.calls), 1)
        self.assertEqual(enricher.audit_stats["ecos"]["cache_hits"], 1)

    def test_no_configured_clients_means_optional_enrichment_not_event_failure(self) -> None:
        enricher = AuthoritativeEnricher(BASE_CONFIG)
        self.assertEqual(enricher.enrich(event(), source()), ())
        self.assertFalse(enricher.audit_stats["ecos"]["configured"])
        self.assertFalse(enricher.audit_stats["kosis"]["configured"])
        self.assertFalse(enricher.audit_stats["opendart"]["configured"])

    def test_ecos_client_places_item_code_in_request_path(self) -> None:
        transport = RecordingTransport()
        client = EcosClient("secret", transport=transport)
        client.statistic_search(
            stat_code="722Y001",
            cycle="M",
            start_period="202607",
            end_period="202608",
            item_code="0101000",
        )
        self.assertEqual(len(transport.urls), 1)
        self.assertTrue(transport.urls[0].endswith("/722Y001/M/202607/202608/0101000/"))

    def test_workflow_exposes_optional_authoritative_credentials_and_config_path_trigger(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "insight-desk-production.yml").read_text(
            encoding="utf-8"
        )
        for name in ("ECOS_API_KEY", "KOSIS_API_KEY", "OPENDART_API_KEY"):
            self.assertIn(f"{name}: ${{{{ secrets.{name} }}}}", workflow)
        self.assertIn('"config/authoritative_sources.json"', workflow)
        self.assertIn('"ecos": configured("ECOS_API_KEY")', workflow)
        self.assertIn('"kosis": configured("KOSIS_API_KEY")', workflow)
        self.assertIn('"opendart": configured("OPENDART_API_KEY")', workflow)

    def test_authoritative_owner_does_not_import_naver_or_relevance_policy(self) -> None:
        source_text = (ROOT / "insight_desk" / "authoritative_enrichment_v2.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("Naver", source_text)
        self.assertNotIn("story_admission", source_text)
        self.assertNotIn("feed_quality", source_text)


if __name__ == "__main__":
    unittest.main()
