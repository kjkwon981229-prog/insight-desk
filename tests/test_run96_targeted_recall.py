from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

from insight_desk.config import load_topics
from insight_desk.domain.models import EvidenceType, NewsItem
from insight_desk.pipeline.clustering import StoryCluster
from insight_desk.pipeline.editorial import assess_cluster
from insight_desk.pipeline.selection import _is_strong_rejected, select_clusters
from insight_desk.pipeline.semantics import typed_event_relation
from insight_desk.pipeline.synthesis import editorial_text_issues, synthesize_cluster


FIXTURE = Path(__file__).with_name("fixtures") / "run96_targeted_recall.json"


def _item(
    record: dict[str, object],
    *,
    lead: str | None = None,
    enriched: bool = True,
) -> NewsItem:
    evidence_id = str(record["id"])
    title = str(record["title"])
    evidence_lead = str(record["lead"]) if lead is None else lead
    provenance = (EvidenceType.SEARCH_SNIPPET,)
    if enriched:
        provenance = (*provenance, EvidenceType.ENRICHED_METADATA)
    return NewsItem(
        evidence_id=evidence_id,
        topic_id=str(record["topic_id"]),
        query=str(record["query"]),
        title=title,
        summary=evidence_lead,
        original_url=f"https://run96-replay.test/{evidence_id}",
        naver_url="",
        canonical_url=f"https://run96-replay.test/{evidence_id}",
        published_at="2026-08-13T07:00:00+09:00",
        source_domain="run96-replay.test",
        content_hash=evidence_id,
        score=88.0,
        metadata_title=title if enriched else "",
        metadata_description=evidence_lead if enriched else "",
        publisher="run96-replay.test",
        provenance=provenance,
        matched_topic_ids=(str(record["topic_id"]),),
        retrieval_channels=("SIM",),
        retrieval_queries=(str(record["query"]),),
    )


class Run96TargetedRecallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.topics, _ = load_topics(Path("config/topics.json"))
        cls.topic_by_id = {topic.id: topic for topic in cls.topics}

    def test_confirmed_fn_corpus_survives_as_typed_events(self) -> None:
        positives = self.payload["positive_events"]
        self.assertEqual(len(positives), self.payload["confirmed_fn_event_count"])
        self.assertEqual(
            sum(int(record["candidate_weight"]) for record in positives),
            self.payload["confirmed_fn_candidate_count"],
        )

        for record in positives:
            item = _item(record)
            cluster = StoryCluster(str(record["topic_id"]), (item,))
            assessment = assess_cluster(
                cluster,
                self.topic_by_id[str(record["topic_id"])],
                novelty="NEW",
            )
            self.assertEqual(assessment.event.event_type, record["event_type"], record["id"])
            self.assertEqual(assessment.event.action, record["action"], record["id"])
            self.assertTrue(assessment.event.passed, record["id"])
            self.assertTrue(assessment.qualified, record["id"])

            result = select_clusters((cluster,), self.topics, limit=10)
            self.assertEqual(len(result.selected), 1, record["id"])
            self.assertEqual(result.strong_rejected_candidates, 0, record["id"])
            row = result.audit[0]
            self.assertTrue(row["qualifying"], record["id"])
            self.assertNotIn("SYNTHESIS_FACT_LOSS", row["selection_reasons"], record["id"])

            canonical = assessment.event.canonical_event
            self.assertIsNotNone(canonical, record["id"])
            self.assertTrue(canonical.fact_complete, record["id"])
            self.assertIn(item.evidence_id, canonical.evidence_owner_ids, record["id"])
            headline, summary, _, _, _, _ = synthesize_cluster(
                cluster,
                topic_name=self.topic_by_id[str(record["topic_id"])].name,
                trend_metrics=(),
                canonical_event_override=canonical,
            )
            self.assertTrue(headline, record["id"])
            self.assertTrue(summary, record["id"])
            self.assertEqual(editorial_text_issues(summary), (), record["id"])
            if record["id"] == "partner-selection":
                self.assertIn("Partner로 선정됐다", summary)
            if record["id"] == "english-chart-result":
                self.assertIn("빌보드 200", headline)
                self.assertNotIn("Arirang는", summary)

    def test_all_44_forensic_true_negatives_are_not_admitted_by_new_relation_parser(self) -> None:
        negatives = self.payload["true_negative_titles"]
        self.assertEqual(len(negatives), 44)
        for title in negatives:
            self.assertIsNone(typed_event_relation(title), title)

    def test_boundary_pairs_require_actor_predicate_and_material_object(self) -> None:
        positives = (
            "회사는 인디애나 HBM 공장 착공식을 열었다",
            "정부는 반도체 규제를 완화했다",
            "기관은 A사를 공식 파트너로 선정했다",
        )
        negatives = (
            "회사는 인디애나 공장 건설 전략을 설명했다",
            "업계에서는 규제 완화 필요성을 제기했다",
            "A사는 파트너 선정 가능성이 거론됐다",
            "한화 선발 화이트의 역투",
            "데이터센터 투자 전략 분석",
        )
        for title in positives:
            self.assertIsNotNone(typed_event_relation(title), title)
        for title in negatives:
            self.assertIsNone(typed_event_relation(title), title)

    def test_owned_title_relation_is_not_foreign_fact_or_missing_enrichment(self) -> None:
        record = self.payload["positive_events"][0]
        item = _item(record, lead="", enriched=False)
        cluster = StoryCluster(str(record["topic_id"]), (item,))
        assessment = assess_cluster(
            cluster,
            self.topic_by_id[str(record["topic_id"])],
            novelty="NEW",
        )
        self.assertTrue(assessment.event.canonical_event.fact_complete)
        self.assertTrue(assessment.qualified)
        self.assertIn("SUPPORTED_SINGLE_SOURCE", assessment.reasons)
        self.assertNotIn("FACT_OWNERSHIP_UNSUPPORTED", assessment.reasons)

    def test_complete_title_metric_survives_without_a_trusted_lead(self) -> None:
        record = next(
            item for item in self.payload["positive_events"] if item["id"] == "market-move"
        )
        item = _item(record, lead="", enriched=False)
        cluster = StoryCluster("economy", (item,))
        assessment = assess_cluster(
            cluster,
            self.topic_by_id["economy"],
            novelty="NEW",
        )
        self.assertTrue(assessment.event.canonical_event.fact_complete)
        self.assertTrue(assessment.qualified)
        self.assertNotIn("SINGLE_SOURCE_METRIC_WITHOUT_TRUSTED_LEAD", assessment.reasons)
        result = select_clusters((cluster,), self.topics, limit=10)
        self.assertEqual(len(result.selected), 1)
        self.assertEqual(result.strong_rejected_candidates, 0)

    def test_owned_relation_loss_is_visible_without_a_story_quota(self) -> None:
        record = self.payload["positive_events"][0]
        cluster = StoryCluster(str(record["topic_id"]), (_item(record),))
        assessment = assess_cluster(
            cluster,
            self.topic_by_id[str(record["topic_id"])],
            novelty="NEW",
        )
        broken = replace(
            assessment,
            event=replace(
                assessment.event,
                passed=False,
                reasons=(*assessment.event.reasons, "EVENT_ACTION_CONTRACT_FAILED"),
            ),
            qualified=False,
            reasons=tuple(
                reason for reason in assessment.reasons if reason != "QUALIFIED"
            )
            + ("EVENT_ACTION_CONTRACT_FAILED", "REJECTED_BY_EDITORIAL_GATE"),
        )
        self.assertTrue(_is_strong_rejected(broken))

        weak_record = {
            "id": "strategy-only",
            "topic_id": "ai_tech",
            "query": "AI",
            "title": "데이터센터 중심 AI 투자 전략 분석",
            "lead": "업계 전략과 전망을 설명했다.",
        }
        weak = assess_cluster(
            StoryCluster("ai_tech", (_item(weak_record),)),
            self.topic_by_id["ai_tech"],
            novelty="NEW",
        )
        self.assertFalse(_is_strong_rejected(weak))


if __name__ == "__main__":
    unittest.main()
