from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

from insight_desk.config import load_topics
from insight_desk.domain.models import EvidenceType, NewsItem
from insight_desk.pipeline.clustering import StoryCluster
from insight_desk.pipeline.editorial import assess_event
from insight_desk.pipeline.selection import select_clusters, topic_diverse_enrichment_candidates
from insight_desk.pipeline.synthesis import synthesize_cluster


FIXTURE = Path(__file__).with_name("fixtures") / "run89_semantic_replay.json"


def _item(record: dict[str, str], *, metadata: bool = True) -> NewsItem:
    provenance = (EvidenceType.SEARCH_SNIPPET,)
    if metadata:
        provenance += (EvidenceType.ENRICHED_METADATA,)
    return NewsItem(
        evidence_id=record["id"],
        topic_id=record["topic_id"],
        query=record["query"],
        title=record["title"],
        summary=record["lead"],
        original_url=f"https://{record['domain']}/{record['id']}",
        naver_url="",
        canonical_url=f"https://{record['domain']}/{record['id']}",
        published_at="2026-08-10T07:00:00+09:00",
        source_domain=record["domain"],
        content_hash=record["id"],
        score=82.0,
        metadata_title=record["title"] if metadata else "",
        metadata_description=record["lead"] if metadata else "",
        publisher=record["domain"],
        provenance=provenance,
        matched_topic_ids=(record["topic_id"],),
        retrieval_channels=("SIM",),
        retrieval_queries=(record["query"],),
    )


class SemanticConvergenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.records = {record["id"]: record for record in payload["items"]}
        cls.topics, _ = load_topics(Path("config/topics.json"))

    def _topic(self, topic_id: str):
        return next(topic for topic in self.topics if topic.id == topic_id)

    def test_run89_replay_converges_semantics_without_literal_exceptions(self) -> None:
        records = self.records
        clusters = (
            StoryCluster("kbo_hanwha", (_item(records["heat-interruption"]),)),
            StoryCluster("kbo_hanwha", (_item(records["heat-resumption"]),)),
            StoryCluster("kbo_hanwha", (_item(records["sports-result-record"]),)),
            StoryCluster("psat_recruitment", (_item(records["recruitment-facts"]),)),
            StoryCluster("kpop", (_item(records["fan-poll"]),)),
            StoryCluster("ai_tech", (_item(records["ambiguous-percent"]),)),
            StoryCluster("ai_tech", (_item(records["product-facts"]),)),
        )

        result = select_clusters(clusters, self.topics, limit=10)
        selected_ids = {
            item.evidence_id
            for cluster in result.selected
            for item in cluster.items
        }

        self.assertTrue({"heat-interruption", "heat-resumption"}.issubset(selected_ids))
        self.assertIn("recruitment-facts", selected_ids)
        self.assertIn("product-facts", selected_ids)
        self.assertIn("sports-result-record", selected_ids)
        self.assertNotIn("fan-poll", selected_ids)
        self.assertNotIn("ambiguous-percent", selected_ids)
        kbo_clusters = [cluster for cluster in result.selected if cluster.topic_id == "kbo_hanwha"]
        self.assertEqual(len(kbo_clusters), 2)
        self.assertEqual(
            sum(
                {"heat-interruption", "heat-resumption"}.issubset(
                    {item.evidence_id for item in cluster.items}
                )
                for cluster in kbo_clusters
            ),
            1,
        )
        self.assertEqual(result.strong_rejected_candidates, 0)
        self.assertFalse(result.filter_collapse)

        audit = {entry["candidate_key"]: entry for entry in result.audit}
        poll_key = f"https://{records['fan-poll']['domain']}/fan-poll"
        earnings_key = f"https://{records['ambiguous-percent']['domain']}/ambiguous-percent"
        self.assertEqual(audit[poll_key]["reason"], "LOW_VALUE_EVENT")
        self.assertIn("WEAK_FACT_STRUCTURE", audit[earnings_key]["selection_reasons"])

    def test_sports_result_award_and_performance_facts_survive_downstream(self) -> None:
        item = _item(self.records["sports-result-record"])
        cluster = StoryCluster("kbo_hanwha", (item,))
        event = assess_event(cluster, self._topic("kbo_hanwha"))
        canonical = event.canonical_event
        self.assertTrue(event.passed)
        self.assertIsNotNone(canonical)
        assert canonical is not None
        self.assertTrue(canonical.fact_complete)
        self.assertEqual(canonical.subject, "외국인 타자")
        self.assertEqual(
            {fact.role for fact in canonical.facts},
            {"AWARD", "HOME_RUN_COUNT", "RBI_COUNT", "PERIOD"},
        )

        _, summary, _, _, facts, _ = synthesize_cluster(
            cluster,
            topic_name="KBO·한화 이글스",
            trend_metrics=(),
            canonical_event_override=canonical,
        )
        self.assertEqual(facts.event_signature, canonical.event_signature)
        self.assertEqual(facts.subject, canonical.subject)
        for expected in ("9홈런", "26타점", "MVP"):
            self.assertIn(expected, summary)

    def test_canonical_recruitment_bundle_is_consumed_unchanged_downstream(self) -> None:
        item = _item(self.records["recruitment-facts"])
        cluster = StoryCluster("psat_recruitment", (item,))
        event = assess_event(cluster, self._topic("psat_recruitment"))
        canonical = event.canonical_event
        self.assertIsNotNone(canonical)
        assert canonical is not None
        self.assertTrue(canonical.fact_complete)
        self.assertEqual(
            {fact.role for fact in canonical.facts},
            {"COMPETITION_RATIO", "SELECTION_COUNT", "APPLICANT_COUNT"},
        )

        _, summary, _, _, facts, _ = synthesize_cluster(
            cluster,
            topic_name="PSAT·공채 일정",
            trend_metrics=(),
            canonical_event_override=canonical,
        )
        self.assertEqual(facts.event_signature, canonical.event_signature)
        self.assertEqual(facts.subject, canonical.subject)
        for expected in ("30명", "372명", "12.4대1"):
            self.assertIn(expected, summary)

    def test_recruitment_headline_variants_converge_on_bound_facts(self) -> None:
        first = _item(self.records["recruitment-facts"])
        second = replace(
            first,
            evidence_id="recruitment-counts",
            title="부산시 지방공무원 7급 공채 30명 선발",
            summary="30명 선발에 372명이 지원해 경쟁률 12.4대1을 기록했다.",
            metadata_title="부산시 지방공무원 7급 공채 30명 선발",
            metadata_description="30명 선발에 372명이 지원해 경쟁률 12.4대1을 기록했다.",
            original_url="https://recruitment-b.example/counts",
            canonical_url="https://recruitment-b.example/counts",
            source_domain="recruitment-b.example",
            publisher="recruitment-b.example",
            content_hash="recruitment-counts",
        )
        result = select_clusters(
            (
                StoryCluster("psat_recruitment", (first,)),
                StoryCluster("psat_recruitment", (second,)),
            ),
            self.topics,
            limit=10,
        )
        self.assertEqual(len(result.selected), 1)
        self.assertEqual(result.selected[0].source_count, 2)
        self.assertEqual(result.strong_rejected_candidates, 0)

    def test_ratio_only_candidate_is_enrichment_gap_not_false_strong_event(self) -> None:
        item = _item(self.records["recruitment-facts"], metadata=False)
        item = replace(item, summary=item.title)
        cluster = StoryCluster("psat_recruitment", (item,))
        result = select_clusters((cluster,), self.topics, limit=10)
        self.assertEqual(result.selected, ())
        self.assertEqual(result.strong_rejected_candidates, 0)
        self.assertEqual(result.enrichment_candidates, (cluster,))

    def test_fact_gap_uses_bounded_enrichment_before_already_ready_story(self) -> None:
        gap = _item(self.records["recruitment-facts"], metadata=False)
        gap = replace(gap, summary=gap.title)
        ready = _item(self.records["product-facts"])
        preliminary = select_clusters(
            (
                StoryCluster("psat_recruitment", (gap,)),
                StoryCluster("ai_tech", (ready,)),
            ),
            self.topics,
            limit=10,
        )
        targets = topic_diverse_enrichment_candidates(
            (gap, ready),
            self.topics,
            limit=1,
            priority_clusters=(
                *preliminary.enrichment_candidates,
                *preliminary.selected,
            ),
        )
        self.assertEqual(targets, (gap,))

    def test_percent_earnings_requires_bound_direction_and_preserves_it(self) -> None:
        ambiguous = _item(self.records["ambiguous-percent"])
        ambiguous_cluster = StoryCluster("ai_tech", (ambiguous,))
        ambiguous_event = assess_event(ambiguous_cluster, self._topic("ai_tech"))
        self.assertFalse(ambiguous_event.passed)
        self.assertEqual(ambiguous_event.canonical_event.observations, ())

        explicit = replace(
            ambiguous,
            topic_id="economy",
            query="삼성전자",
            title="삼성전자 2분기 매출 85% 증가",
            summary="삼성전자의 2분기 매출이 85% 증가했다고 발표했다.",
            metadata_title="삼성전자 2분기 매출 85% 증가",
            metadata_description="삼성전자의 2분기 매출이 85% 증가했다고 발표했다.",
            matched_topic_ids=("economy",),
        )
        cluster = StoryCluster("economy", (explicit,))
        event = assess_event(cluster, self._topic("economy"))
        self.assertTrue(event.passed)
        canonical = event.canonical_event
        assert canonical is not None
        self.assertEqual(canonical.observations[0].direction, "증가")
        _, summary, _, watch, facts, _ = synthesize_cluster(
            cluster,
            topic_name="경제·투자",
            trend_metrics=(),
            canonical_event_override=canonical,
        )
        self.assertIn("매출이 85% 증가", summary)
        self.assertNotIn("85%를 기록", summary)
        self.assertEqual(facts.action, "증가")
        self.assertEqual(watch, ())

    def test_material_official_conflict_cannot_receive_an_evidence_boost(self) -> None:
        source = _item(self.records["ambiguous-percent"])
        conflicted = replace(
            source,
            topic_id="economy",
            query="삼성전자",
            title="삼성전자 2분기 매출 85% 증가",
            summary="삼성전자의 2분기 매출이 85% 증가했다고 발표했다.",
            metadata_title="삼성전자 2분기 매출 85% 증가",
            metadata_description="삼성전자의 2분기 매출이 85% 증가했다고 발표했다.",
            matched_topic_ids=("economy",),
            authority_conflict="VALUE_CONFLICT",
        )
        result = select_clusters(
            (StoryCluster("economy", (conflicted,)),),
            self.topics,
            limit=10,
        )
        self.assertEqual(result.selected, ())
        self.assertEqual(result.audit[0]["reason"], "AUTHORITY_CONFLICT")
        self.assertIn("AUTHORITY_CONFLICT", result.audit[0]["selection_reasons"])
        self.assertIn("VALUE_CONFLICT", result.audit[0]["selection_reasons"])
        self.assertNotIn("OFFICIAL_SOURCE", result.audit[0]["selection_reasons"])

    def test_recognized_chart_survives_while_fan_poll_does_not(self) -> None:
        poll = _item(self.records["fan-poll"])
        chart = replace(
            poll,
            evidence_id="recognized-chart",
            title="아티스트 새 앨범 국내 음원 차트 1위",
            summary="아티스트가 새 앨범 발매 당일 국내 음원 차트 1위에 올랐다.",
            metadata_title="아티스트 새 앨범 국내 음원 차트 1위",
            metadata_description="아티스트가 새 앨범 발매 당일 국내 음원 차트 1위에 올랐다.",
            original_url="https://chart.example/recognized-chart",
            canonical_url="https://chart.example/recognized-chart",
            source_domain="chart.example",
            content_hash="recognized-chart",
        )
        result = select_clusters(
            (StoryCluster("kpop", (poll,)), StoryCluster("kpop", (chart,))),
            self.topics,
            limit=10,
        )
        self.assertEqual([cluster.representative.evidence_id for cluster in result.selected], ["recognized-chart"])
        self.assertEqual(result.strong_rejected_candidates, 0)


if __name__ == "__main__":
    unittest.main()
