from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact
from insight_desk.feed_quality import (
    VisibleStoryIssue,
    non_event_analytical_text,
    visible_metadata_text,
    visible_story_issues,
)
from insight_desk.semantic.material import (
    MaterialEventReason,
    MaterialEventVerdict,
    assess_material_event,
)
from scripts.phase11_daily_production import event_topic_relevant, load_topics


@dataclass(frozen=True)
class _Token:
    tag: str = "VV"


class _PredicateMorphology:
    def analyze(self, text: str):
        del text
        return (_Token(),)


def _material(text: str, *, subject: str, action: str):
    span = EvidenceSpan(
        evidence_id="evidence:230",
        article_id="article:230",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id="fact:230",
        subject=subject,
        action=action,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:230",
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


def _topic(topic_id: str):
    return next(
        item
        for item in load_topics(Path("config/topics.json"))
        if item.topic_id == topic_id
    )


def _kbo_relevant(*, subject: str, action: str, object_text: str | None = None) -> bool:
    text = " ".join(value for value in (subject, action, object_text or "") if value)
    span = EvidenceSpan(
        evidence_id="evidence:kbo-230",
        article_id="article:kbo-230",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id="fact:kbo-230",
        subject=subject,
        action=action,
        object=object_text,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:kbo-230",
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


class Daily230NegativeRegressions(unittest.TestCase):
    def test_rate_definition_card_is_non_event(self) -> None:
        text = (
            "기준금리는 한국은행이 금융기관과 거래할 때 기준이 되는 금리로, "
            "우리나라 전체 금리의 방향을 결정하는 역할을 한다."
        )
        self.assertTrue(non_event_analytical_text(text))
        assessment = _material(
            text,
            subject="기준금리",
            action=(
                "한국은행이 금융기관과 거래할 때 기준이 되는 금리로, "
                "우리나라 전체 금리의 방향을 결정하는 역할을 한다"
            ),
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,),
        )
        issues = visible_story_issues(
            topic="경제·투자",
            headline="기준금리, 한국은행 거래 기준",
            summary=text,
        )
        self.assertIn(VisibleStoryIssue.NON_EVENT_ANALYTICAL_SUMMARY, issues)

    def test_kbo_provider_credit_is_metadata_not_news_text(self) -> None:
        self.assertTrue(visible_metadata_text("KBO 사무국 제공"))
        assessment = _material(
            "KBO 사무국 제공",
            subject="KBO 사무국",
            action="제공",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)

    def test_lg_centered_win_and_rank_event_is_not_hanwha_central(self) -> None:
        self.assertFalse(
            _kbo_relevant(
                subject="LG",
                action=(
                    "지난 23일 대전 한화 이글스전에서 12-3으로 승리하고 "
                    "리그 4위에서 3위로 순위가 상승했다"
                ),
                object_text="한화 이글스",
            )
        )


class Daily230PositiveBoundaries(unittest.TestCase):
    def test_actual_rate_decision_and_attributed_forecast_remain_events(self) -> None:
        decision = _material(
            "한국은행은 기준금리를 2.75%에서 3.00%로 인상했다.",
            subject="한국은행",
            action="기준금리를 2.75%에서 3.00%로 인상했다",
        )
        forecast = _material(
            "BNP파리바는 한국은행이 기준금리를 동결할 것으로 내다봤다.",
            subject="BNP파리바",
            action="한국은행이 기준금리를 동결할 것으로 내다봤다",
        )
        self.assertIs(decision.verdict, MaterialEventVerdict.MATERIAL)
        self.assertIs(forecast.verdict, MaterialEventVerdict.MATERIAL)

    def test_kbo_office_as_real_actor_is_not_metadata(self) -> None:
        text = "KBO 사무국은 정규시즌 일정을 발표했다."
        self.assertFalse(visible_metadata_text(text))
        assessment = _material(
            text,
            subject="KBO 사무국",
            action="정규시즌 일정을 발표했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_hanwha_subject_events_remain_topic_central(self) -> None:
        cases = (
            "LG를 5-3으로 꺾고 승리했다",
            "LG에 2-4로 패했다",
            "내야수 노시환의 부상을 발표했다",
            "문동주를 25일 선발투수로 예고했다",
            "시즌 60승을 기록했다",
        )
        for action in cases:
            with self.subTest(action=action):
                self.assertTrue(
                    _kbo_relevant(
                        subject="한화 이글스",
                        action=action,
                    )
                )


if __name__ == "__main__":
    unittest.main()
