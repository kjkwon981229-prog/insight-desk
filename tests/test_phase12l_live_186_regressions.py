from __future__ import annotations

from dataclasses import dataclass
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact
from insight_desk.semantic.material import MaterialEventReason, MaterialEventVerdict, assess_material_event
from scripts.phase11_daily_production import TopicConfig, _visible_topic_headline_bound, event_topic_relevant
from scripts.validate_feed_artifact import validate_html


@dataclass(frozen=True)
class _Token:
    tag: str = "VV"


class _PredicateMorphology:
    def analyze(self, text: str):
        del text
        return (_Token(),)


def _topic(
    topic_id: str,
    name: str,
    *,
    anchors: tuple[str, ...],
    required: tuple[str, ...],
) -> TopicConfig:
    return TopicConfig(
        topic_id=topic_id,
        name=name,
        priority=1,
        candidate_budget=8,
        selection_cap=3,
        intent_anchors=anchors,
        required_intent_terms=required,
        news_queries=("fixture",),
    )


def _event(
    *,
    topic_id: str,
    text: str,
    subject: str,
    action: str,
    object_: str | None = None,
):
    span = EvidenceSpan(
        evidence_id=f"evidence:{topic_id}",
        article_id=f"article:{topic_id}",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id=f"fact:{topic_id}",
        subject=subject,
        action=action,
        object=object_,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id=f"event:{topic_id}",
        topic_id=topic_id,
        fact_ids=(fact.fact_id,),
        article_ids=(span.article_id,),
    )
    return event, {fact.fact_id: fact}, {span.evidence_id: span}


def _material(text: str, *, subject: str, action: str):
    event, facts, evidence = _event(
        topic_id="material",
        text=text,
        subject=subject,
        action=action,
    )
    return assess_material_event(
        event,
        facts=facts,
        evidence=evidence,
        morphology=_PredicateMorphology(),
    )


def _story_html(*, topic: str, headline: str, summary: str) -> str:
    return (
        '<!doctype html><html><body>'
        '<article class="story-row" data-event-id="event:186">'
        '<div class="story-main">'
        f'<span class="story-topic">{topic}</span>'
        f'<h3>{headline}</h3>'
        f'<p class="story-summary">{summary}</p>'
        '</div></article></body></html>'
    )


class Live186AiCentralityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.topic = _topic(
            "ai_tech",
            "AI·테크",
            anchors=("인공지능", "AI", "데이터센터"),
            required=("인공지능 산업", "AI 활용", "데이터센터"),
        )

    def test_incidental_ai_context_does_not_bind_fiscal_fund_event(self) -> None:
        text = "정부는 인공지능 산업 등에 투자할 미래대응기금의 구체적인 방안을 발표했다."
        event, facts, evidence = _event(
            topic_id="ai_tech",
            text=text,
            subject="정부",
            action="미래대응기금의 구체적인 방안을 발표했다",
        )
        self.assertFalse(
            event_topic_relevant(
                event=event,
                facts=facts,
                evidence=evidence,
                topic=self.topic,
            )
        )

    def test_ai_term_inside_fact_surface_remains_bound(self) -> None:
        text = "서울중기청장은 전통시장 소상공인의 디지털·AI 활용을 지속적으로 지원하겠다고 밝혔다."
        event, facts, evidence = _event(
            topic_id="ai_tech",
            text=text,
            subject="서울중기청장",
            action="전통시장 소상공인의 디지털·AI 활용을 지속적으로 지원하겠다고 밝혔다",
        )
        self.assertTrue(
            event_topic_relevant(
                event=event,
                facts=facts,
                evidence=evidence,
                topic=self.topic,
            )
        )


class Live186MaterialityTests(unittest.TestCase):
    def test_explicit_2017_event_is_stale_even_inside_fresh_article(self) -> None:
        assessment = _material(
            "2017년 대전자생한방병원이 한화이글스와 의료지원 협약을 체결했다.",
            subject="대전자생한방병원",
            action="한화이글스와 의료지원 협약을 체결했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(assessment.reasons, (MaterialEventReason.STALE_EXPLICIT_PAST_EVENT,))

    def test_historical_modifier_does_not_block_current_event(self) -> None:
        assessment = _material(
            "2017년 설립한 네오팩토리가 AI 데이터센터 구축 사업을 수주했다.",
            subject="네오팩토리",
            action="AI 데이터센터 구축 사업을 수주했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_past_year_at_start_of_action_is_stale(self) -> None:
        assessment = _material(
            "네오팩토리는 2017년 한화와 의료지원 협약을 체결했다.",
            subject="네오팩토리",
            action="2017년 한화와 의료지원 협약을 체결했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(assessment.reasons, (MaterialEventReason.STALE_EXPLICIT_PAST_EVENT,))

    def test_interpretive_forecast_ending_is_not_material_event(self) -> None:
        assessment = _material(
            "경제의 기초체력이 강화되면서 기준금리 상방 압력 쪽에 무게가 실릴 것으로 풀이된다.",
            subject="경제의 기초체력",
            action="강화되면서 기준금리 상방 압력 쪽에 무게가 실릴 것으로 풀이된다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(assessment.reasons, (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,))


class Live186FinalValidatorParityTests(unittest.TestCase):
    def test_kpop_scope_matches_existing_final_contract_item_locally(self) -> None:
        kpop = _topic(
            "kpop",
            "엔터·음악·K-POP",
            anchors=("K-POP", "가수", "콘서트"),
            required=("가수", "콘서트"),
        )
        self.assertFalse(_visible_topic_headline_bound(kpop, "제작총괄의 첫 연출작 ‘고스트밴드’ 공개"))
        self.assertTrue(_visible_topic_headline_bound(kpop, "삼익악기, 백화점 방문객 대상 소규모 콘서트 소개"))

    def test_stale_2017_visible_summary_fails_backstop(self) -> None:
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_STALE_DATED_CONTEXT"):
            validate_html(
                _story_html(
                    topic="KBO·한화 이글스",
                    headline="대전자생한방병원·한화이글스 의료지원 협약 체결",
                    summary="2017년 대전자생한방병원이 한화이글스와 의료지원 협약을 체결하고 선수들을 지원했다.",
                )
            )

    def test_interpretive_forecast_visible_summary_fails_backstop(self) -> None:
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY"):
            validate_html(
                _story_html(
                    topic="경제·투자",
                    headline="기준금리 상방 압력에 무게 실릴 전망",
                    summary="경제의 기초체력이 강화된다는 측면에서 기준금리 상방 압력 쪽에 무게가 실릴 것으로 풀이된다.",
                )
            )


if __name__ == "__main__":
    unittest.main()
