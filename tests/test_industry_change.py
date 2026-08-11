from __future__ import annotations

import json
import unittest
from pathlib import Path

from insight_desk.config import load_topics
from insight_desk.domain.models import EvidenceType, NewsItem
from insight_desk.pipeline.clustering import StoryCluster
from insight_desk.pipeline.editorial import assess_event
from insight_desk.pipeline.selection import select_clusters
from insight_desk.pipeline.semantics import build_canonical_event, event_action_signal, industry_change_facts
from insight_desk.pipeline.synthesis import (
    industry_summary_preserves_fact_binding,
    synthesize_cluster,
)


FIXTURE = Path(__file__).with_name("fixtures") / "run91_industry_change_replay.json"


def _item(title: str, lead: str, *, evidence_id: str = "industry") -> NewsItem:
    return NewsItem(
        evidence_id,
        "ai_tech",
        "인공지능",
        title,
        lead,
        f"https://industry.example/{evidence_id}",
        "",
        f"https://industry.example/{evidence_id}",
        "2026-08-10T07:00:00+09:00",
        "industry.example",
        evidence_id,
        82.0,
        metadata_title=title,
        metadata_description=lead,
        publisher="industry.example",
        provenance=(EvidenceType.SEARCH_SNIPPET, EvidenceType.ENRICHED_METADATA),
        matched_topic_ids=("ai_tech",),
        retrieval_channels=("DATE",),
        retrieval_queries=("인공지능",),
    )


class IndustryChangeTests(unittest.TestCase):
    def test_material_relationship_matrix_is_bound_and_preserved(self) -> None:
        cases = (
            ("investment amount", "네오테크, 5000억원 AI 투자 유치", "네오테크가 5000억원 규모의 AI 투자를 유치했다.", ("5000억원",)),
            ("comparison", "AI 보안 투자 91 vs 고도화 16", "AI 보안 분야에서 투자 91과 고도화 16의 비교 수치가 제시됐다.", ("91", "16")),
            ("ratio", "네오테크 점유율 18%에서 27%로 확대", "네오테크의 점유율이 18%에서 27%로 확대됐다.", ("18%", "27%")),
            ("contract quantity", "네오테크, 20만대 서버 공급 계약", "네오테크가 20만대 서버 공급 계약을 체결했다.", ("20만대",)),
            ("production change", "네오테크 월 생산량 3만에서 5만으로 확대", "네오테크의 월 생산량을 3만에서 5만으로 확대했다.", ("3만", "5만")),
            ("acquisition amount", "네오테크, 2조원에 기업 인수", "네오테크가 2조원에 기업을 인수했다.", ("2조원",)),
            ("strategy fact", "네오테크 신사업 전략 3000억원 투자", "네오테크는 신사업 전략에 3000억원을 투자한다고 밝혔다.", ("3000억원",)),
            ("single-source fact-rich", "AI 보안 투자 91 vs 고도화 16", "AI 보안 분야에서 투자 91과 고도화 16의 비교 수치가 제시됐다.", ("91", "16")),
        )
        for case_name, title, lead, expected_values in cases:
            canonical = build_canonical_event("INDUSTRY_CHANGE", title, lead=lead)
            self.assertTrue(canonical.facts, case_name)
            self.assertTrue(canonical.fact_complete, case_name)
            _, summary, _, _, _, _ = synthesize_cluster(
                StoryCluster("ai_tech", (_item(title, lead, evidence_id=case_name),)),
                topic_name="AI·테크",
                trend_metrics=(),
                event_type_override="INDUSTRY_CHANGE",
                canonical_event_override=canonical,
            )
            for value in expected_values:
                self.assertIn(value, summary, case_name)
            self.assertTrue(industry_summary_preserves_fact_binding(title, summary, canonical.facts), case_name)

    def test_negative_numeric_shapes_do_not_become_industry_facts(self) -> None:
        cases = (
            "네오테크 매출 500억원, 직원 100명 현황",
            "네오테크 2026년 5일 행사",
            "네오테크 전략 발표",
            "네오테크 91 16",
        )
        for title in cases:
            self.assertEqual(industry_change_facts(title), (), title)

    def test_run91_replay_has_no_downstream_fact_loss(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        record = payload["items"][0]
        item = _item(record["title"], record["lead"], evidence_id=record["id"])
        topics, _ = load_topics(Path("config/topics.json"))
        result = select_clusters((StoryCluster("ai_tech", (item,)),), topics, limit=10)
        self.assertEqual(len(result.selected), 1)
        self.assertEqual(result.strong_rejected_candidates, 0)
        self.assertFalse(result.filter_collapse)
        audit = next(entry for entry in result.audit if entry["candidate_key"].endswith(record["id"]))
        self.assertTrue(audit["qualifying"])
        self.assertNotIn("SYNTHESIS_FACT_LOSS", audit["selection_reasons"])
        _, summary, _, _, _, _ = synthesize_cluster(
            result.selected[0],
            topic_name="AI·테크",
            trend_metrics=(),
        )
        self.assertIn("91", summary)
        self.assertIn("16", summary)

    def test_industry_event_type_survives_generalized_change_markers(self) -> None:
        topics, _ = load_topics(Path("config/topics.json"))
        topic = next(topic for topic in topics if topic.id == "ai_tech")
        item = _item(
            "네오테크 점유율 18%에서 27%로 확대",
            "네오테크의 점유율이 18%에서 27%로 확대됐다.",
        )
        event = assess_event(StoryCluster("ai_tech", (item,)), topic)
        self.assertEqual(event.event_type, "INDUSTRY_CHANGE")
        self.assertTrue(event.passed)
        self.assertEqual(event.canonical_event.facts[0].role, "RATIO_CHANGE")

    def test_terminal_industry_action_and_change_sentence_remain_bound(self) -> None:
        title = "네오테크, 5000억원 AI 투자 유치"
        lead = "네오테크가 5000억원 규모의 AI 투자를 유치했다."
        self.assertEqual(event_action_signal("INDUSTRY_CHANGE", title, lead), "유치")
        event = build_canonical_event("INDUSTRY_CHANGE", title, lead=lead)
        _, summary, _, _, _, _ = synthesize_cluster(
            StoryCluster("ai_tech", (_item(title, lead),)),
            topic_name="AI·테크",
            trend_metrics=(),
            event_type_override="INDUSTRY_CHANGE",
            canonical_event_override=event,
        )
        self.assertIn("5000억원", summary)
        self.assertIn("투자를 유치했다", summary)

        production_title = "네오테크 월 생산량 3만에서 5만으로 확대"
        production_lead = "네오테크의 월 생산량을 3만에서 5만으로 확대했다."
        production_event = build_canonical_event("INDUSTRY_CHANGE", production_title, lead=production_lead)
        _, production_summary, _, _, _, _ = synthesize_cluster(
            StoryCluster("ai_tech", (_item(production_title, production_lead),)),
            topic_name="AI·테크",
            trend_metrics=(),
            event_type_override="INDUSTRY_CHANGE",
            canonical_event_override=production_event,
        )
        self.assertIn("생산 관련 수치가 3만에서 5만으로 확대됐다", production_summary)
