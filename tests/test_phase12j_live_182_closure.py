from __future__ import annotations

import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact
from insight_desk.generation import GenerationRequest
from insight_desk.generation_pipeline import ExtractiveFallbackGenerator, ExtractiveFallbackUnavailable
from scripts.phase11_daily_production import (
    TopicConfig,
    _visible_topic_headline_bound,
    event_topic_relevant,
)
from scripts.validate_feed_artifact import validate_html


def _topic() -> TopicConfig:
    return TopicConfig(
        topic_id="kbo_hanwha",
        name="KBO·한화 이글스",
        priority=65,
        candidate_budget=36,
        selection_cap=3,
        intent_anchors=("한화 이글스", "한화", "KBO", "프로야구", "홈런", "경기"),
        required_intent_terms=("한화", "한화 이글스"),
        news_queries=("한화 이글스",),
        event_terms=("경기", "결과", "승리", "패배", "순위", "선발", "부상", "홈런", "기록"),
    )


def _event(text: str, *, subject: str, action: str, object_: str | None = None):
    span = EvidenceSpan(
        evidence_id="ev:182",
        article_id="article:182",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id="fact:182",
        subject=subject,
        action=action,
        object=object_,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:182",
        topic_id="kbo_hanwha",
        fact_ids=(fact.fact_id,),
        article_ids=(span.article_id,),
    )
    return event, {fact.fact_id: fact}, {span.evidence_id: span}


def _story_html(*, headline: str, summary: str) -> str:
    return (
        '<!doctype html><html><body>'
        '<article id="story-1" class="story-row" data-event-id="event:182">'
        '<div class="story-main">'
        '<div class="story-meta"><span class="story-topic">KBO·한화 이글스</span></div>'
        f'<h3>{headline}</h3>'
        f'<p class="story-summary">{summary}</p>'
        '</div></article></body></html>'
    )


class Live182TopicCentralityTests(unittest.TestCase):
    def test_hanwha_previous_game_reference_is_not_a_hanwha_event(self) -> None:
        text = "지난 19일 대전 한화 이글스전 이후 4경기 만에 홈런이 나왔다."
        event, facts, evidence = _event(
            text,
            subject="홈런",
            action="지난 19일 대전 한화 이글스전 이후 4경기 만에 홈런이 나왔다",
        )
        self.assertFalse(
            event_topic_relevant(event=event, facts=facts, evidence=evidence, topic=_topic())
        )

    def test_entertainment_hanwha_victory_fairy_is_not_a_kbo_event(self) -> None:
        text = (
            "그룹 코르티스 멤버 성현이 한화 이글스의 승리 요정을 목표로 한다고 "
            "한화 이글스 공식 계정이 밝혔다."
        )
        event, facts, evidence = _event(
            text,
            subject="그룹 코르티스 멤버 성현",
            action="한화 이글스의 승리 요정을 목표로 한다고 한화 이글스 공식 계정이 밝혔다",
        )
        self.assertFalse(
            event_topic_relevant(event=event, facts=facts, evidence=evidence, topic=_topic())
        )

    def test_explicit_hanwha_player_result_remains_relevant(self) -> None:
        text = "한화 이글스 김서현이 23일 LG전에서 1이닝 2피안타 무실점을 기록했다."
        event, facts, evidence = _event(
            text,
            subject="김서현",
            action="23일 LG전에서 1이닝 2피안타 무실점을 기록했다",
        )
        self.assertTrue(
            event_topic_relevant(event=event, facts=facts, evidence=evidence, topic=_topic())
        )

    def test_visible_hanwha_scope_is_item_local_before_final_validator(self) -> None:
        topic = _topic()
        self.assertFalse(_visible_topic_headline_bound(topic, "4경기 만의 홈런 기록"))
        self.assertTrue(
            _visible_topic_headline_bound(topic, "프로야구 한화 이글스 연패로 가을 야구 멀어져")
        )

    def test_entertainment_hanwha_crossover_fails_final_product_gate(self) -> None:
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_TOPIC_BINDING"):
            validate_html(
                _story_html(
                    headline="그룹 코르티스 멤버 성현, 한화 이글스 승리 요정 정조준",
                    summary=(
                        "그룹 코르티스 멤버 성현이 한화 이글스의 승리 요정을 목표로 한다고 "
                        "한화 이글스 공식 계정이 밝혔다."
                    ),
                )
            )


class Live182FallbackHeadlineTests(unittest.TestCase):
    def test_contextless_first_line_without_fact_subject_is_rejected(self) -> None:
        first = (
            "초고성능 서버 가동을 위해 고밀도 전력을 안정적으로 공급해야 하지만, "
            "구조상 간섭과 한계가 있는 기존 케이블 방식만으로는 이를 소화하기 어렵다."
        )
        second = "AI 데이터센터는 초고성능 서버 가동을 위해 고밀도 전력을 안정적으로 공급해야 한다."
        text = first + "\n" + second
        span = EvidenceSpan(
            evidence_id="ev:ai182",
            article_id="article:ai182",
            field=EvidenceField.BODY,
            start=0,
            end=len(text),
            text=text,
        )
        fact = EventFact(
            fact_id="fact:ai182",
            subject="AI 데이터센터",
            action="초고성능 서버 가동을 위해 고밀도 전력을 안정적으로 공급해야 한다",
            evidence_ids=(span.evidence_id,),
        )
        event = CandidateEvent(
            event_id="event:ai182",
            topic_id="ai_tech",
            fact_ids=(fact.fact_id,),
            article_ids=(span.article_id,),
        )
        request = GenerationRequest(
            event=event,
            facts={fact.fact_id: fact},
            evidence={span.evidence_id: span},
        )
        with self.assertRaises(ExtractiveFallbackUnavailable):
            ExtractiveFallbackGenerator().generate(request)


if __name__ == "__main__":
    unittest.main()
