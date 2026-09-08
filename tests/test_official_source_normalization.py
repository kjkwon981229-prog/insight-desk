from __future__ import annotations

import unittest
from datetime import datetime, timezone

from insight_desk.acquisition import (
    normalize_ecos_statistics,
    normalize_kosis_statistics,
    normalize_opendart_filings,
)
from insight_desk.core import EvidenceField, EvidenceSpan

NOW = datetime(2026, 8, 23, 2, 0, tzinfo=timezone.utc)
FAKE_SECRET = "SECRET_KEY_MUST_NEVER_APPEAR"


def evidence_for_literal(article, literal: str) -> EvidenceSpan:
    start = article.body.index(literal)
    return EvidenceSpan.from_article(
        evidence_id="ev-1",
        article=article,
        field=EvidenceField.BODY,
        start=start,
        end=start + len(literal),
    )


class OpenDartNormalizationTests(unittest.TestCase):
    def test_filing_uses_secret_free_public_url_and_preserves_fields(self) -> None:
        payload = {
            "status": "000",
            "list": [
                {
                    "corp_code": "00126380",
                    "corp_name": "삼성전자",
                    "report_nm": "주요사항보고서(유상증자결정)",
                    "rcept_no": "20260823000123",
                    "rcept_dt": "20260823",
                    "flr_nm": "삼성전자",
                    "remark": "13.6%",
                }
            ],
        }
        articles = normalize_opendart_filings(
            payload,
            fetched_at=NOW,
            corp_code="00126380",
            topic_ids=("economy",),
            query="삼성전자 공시",
        )
        self.assertEqual(len(articles), 1)
        article = articles[0]
        self.assertEqual(article.title, "삼성전자 · 주요사항보고서(유상증자결정)")
        self.assertIn("rcpNo=20260823000123", article.provenance.url)
        self.assertNotIn("crtfc_key", article.provenance.url)
        self.assertNotIn(FAKE_SECRET, article.provenance.url)
        self.assertEqual(article.provenance.retrieved_via, "opendart_api")
        self.assertIsNone(article.provenance.published_at)
        for literal in ("삼성전자", "20260823", "13.6%"):
            self.assertIn(literal, article.body)
            span = evidence_for_literal(article, literal)
            span.validate_against(article)
            self.assertEqual(span.text, literal)

    def test_duplicate_receipt_is_emitted_once(self) -> None:
        row = {"corp_name": "A", "report_nm": "공시", "rcept_no": "1"}
        articles = normalize_opendart_filings(
            {"list": [row, dict(row)]},
            fetched_at=NOW,
            corp_code="00000001",
            topic_ids=("economy",),
            query="A 공시",
        )
        self.assertEqual(len(articles), 1)


class KosisNormalizationTests(unittest.TestCase):
    def test_statistics_are_deterministic_evidence_text_with_safe_public_url(self) -> None:
        payload = [
            {
                "PRD_DE": "2026",
                "C1_NM": "전국",
                "ITM_NM": "인구",
                "DT": "1,050만",
            },
            {
                "PRD_DE": "2025",
                "C1_NM": "전국",
                "ITM_NM": "증가율",
                "DT": "13.6%",
            },
        ]
        article = normalize_kosis_statistics(
            payload,
            fetched_at=NOW,
            org_id="101",
            table_id="DT_1B040A3",
            topic_ids=("economy",),
            query="인구 통계",
        )
        self.assertEqual(article.provenance.source_name, "KOSIS 국가통계포털")
        self.assertIn("orgId=101", article.provenance.url)
        self.assertIn("tblId=DT_1B040A3", article.provenance.url)
        self.assertNotIn("apiKey", article.provenance.url)
        self.assertNotIn(FAKE_SECRET, article.provenance.url)
        for literal in ("1,050만", "13.6%", "2026"):
            span = evidence_for_literal(article, literal)
            span.validate_against(article)
            self.assertEqual(span.text, literal)

    def test_same_payload_produces_same_document_id(self) -> None:
        kwargs = dict(
            fetched_at=NOW,
            org_id="101",
            table_id="T1",
            topic_ids=("economy",),
            query="통계",
        )
        left = normalize_kosis_statistics([{"DT": "317억 달러"}], **kwargs)
        right = normalize_kosis_statistics([{"DT": "317억 달러"}], **kwargs)
        self.assertEqual(left.article_id, right.article_id)
        self.assertEqual(left.body, right.body)


class EcosNormalizationTests(unittest.TestCase):
    def test_ecos_never_persists_credential_bearing_api_url(self) -> None:
        payload = {
            "StatisticSearch": {
                "list_total_count": 1,
                "row": [
                    {
                        "STAT_CODE": "722Y001",
                        "STAT_NAME": "기준금리",
                        "TIME": "202608",
                        "DATA_VALUE": "3.25",
                        "UNIT_NAME": "%",
                    }
                ],
            }
        }
        article = normalize_ecos_statistics(
            payload,
            fetched_at=NOW,
            stat_code="722Y001",
            cycle="M",
            start_period="202608",
            end_period="202608",
            topic_ids=("economy",),
            query="한국은행 기준금리",
        )
        self.assertEqual(article.provenance.url, "https://ecos.bok.or.kr/")
        self.assertNotIn(FAKE_SECRET, article.provenance.url)
        self.assertNotIn("api/StatisticSearch", article.provenance.url)
        self.assertEqual(article.provenance.retrieved_via, "ecos_api")
        for literal in ("기준금리", "202608", "3.25", "722Y001"):
            span = evidence_for_literal(article, literal)
            span.validate_against(article)
            self.assertEqual(span.text, literal)


if __name__ == "__main__":
    unittest.main()
