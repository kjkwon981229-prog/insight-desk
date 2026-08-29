from __future__ import annotations

from pathlib import Path
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact
from scripts.phase11_daily_production_core import TopicConfig, event_topic_relevant


def _decision(
    *,
    topic: TopicConfig,
    subject: str,
    action: str,
    evidence_text: str,
    object: str | None = None,
) -> bool:
    evidence_id = "evidence-1"
    fact_id = "fact-1"
    article_id = "article-1"
    event = CandidateEvent(
        event_id="event-1",
        topic_id=topic.topic_id,
        fact_ids=(fact_id,),
        article_ids=(article_id,),
    )
    fact = EventFact(
        fact_id=fact_id,
        subject=subject,
        action=action,
        object=object,
        evidence_ids=(evidence_id,),
    )
    span = EvidenceSpan(
        evidence_id=evidence_id,
        article_id=article_id,
        field=EvidenceField.BODY,
        start=0,
        end=len(evidence_text),
        text=evidence_text,
    )
    return event_topic_relevant(
        event=event,
        facts={fact_id: fact},
        evidence={evidence_id: span},
        topic=topic,
    )


def _economy() -> TopicConfig:
    return TopicConfig(
        topic_id="economy",
        name="경제·투자",
        priority=75,
        candidate_budget=8,
        selection_cap=3,
        intent_anchors=("한국은행", "기준금리", "환율", "코스피", "투자"),
        required_intent_terms=(),
        news_queries=("한국은행 기준금리",),
        event_terms=("발표", "기준금리", "환율", "코스피", "투자"),
    )


def _psat() -> TopicConfig:
    return TopicConfig(
        topic_id="psat_recruitment",
        name="PSAT·공채 일정",
        priority=55,
        candidate_budget=8,
        selection_cap=3,
        intent_anchors=("PSAT", "공직적격성평가", "5급 공채", "7급 공채", "국가공무원 채용", "채용", "시험"),
        required_intent_terms=("공직적격성평가", "5급 공채", "7급 공채", "국가공무원", "공무원 시험", "인사혁신처", "공채", "공무원", "5급", "7급"),
        news_queries=("PSAT",),
        event_terms=("시험", "공채", "채용", "원서접수", "일정", "공고", "합격", "선발", "시행", "개편"),
    )


class FreshEventRoutingRegressions(unittest.TestCase):
    def test_active_v2_adapter_uses_evidence_local_event_routing_not_assigned_topic_tautology(self) -> None:
        source = Path("insight_desk/production_orchestrator_compat_v2.py").read_text(encoding="utf-8")
        self.assertIn("legacy_event_topic_relevant = core_module.event_topic_relevant", source)
        start = source.index("    def event_relevant(")
        end = source.index("    def build_rendered_briefing_v2(", start)
        owner = source[start:end]
        self.assertIn("return legacy_event_topic_relevant(", owner)
        self.assertNotIn("canonical.topic == topic.topic_id", owner)

    def test_daily_core_consumes_one_article_level_understanding_map_before_phase6(self) -> None:
        source = Path("scripts/phase11_daily_production_core.py").read_text(encoding="utf-8")
        self.assertIn("assess_compatibility_article_understanding", source)
        mapping = source.index("understanding_by_event = assess_compatibility_article_understanding(")
        loop = source.index("for event in semantic_result.events:", mapping)
        phase6 = source.index("assessment = phase6.assess_with_auto_material(", loop)
        self.assertLess(mapping, loop)
        self.assertLess(loop, phase6)
        event_slice = source[loop:phase6]
        self.assertIn("understanding = understanding_by_event[event.event_id]", event_slice)
        self.assertNotIn("understanding = event_understanding_decision(", event_slice)

    def test_fresh_economy_police_commentary_fact_is_not_bound_by_article_level_query_label(self) -> None:
        self.assertFalse(
            _decision(
                topic=_economy(),
                subject="한겨레",
                action="경찰 역량 강화와 권한 감시 방안 마련을 촉구했다",
                evidence_text=(
                    "한겨레는 경찰이 보완수사권 논쟁에 매몰되어 정작 역량 강화와 "
                    "권한 감시 방안 마련에는 소홀했다고 지적했다."
                ),
            )
        )

    def test_fresh_psat_law_firm_experience_fact_is_not_bound_by_article_level_query_label(self) -> None:
        self.assertFalse(
            _decision(
                topic=_psat(),
                subject="전북대학교 공공인재학부",
                action="재학생 대상 로펌 체험 프로그램을 운영했다",
                evidence_text=(
                    "전북대학교 공공인재학부는 전북특별자치도지방변호사회와 공동으로 "
                    "재학생 대상 로펌 체험 프로그램을 운영했다."
                ),
            )
        )

    def test_real_bok_rate_event_remains_routable(self) -> None:
        self.assertTrue(
            _decision(
                topic=_economy(),
                subject="한국은행 금융통화위원회",
                action="기준금리를 결정했다",
                object="기준금리",
                evidence_text="한국은행 금융통화위원회는 기준금리를 결정했다.",
            )
        )

    def test_real_psat_civil_service_change_remains_routable(self) -> None:
        self.assertTrue(
            _decision(
                topic=_psat(),
                subject="인사혁신처",
                action="7급 공채 PSAT 시행 일정을 발표했다",
                evidence_text="인사혁신처는 7급 공채 PSAT 시행 일정을 발표했다.",
            )
        )


if __name__ == "__main__":
    unittest.main()
