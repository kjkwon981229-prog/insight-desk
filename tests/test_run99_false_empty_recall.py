from __future__ import annotations

import json
import unittest
from datetime import datetime
from pathlib import Path

from insight_desk.config import load_topics
from insight_desk.domain.models import EvidenceType, NewsItem
from insight_desk.pipeline.clustering import StoryCluster
from insight_desk.pipeline.selection import select_clusters
from insight_desk.pipeline.semantics import (
    explicit_unclassified_event_signal,
    typed_event_relation,
)


FIXTURE = Path(__file__).with_name("fixtures") / "run96_targeted_recall.json"


def _item(
    *,
    evidence_id: str,
    topic_id: str,
    query: str,
    title: str,
    lead: str = "",
    publisher: str = "fixture.test",
) -> NewsItem:
    return NewsItem(
        evidence_id=evidence_id,
        topic_id=topic_id,
        query=query,
        title=title,
        summary=lead,
        original_url=f"https://fixture.test/{evidence_id}",
        naver_url="",
        canonical_url=f"https://fixture.test/{evidence_id}",
        published_at="2026-08-14T06:30:00+09:00",
        source_domain="fixture.test",
        content_hash=evidence_id,
        score=90.0,
        metadata_title=title,
        metadata_description=lead,
        publisher=publisher,
        provenance=(EvidenceType.SEARCH_SNIPPET, EvidenceType.ENRICHED_METADATA),
        matched_topic_ids=(topic_id,),
        retrieval_channels=("SIM",),
        retrieval_queries=(query,),
    )


class Run99FalseEmptyRecallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.topics, _ = load_topics(Path("config/topics.json"))

    def test_openai_executive_replacement_is_a_bound_relation(self) -> None:
        relation = typed_event_relation(
            "OpenAI replaces chief revenue officer after just months"
        )
        self.assertIsNotNone(relation)
        assert relation is not None
        event_type, fact = relation
        self.assertEqual(event_type, "ANNOUNCEMENT")
        self.assertEqual(fact.subject, "OpenAI")
        self.assertEqual(fact.object.casefold(), "chief revenue officer")
        self.assertEqual(fact.relation, "교체")

    def test_openai_replacement_does_not_admit_prospective_or_non_personnel_uses(self) -> None:
        negatives = (
            "OpenAI may replace chief revenue officer",
            "OpenAI could replace chief revenue officer",
            "OpenAI will replace chief revenue officer",
            "OpenAI plans to replace chief revenue officer",
            "Who could replace the CEO at OpenAI?",
            "CEO discusses replacing workers with AI",
            "Replacement demand for GPUs rises",
        )
        for title in negatives:
            self.assertIsNone(typed_event_relation(title), title)

    def test_run96_relation_families_accept_run99_surface_variants(self) -> None:
        cases = (
            (
                "삼성SDS 중앙부처 9곳에 AI 협업 솔루션 공급",
                "INDUSTRY_CHANGE",
                "공급",
            ),
            (
                "트와이스 채영 14년 만에 JYP 떠난다",
                "ANNOUNCEMENT",
                "떠남",
            ),
            (
                "KBO 규정 착오로 LG 오카다 영입 무산",
                "ROSTER_PERSONNEL",
                "영입 무산",
            ),
        )
        for title, event_type, action in cases:
            relation = typed_event_relation(title)
            self.assertIsNotNone(relation, title)
            assert relation is not None
            self.assertEqual(relation[0], event_type, title)
            self.assertEqual(relation[1].relation, action, title)

    def test_locked_run96_true_negatives_stay_closed(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        negatives = payload["true_negative_titles"]
        self.assertEqual(len(negatives), 44)
        for title in negatives:
            self.assertIsNone(typed_event_relation(title), title)

    def test_unclassified_signal_is_diagnostic_only_and_uncertainty_safe(self) -> None:
        self.assertTrue(
            explicit_unclassified_event_signal(
                "코스피 MSCI 정기변경, 에코프로머티 등 4개 종목 편입"
            )
        )
        negatives = (
            "MSCI 편입 가능성 전망",
            "MSCI 편입 검토",
            "Who could replace the CEO at OpenAI?",
            "AI 공급 전망",
            "GPU 공급 부족 분석",
        )
        for title in negatives:
            self.assertFalse(explicit_unclassified_event_signal(title), title)

    def test_unclassified_current_event_prevents_false_valid_empty(self) -> None:
        item = _item(
            evidence_id="run99-shadow-openai-acquisition",
            topic_id="ai_tech",
            query="OpenAI",
            title="OpenAI acquires startup in infrastructure deal",
            lead="OpenAI acquired the startup to expand its infrastructure operations.",
        )
        result = select_clusters(
            (StoryCluster("ai_tech", (item,)),),
            self.topics,
            limit=10,
            now=datetime.fromisoformat("2026-08-14T07:30:00+09:00"),
        )
        self.assertEqual(result.selected, ())
        self.assertEqual(result.strong_rejected_candidates, 1)
        self.assertTrue(result.filter_collapse)
        self.assertEqual(result.funnel["ai_tech"]["strong_rejected"], 1)

    def test_run99_openai_candidate_can_reach_selection(self) -> None:
        item = _item(
            evidence_id="run99-openai-cro",
            topic_id="ai_tech",
            query="OpenAI",
            title="OpenAI replaces chief revenue officer after just months",
            lead=(
                "OpenAI said Denise Dresser is leaving the chief revenue officer role "
                "after just months in the job."
            ),
            publisher="The New York Times",
        )
        result = select_clusters(
            (StoryCluster("ai_tech", (item,)),),
            self.topics,
            limit=10,
            now=datetime.fromisoformat("2026-08-14T07:30:00+09:00"),
        )
        self.assertEqual(len(result.selected), 1, result.audit)
        self.assertEqual(result.strong_rejected_candidates, 0)
        row = result.audit[0]
        self.assertTrue(row["qualifying"])
        self.assertEqual(row["event_type"], "ANNOUNCEMENT")


if __name__ == "__main__":
    unittest.main()
