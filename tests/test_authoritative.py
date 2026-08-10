from __future__ import annotations

import json
import unittest
from datetime import date, datetime
from urllib.parse import parse_qs, urlparse

from insight_desk.authoritative.adapters import KosisAdapter, OpenDartAdapter, _report_is_relevant
from insight_desk.authoritative.config import (
    AuthorityConfig,
    KosisConfig,
    KosisDataset,
    OpenDartConfig,
    OpenDartEntity,
    PublicSourceConfig,
)
from insight_desk.authoritative.public import PublicOfficialAdapter
from insight_desk.authoritative.router import AuthoritativeRouter
from insight_desk.collectors.transport import HttpResponse
from insight_desk.domain.models import AuthoritySourceType, NewsItem


class FakeTransport:
    def __init__(self, responses: tuple[HttpResponse | Exception, ...]) -> None:
        self.responses = list(responses)
        self.urls: list[str] = []

    def request(self, method: str, url: str, headers: dict[str, str], *, timeout: float = 20.0, **kwargs: object) -> HttpResponse:
        self.urls.append(url)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _response(payload: object, *, status: int = 200) -> HttpResponse:
    return HttpResponse(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), {})


def _item(
    evidence_id: str,
    title: str,
    summary: str,
    *,
    query: str,
    topic_id: str = "economy",
) -> NewsItem:
    return NewsItem(
        evidence_id=evidence_id,
        topic_id=topic_id,
        query=query,
        title=title,
        summary=summary,
        original_url=f"https://news.example/{evidence_id}",
        naver_url="",
        canonical_url=f"https://news.example/{evidence_id}",
        published_at="2026-08-10T07:00:00+09:00",
        source_domain="news.example",
        content_hash=evidence_id,
    )


def _dart_config() -> OpenDartConfig:
    return OpenDartConfig(
        enabled=True,
        lookback_days=7,
        page_count=50,
        disclosure_type="B",
        max_requests=1,
        entities=(OpenDartEntity("hybe", ("HYBE", "하이브"), ("kpop",), "01204056"),),
    )


def _kosis_dataset() -> KosisDataset:
    return KosisDataset(
        id="consumer_price_index",
        label="소비자물가지수",
        org_id="101",
        tbl_id="DT_TEST",
        obj_l1="00",
        itm_id="1000",
        prd_se="M",
        keywords=("물가", "소비자물가"),
        expected_unit="2020=100",
        publisher="통계청 KOSIS",
        obj_l2="0",
    )


class AuthoritativeAdapterTests(unittest.TestCase):
    def test_public_official_page_requires_same_entity_event_and_fact(self) -> None:
        source = PublicSourceConfig(
            id="kbo-public",
            url="https://official.example/schedule",
            topic_ids=("kbo",),
            source_type="OFFICIAL_SPORTS",
            publisher="KBO",
            trusted_domains=("official.example",),
            entity_aliases=("한화 이글스", "KBO"),
            event_markers=("경기", "결과"),
        )
        page = """
        <html><head><title>KBO 공식 일정</title></head><body>
          <a href="/game/20260810">한화 이글스 8월 10일 경기 결과 5-3 승리</a>
        </body></html>
        """.encode("utf-8")
        item = _item(
            "public-match",
            "한화 이글스 8월 10일 경기 결과 5-3 승리",
            "한화 이글스가 8월 10일 경기에서 5-3으로 승리했다.",
            query="KBO",
            topic_id="kbo",
        )
        payload = PublicOfficialAdapter(
            config=source,
            transport=FakeTransport((HttpResponse(200, page, {"Content-Type": "text/html"}),)),
        ).fetch((item,))
        self.assertTrue(payload.result.success)
        self.assertEqual(payload.result.events_augmented, 1)
        evidence = payload.evidence[0][1]
        self.assertEqual(evidence.source_type, AuthoritySourceType.OFFICIAL_SPORTS)
        self.assertEqual(evidence.canonical_url, "https://official.example/game/20260810")

        unrelated = _item(
            "public-unrelated",
            "한화 기업 투자 발표",
            "한화의 투자 계획이 발표됐다.",
            query="한화",
            topic_id="kbo",
        )
        self.assertEqual(
            PublicOfficialAdapter(
                config=source,
                transport=FakeTransport((HttpResponse(200, page, {"Content-Type": "text/html"}),)),
            ).fetch((unrelated,)).evidence,
            (),
        )

    def test_public_page_does_not_attach_generic_navigation_to_event(self) -> None:
        source = PublicSourceConfig(
            id="psat-public",
            url="https://official.example/recruitment",
            topic_ids=("psat",),
            source_type="OFFICIAL_GOVERNMENT",
            publisher="공식 채용시스템",
            trusted_domains=("official.example",),
            entity_aliases=("해양경찰청", "시험"),
            event_markers=("채용", "공고", "시험"),
        )
        page = """
        <html><body>
          <a href="/faq">채용시험종합안내(FAQ)</a>
          <div>2026년 3차 해양경찰공무원 채용시험 공고(해양경찰청)</div>
        </body></html>
        """.encode("utf-8")
        item = _item(
            "psat-public-match",
            "2026년 3차 해양경찰공무원 채용시험 공고(해양경찰청)",
            "해양경찰청 채용시험 공고가 게시됐다.",
            query="PSAT",
            topic_id="psat",
        )
        payload = PublicOfficialAdapter(
            config=source,
            transport=FakeTransport((HttpResponse(200, page, {"Content-Type": "text/html"}),)),
        ).fetch((item,))
        self.assertEqual(payload.result.events_augmented, 1)
        self.assertEqual(payload.evidence[0][1].canonical_url, "https://official.example/recruitment")

    def test_public_ai_source_requires_same_event_and_can_attach_official_primary(self) -> None:
        source = PublicSourceConfig(
            id="openai-news",
            url="https://openai.com/news/",
            topic_ids=("ai",),
            source_type="OFFICIAL_PRIMARY",
            publisher="OpenAI",
            trusted_domains=("openai.com",),
            entity_aliases=("OpenAI", "GPT-5"),
            event_markers=("launch", "model", "발표"),
        )
        page = """
        <html><head><title>OpenAI News</title></head><body>
          <a href="/index/gpt-5">OpenAI launches GPT-5 model</a>
        </body></html>
        """.encode("utf-8")
        item = _item(
            "openai-match",
            "OpenAI launches GPT-5 model",
            "OpenAI launched the GPT-5 model on 2026-08-10.",
            query="ChatGPT",
            topic_id="ai",
        )
        payload = PublicOfficialAdapter(
            config=source,
            transport=FakeTransport((HttpResponse(200, page, {"Content-Type": "text/html"}),)),
        ).fetch((item,))
        self.assertEqual(payload.result.events_augmented, 1)
        evidence = payload.evidence[0][1]
        self.assertEqual(evidence.publisher, "OpenAI")
        self.assertEqual(evidence.canonical_url, "https://openai.com/index/gpt-5")

        unrelated = _item(
            "openai-unrelated",
            "ChatGPT education partnership announced",
            "A separate education partnership was announced.",
            query="ChatGPT",
            topic_id="ai",
        )
        self.assertEqual(
            PublicOfficialAdapter(
                config=source,
                transport=FakeTransport((HttpResponse(200, page, {"Content-Type": "text/html"}),)),
            ).fetch((unrelated,)).evidence,
            (),
        )

    def test_opendart_matches_event_category_and_caps_candidate_attachments(self) -> None:
        item = _item(
            "dart-category",
            "하이브 대규모 투자 계획 발표",
            "하이브의 투자 계획이 발표됐다.",
            query="HYBE",
            topic_id="kpop",
        )
        self.assertTrue(_report_is_relevant("주요사항보고서(타법인주식및출자증권취득결정)", item))
        self.assertFalse(_report_is_relevant("주요사항보고서(계약)", item))
        transport = FakeTransport(
            (
                _response(
                    {
                        "status": "000",
                        "list": [
                            {
                                "corp_name": "하이브",
                                "report_nm": "주요사항보고서(투자)",
                                "rcept_no": f"2026081012345{i}",
                                "rcept_dt": "20260810",
                            }
                            for i in range(1, 5)
                        ],
                    }
                ),
            )
        )
        payload = OpenDartAdapter(
            api_key="placeholder-opendart-key", config=_dart_config(), transport=transport
        ).fetch((item,), today=date(2026, 8, 10))
        self.assertEqual(payload.result.events_augmented, 2)
        self.assertEqual(len(payload.evidence), 2)

    def test_opendart_normalizes_relevant_filing_without_exposing_key(self) -> None:
        secret = "placeholder-opendart-key"
        transport = FakeTransport(
            (
                _response(
                    {
                        "status": "000",
                        "list": [
                            {
                                "corp_name": "하이브",
                                "report_nm": "주요사항보고서(계약)",
                                "rcept_no": "20260810123456",
                                "rcept_dt": "20260810",
                            }
                        ],
                    }
                ),
            )
        )
        item = _item("dart-1", "하이브 글로벌 계약 체결", "하이브가 새 계약을 체결했다.", query="HYBE", topic_id="kpop")
        payload = OpenDartAdapter(api_key=secret, config=_dart_config(), transport=transport).fetch(
            (item,), today=date(2026, 8, 10)
        )
        self.assertTrue(payload.result.success)
        self.assertEqual(payload.result.events_augmented, 1)
        self.assertEqual(payload.evidence[0][0], "dart-1")
        evidence = payload.evidence[0][1]
        self.assertEqual(evidence.source_type, AuthoritySourceType.OFFICIAL_CORPORATE)
        self.assertEqual(evidence.publisher, "금융감독원 OpenDART")
        self.assertIn("rcpNo=20260810123456", evidence.canonical_url)
        self.assertNotIn(secret, json.dumps(payload.result.to_audit(), ensure_ascii=False))
        query = parse_qs(urlparse(transport.urls[0]).query)
        self.assertEqual(query["crtfc_key"], [secret])

    def test_opendart_invalid_key_is_isolated_and_routine_filing_is_not_story_evidence(self) -> None:
        transport = FakeTransport((_response({"status": "010", "message": "invalid key"}),))
        item = _item("dart-2", "하이브 실적 관련 기사", "공시가 언급됐다.", query="HYBE", topic_id="kpop")
        payload = OpenDartAdapter(api_key="placeholder-opendart-key", config=_dart_config(), transport=transport).fetch(
            (item,), today=date(2026, 8, 10)
        )
        self.assertFalse(payload.result.success)
        self.assertEqual(payload.result.failure_reason, "API_STATUS_010")
        self.assertEqual(payload.evidence, ())

        routine_transport = FakeTransport(
            (
                _response(
                    {
                        "status": "000",
                        "list": [
                            {
                                "corp_name": "하이브",
                                "report_nm": "반기보고서",
                                "rcept_no": "20260810123457",
                                "rcept_dt": "20260810",
                            }
                        ],
                    }
                ),
            )
        )
        routine = OpenDartAdapter(
            api_key="placeholder-opendart-key", config=_dart_config(), transport=routine_transport
        ).fetch((item,), today=date(2026, 8, 10))
        self.assertTrue(routine.result.success)
        self.assertEqual(routine.result.events_augmented, 0)
        self.assertEqual(routine.evidence, ())

    def test_opendart_never_falls_back_to_global_first_page_without_corp_code(self) -> None:
        config = OpenDartConfig(
            enabled=True,
            lookback_days=7,
            page_count=50,
            disclosure_type="B",
            max_requests=2,
            entities=(OpenDartEntity("hybe", ("HYBE", "하이브"), ("kpop",)),),
        )
        transport = FakeTransport(())
        item = _item("dart-no-code", "하이브 투자 계약 체결", "하이브가 투자 계약을 체결했다.", query="HYBE", topic_id="kpop")
        payload = OpenDartAdapter(
            api_key="placeholder-opendart-key", config=config, transport=transport
        ).fetch((item,), today=date(2026, 8, 10))
        self.assertFalse(payload.result.success)
        self.assertEqual(payload.result.failure_reason, "CORP_CODE_NOT_CONFIGURED")
        self.assertEqual(payload.result.attempted, 0)
        self.assertEqual(transport.urls, [])

    def test_kosis_normalizes_unit_period_and_direction(self) -> None:
        transport = FakeTransport(
            (
                _response(
                    [
                        {"PRD_DE": "202605", "DT": "116.1", "UNIT_NM": "2020 = 100", "LST_CHN_DE": "20260603"},
                        {"PRD_DE": "202606", "DT": "116.5", "UNIT_NM": "2020 = 100", "LST_CHN_DE": "20260702"},
                    ]
                ),
            )
        )
        item = _item("kosis-1", "소비자물가 6월 상승", "소비자물가 지수가 올랐다.", query="물가")
        payload = KosisAdapter(
            api_key="placeholder-kosis-key",
            datasets=(_kosis_dataset(),),
            max_requests=1,
            transport=transport,
        ).fetch((item,))
        self.assertTrue(payload.result.success)
        evidence = payload.evidence[0][1]
        self.assertEqual(evidence.unit, "2020 = 100")
        self.assertEqual(evidence.period, "202606")
        self.assertEqual(evidence.revision_date, "20260702")
        self.assertIn("상승", evidence.description)
        self.assertEqual(evidence.fact_values[0], "202606=116.5 2020 = 100")
        self.assertIn("/openapi/Param/statisticsParameterData.do", transport.urls[0])
        query = parse_qs(urlparse(transport.urls[0]).query)
        self.assertEqual(query["objL1"], ["00"])
        self.assertEqual(query["objL2"], ["0"])
        self.assertEqual(query["itmId"], ["1000"])

    def test_kosis_query_provenance_cannot_trigger_unrelated_article_augmentation(self) -> None:
        transport = FakeTransport(
            (
                _response(
                    [
                        {"PRD_DE": "202606", "DT": "116.5", "UNIT_NM": "2020=100", "LST_CHN_DE": "20260702"},
                        {"PRD_DE": "202605", "DT": "116.1", "UNIT_NM": "2020=100", "LST_CHN_DE": "20260603"},
                    ]
                ),
            )
        )
        item = _item(
            "kosis-query-only",
            "AI 모델 투자 발표",
            "AI 모델 출시 일정이 공개됐다.",
            query="소비자물가",
        )
        payload = KosisAdapter(
            api_key="placeholder-kosis-key",
            datasets=(_kosis_dataset(),),
            max_requests=1,
            transport=transport,
        ).fetch((item,))
        self.assertEqual(payload.evidence, ())
        self.assertEqual(payload.result.attempted, 0)

    def test_kosis_rejects_unexpected_unit(self) -> None:
        transport = FakeTransport(
            (
                _response(
                    [{"PRD_DE": "202606", "DT": "116.5", "UNIT_NM": "%", "LST_CHN_DE": "20260702"}]
                ),
            )
        )
        item = _item("kosis-2", "소비자물가 6월 상승", "물가 변화가 발표됐다.", query="물가")
        payload = KosisAdapter(
            api_key="placeholder-kosis-key",
            datasets=(_kosis_dataset(),),
            max_requests=1,
            transport=transport,
        ).fetch((item,))
        self.assertFalse(payload.result.success)
        self.assertTrue(payload.result.failure_reason.startswith("UNIT_MISMATCH:"))
        self.assertEqual(payload.evidence, ())

    def test_kosis_rejects_same_subject_with_mismatched_period(self) -> None:
        transport = FakeTransport(
            (
                _response(
                    [{"PRD_DE": "202606", "DT": "116.5", "UNIT_NM": "2020=100", "LST_CHN_DE": "20260702"}]
                ),
            )
        )
        item = _item("kosis-period", "소비자물가 5월 상승", "5월 물가가 올랐다.", query="물가")
        payload = KosisAdapter(
            api_key="placeholder-kosis-key",
            datasets=(_kosis_dataset(),),
            max_requests=1,
            transport=transport,
        ).fetch((item,))
        self.assertTrue(payload.result.success)
        self.assertEqual(payload.evidence, ())

    def test_kosis_accepts_official_base_index_punctuation_variant(self) -> None:
        transport = FakeTransport(
            (
                _response(
                    [{"PRD_DE": "202606", "DT": "116.5", "UNIT_NM": "2020,100", "LST_CHN_DE": "20260702"}]
                ),
            )
        )
        item = _item("kosis-variant", "소비자물가 6월 지수", "소비자물가 지수가 발표됐다.", query="물가")
        payload = KosisAdapter(
            api_key="placeholder-kosis-key",
            datasets=(_kosis_dataset(),),
            max_requests=1,
            transport=transport,
        ).fetch((item,))
        self.assertTrue(payload.result.success)
        self.assertEqual(payload.evidence[0][1].unit, "2020,100")

    def test_kosis_accepts_compact_official_base_index_unit(self) -> None:
        transport = FakeTransport(
            (
                _response(
                    [{"PRD_DE": "202606", "DT": "116.5", "UNIT_NM": "2020100", "LST_CHN_DE": "20260702"}]
                ),
            )
        )
        item = _item("kosis-compact-unit", "소비자물가 6월 지수", "소비자물가 지수가 발표됐다.", query="물가")
        payload = KosisAdapter(
            api_key="placeholder-kosis-key",
            datasets=(_kosis_dataset(),),
            max_requests=1,
            transport=transport,
        ).fetch((item,))
        self.assertTrue(payload.result.success)
        self.assertEqual(payload.evidence[0][1].unit, "2020100")

    def test_kosis_accepts_base_index_separator_variant(self) -> None:
        transport = FakeTransport(
            (
                _response(
                    [{"PRD_DE": "202606", "DT": "116.5", "UNIT_NM": "2020:100", "LST_CHN_DE": "20260702"}]
                ),
            )
        )
        item = _item("kosis-separator-unit", "소비자물가 6월 지수", "소비자물가 지수가 발표됐다.", query="물가")
        payload = KosisAdapter(
            api_key="placeholder-kosis-key",
            datasets=(_kosis_dataset(),),
            max_requests=1,
            transport=transport,
        ).fetch((item,))
        self.assertTrue(payload.result.success)
        self.assertEqual(payload.evidence[0][1].unit, "2020:100")

    def test_router_keeps_naver_path_alive_when_one_adapter_fails(self) -> None:
        transport = FakeTransport(
            (
                TimeoutError(),
                _response(
                    [
                        {"PRD_DE": "202606", "DT": "116.5", "UNIT_NM": "2020=100", "LST_CHN_DE": "20260702"},
                        {"PRD_DE": "202605", "DT": "116.1", "UNIT_NM": "2020=100", "LST_CHN_DE": "20260603"},
                    ]
                ),
            )
        )
        config = AuthorityConfig(
            schema_version=1,
            open_dart=_dart_config(),
            kosis=KosisConfig(enabled=True, max_requests=1, datasets=(_kosis_dataset(),)),
        )
        item = _item(
            "router-1",
            "하이브 6월 소비자물가 지수 상승",
            "하이브와 물가가 함께 언급된 후보.",
            query="물가",
            topic_id="kpop",
        )
        report = AuthoritativeRouter(
            config=config,
            transport=transport,
            open_dart_key="placeholder-opendart-key",
            kosis_key="placeholder-kosis-key",
        ).augment((item,), now=datetime(2026, 8, 10, 7, 30))
        self.assertEqual(len(report.items), 1)
        self.assertEqual(len(report.items[0].authoritative_evidence), 1)
        self.assertEqual(report.items[0].authoritative_evidence[0].adapter, "kosis")
        self.assertEqual(report.items[0].authority_conflict, "CONFIRMED_MATCH")
        self.assertEqual(report.succeeded, 1)
        self.assertTrue(any("공식 근거 보강" in warning for warning in report.warnings))
        self.assertEqual([audit["adapter"] for audit in report.audits], ["opendart", "kosis"])

    def test_router_records_numeric_fact_conflict_without_dropping_candidate(self) -> None:
        transport = FakeTransport(
            (
                _response(
                    [
                        {"PRD_DE": "202606", "DT": "116.5", "UNIT_NM": "2020=100", "LST_CHN_DE": "20260702"},
                        {"PRD_DE": "202605", "DT": "116.1", "UNIT_NM": "2020=100", "LST_CHN_DE": "20260603"},
                    ]
                ),
            )
        )
        config = AuthorityConfig(
            schema_version=1,
            open_dart=OpenDartConfig(False, 7, 50, "B", 1, ()),
            kosis=KosisConfig(enabled=True, max_requests=1, datasets=(_kosis_dataset(),)),
        )
        item = _item("router-conflict", "소비자물가 6월 116.4 상승", "소비자물가 수치가 제시됐다.", query="물가")
        report = AuthoritativeRouter(
            config=config,
            transport=transport,
            kosis_key="placeholder-kosis-key",
        ).augment((item,), now=datetime(2026, 8, 10, 7, 30))
        self.assertEqual(len(report.items[0].authoritative_evidence), 1)
        self.assertEqual(report.items[0].authority_conflict, "VALUE_CONFLICT")
        self.assertEqual(report.audits[0]["adapter"], "opendart")
        self.assertEqual(report.audits[1]["conflicts_found"], 1)

    def test_router_does_not_compare_rate_to_official_base_index(self) -> None:
        transport = FakeTransport(
            (
                _response(
                    [
                        {"PRD_DE": "202606", "DT": "116.5", "UNIT_NM": "2020=100", "LST_CHN_DE": "20260702"},
                        {"PRD_DE": "202605", "DT": "116.1", "UNIT_NM": "2020=100", "LST_CHN_DE": "20260603"},
                    ]
                ),
            )
        )
        config = AuthorityConfig(
            schema_version=1,
            open_dart=OpenDartConfig(False, 7, 50, "B", 1, ()),
            kosis=KosisConfig(enabled=True, max_requests=1, datasets=(_kosis_dataset(),)),
        )
        item = _item("router-rate", "소비자물가 6월 2.7% 상승", "소비자물가가 2.7% 상승했다.", query="물가")
        report = AuthoritativeRouter(config=config, transport=transport, kosis_key="placeholder-kosis-key").augment(
            (item,), now=datetime(2026, 8, 10, 7, 30)
        )
        self.assertEqual(report.items[0].authority_conflict, "CONFIRMED_MATCH")
