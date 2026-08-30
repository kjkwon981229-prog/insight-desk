from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact
from insight_desk.feed_quality import visible_story_issues
from insight_desk.semantic.material import (
    MaterialEventReason,
    MaterialEventVerdict,
    assess_material_event,
)
from scripts.phase11_daily_production import TopicConfig, event_topic_relevant, load_topics
from scripts.validate_feed_artifact import validate_html


@dataclass(frozen=True)
class _Token:
    tag: str = "VV"


class _PredicateMorphology:
    def analyze(self, text: str):
        del text
        return (_Token(),)


def _material(text: str, *, subject: str, action: str):
    span = EvidenceSpan(
        evidence_id="evidence:206:material",
        article_id="article:206:material",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id="fact:206:material",
        subject=subject,
        action=action,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:206:material",
        topic_id="fixture",
        fact_ids=(fact.fact_id,),
        article_ids=(span.article_id,),
    )
    return assess_material_event(
        event,
        facts={fact.fact_id: fact},
        evidence={span.evidence_id: span},
        morphology=_PredicateMorphology(),
    )


def _topic(topic_id: str) -> TopicConfig:
    return next(
        topic
        for topic in load_topics(Path("config/topics.json"))
        if topic.topic_id == topic_id
    )


def _kbo_relevant(
    *,
    text: str,
    subject: str,
    action: str,
    object_: str | None = None,
) -> bool:
    span = EvidenceSpan(
        evidence_id="evidence:206:kbo",
        article_id="article:206:kbo",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id="fact:206:kbo",
        subject=subject,
        action=action,
        object=object_,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:206:kbo",
        topic_id="kbo_hanwha",
        fact_ids=(fact.fact_id,),
        article_ids=(span.article_id,),
    )
    return event_topic_relevant(
        event=event,
        facts={fact.fact_id: fact},
        evidence={span.evidence_id: span},
        topic=_topic("kbo_hanwha"),
    )


def _story_html(*, topic: str, headline: str, summary: str) -> str:
    return (
        "<!doctype html><html><body>"
        '<article class="story-row" data-event-id="event:206">'
        f'<span class="story-topic">{topic}</span>'
        f"<h3>{headline}</h3>"
        f'<p class="story-summary">{summary}</p>'
        "</article></body></html>"
    )


def _issue_values(*, topic: str, headline: str, summary: str) -> set[str]:
    return {
        issue.value
        for issue in visible_story_issues(
            topic=topic,
            headline=headline,
            summary=summary,
        )
    }


class Live206EmbeddedPastEventRegressions(unittest.TestCase):
    _LIVE_SUMMARY = (
        "도시바는 가전과 반도체 중심의 사업 구조를 발전 및 인프라 중심으로 "
        "개편하고자 2006년 54억달러(약 7조 4500억원)를 투자해 "
        "웨스팅하우스를 인수했다."
    )
    _LIVE_ACTION = (
        "가전과 반도체 중심의 사업 구조를 발전 및 인프라 중심으로 개편하고자 "
        "2006년 54억달러(약 7조 4500억원)를 투자해 웨스팅하우스를 인수했다"
    )

    def test_live_2006_acquisition_is_stale_material_event(self) -> None:
        assessment = _material(
            self._LIVE_SUMMARY,
            subject="도시바",
            action=self._LIVE_ACTION,
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.STALE_EXPLICIT_PAST_EVENT,),
        )

    def test_embedded_past_year_fails_shared_visible_contract(self) -> None:
        values = _issue_values(
            topic="AI·테크",
            headline="도시바의 웨스팅하우스 인수",
            summary=self._LIVE_SUMMARY,
        )
        self.assertIn("FEED_QUALITY_STALE_DATED_CONTEXT", values)

    def test_embedded_past_year_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_STALE_DATED_CONTEXT"):
            validate_html(_story_html(
                topic="AI·테크",
                headline="도시바의 웨스팅하우스 인수",
                summary=self._LIVE_SUMMARY,
            ))

    def test_historical_modifier_before_current_event_remains_material(self) -> None:
        assessment = _material(
            "2017년 설립한 네오팩토리가 올해 AI 데이터센터 구축 사업을 수주했다.",
            subject="네오팩토리",
            action="올해 AI 데이터센터 구축 사업을 수주했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_since_past_year_current_contract_remains_visible(self) -> None:
        self.assertFalse(_issue_values(
            topic="AI·테크",
            headline="웨스팅하우스, 올해 신규 원전 계약 체결",
            summary=(
                "웨스팅하우스는 2006년 이후 처음으로 올해 신규 원전 계약을 체결했다."
            ),
        ))


class Live206MixedEventSummaryRegressions(unittest.TestCase):
    _LIVE_SUMMARY = (
        "미국 30년 만기 국채 금리가 5.3%에 도달했다. 이는 미국 연방준비제도"
        "(Fed·연준)의 선제지침 제거와 소통 방식 전환 가운데 나타난 현상으로, "
        "한국은행은 외환 및 채권 시장의 차입 비용 상승 압박 경로를 점검하고 있다."
    )

    def test_live_treasury_and_bok_summary_fails_shared_contract(self) -> None:
        values = _issue_values(
            topic="경제·투자",
            headline="미국 30년 만기 국채 금리 5.3% 도달",
            summary=self._LIVE_SUMMARY,
        )
        self.assertIn("FEED_QUALITY_MIXED_EVENT_SUMMARY", values)

    def test_live_treasury_and_bok_summary_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_MIXED_EVENT_SUMMARY"):
            validate_html(_story_html(
                topic="경제·투자",
                headline="미국 30년 만기 국채 금리 5.3% 도달",
                summary=self._LIVE_SUMMARY,
            ))

    def test_same_subject_yield_elaboration_remains_visible(self) -> None:
        self.assertFalse(_issue_values(
            topic="경제·투자",
            headline="미국 30년 만기 국채 금리 5.3% 도달",
            summary=(
                "미국 30년 만기 국채 금리가 5.3%에 도달했다. "
                "이는 2007년 이후 19년 만의 최고 수준이다."
            ),
        ))

    def test_actual_bok_review_meeting_remains_material(self) -> None:
        assessment = _material(
            "한국은행은 외환시장 리스크 점검회의를 개최했다.",
            subject="한국은행",
            action="외환시장 리스크 점검회의를 개최했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)


class Live206SubjectlessFundingRegressions(unittest.TestCase):
    _LIVE_HEADLINE = "투자 심리 위축 속 자금 모집 완판 성공"
    _LIVE_SUMMARY = (
        "한국은행 금융통화위원회를 앞두고 크레디트물 전반의 투자 심리가 "
        "얼어붙었으나, 모집액을 웃도는 자금을 확보하며 완판에 성공했다."
    )

    def test_live_subjectless_funding_result_fails_shared_contract(self) -> None:
        values = _issue_values(
            topic="경제·투자",
            headline=self._LIVE_HEADLINE,
            summary=self._LIVE_SUMMARY,
        )
        self.assertIn("FEED_QUALITY_CONTEXT_DEPENDENT_HEADLINE", values)
        self.assertIn("FEED_QUALITY_CONTEXT_DEPENDENT_SUMMARY", values)

    def test_live_subjectless_funding_result_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_CONTEXT_DEPENDENT"):
            validate_html(_story_html(
                topic="경제·투자",
                headline=self._LIVE_HEADLINE,
                summary=self._LIVE_SUMMARY,
            ))

    def test_named_issuer_funding_result_remains_standalone(self) -> None:
        self.assertFalse(_issue_values(
            topic="경제·투자",
            headline="교보생명 신종자본증권 5000억원 완판",
            summary=(
                "교보생명은 신종자본증권 수요예측을 통해 5000억원 조달을 확정했다."
            ),
        ))


class Live206KboComparisonBindingRegressions(unittest.TestCase):
    _LIVE_TEXT = "NC는 롯데보다 4경기, 한화보다는 3경기 덜 치렀다."
    _LIVE_HEADLINE = "NC, 롯데·한화 대비 잔여 경기 현황"
    _LIVE_SUMMARY = "NC는 롯데보다 4경기, 한화보다는 3경기 적게 경기를 치렀다."

    def test_comparison_only_hanwha_reference_fails_event_binding(self) -> None:
        self.assertFalse(_kbo_relevant(
            text=self._LIVE_TEXT,
            subject="NC",
            action="롯데보다 4경기, 한화보다는 3경기 덜 치렀다",
        ))

    def test_comparison_only_hanwha_card_fails_shared_visible_binding(self) -> None:
        values = _issue_values(
            topic="KBO·한화 이글스",
            headline=self._LIVE_HEADLINE,
            summary=self._LIVE_SUMMARY,
        )
        self.assertIn("FEED_QUALITY_TOPIC_BINDING", values)

    def test_comparison_only_hanwha_card_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_TOPIC_BINDING"):
            validate_html(_story_html(
                topic="KBO·한화 이글스",
                headline=self._LIVE_HEADLINE,
                summary=self._LIVE_SUMMARY,
            ))

    def test_actual_hanwha_opponent_result_remains_bound(self) -> None:
        self.assertTrue(_kbo_relevant(
            text="NC가 한화 이글스를 5대 4로 꺾고 승리했다.",
            subject="NC",
            action="한화 이글스를 5대 4로 꺾고 승리했다",
            object_="한화 이글스",
        ))

    def test_hanwha_own_games_played_comparison_remains_bound(self) -> None:
        self.assertTrue(_kbo_relevant(
            text="한화 이글스는 NC보다 3경기 더 치렀다.",
            subject="한화 이글스",
            action="NC보다 3경기 더 치렀다",
        ))


if __name__ == "__main__":
    unittest.main()
