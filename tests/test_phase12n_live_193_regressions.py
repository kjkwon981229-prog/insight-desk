from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import importlib
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact
from insight_desk.semantic.material import MaterialEventReason, MaterialEventVerdict, assess_material_event
from scripts.phase11_daily_production import event_topic_relevant, load_topics
from scripts.validate_feed_artifact import validate_html


@dataclass(frozen=True)
class _Token:
    tag: str = "VV"


class _PredicateMorphology:
    def analyze(self, text: str):
        del text
        return (_Token(),)


def _topic(topic_id: str):
    return next(
        item for item in load_topics(Path("config/topics.json"))
        if item.topic_id == topic_id
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
        evidence_id=f"evidence:193:{topic_id}",
        article_id=f"article:193:{topic_id}",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id=f"fact:193:{topic_id}",
        subject=subject,
        action=action,
        object=object_,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id=f"event:193:{topic_id}",
        topic_id=topic_id,
        fact_ids=(fact.fact_id,),
        article_ids=(span.article_id,),
    )
    return event, {fact.fact_id: fact}, {span.evidence_id: span}


def _event_relevant(
    *,
    topic_id: str,
    text: str,
    subject: str,
    action: str,
    object_: str | None = None,
) -> bool:
    event, facts, evidence = _event(
        topic_id=topic_id,
        text=text,
        subject=subject,
        action=action,
        object_=object_,
    )
    return event_topic_relevant(
        event=event,
        facts=facts,
        evidence=evidence,
        topic=_topic(topic_id),
    )


def _material(text: str, *, subject: str, action: str):
    event, facts, evidence = _event(
        topic_id="fixture",
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
        '<article class="story-row" data-event-id="event:193">'
        f'<span class="story-topic">{topic}</span>'
        f'<h3>{headline}</h3>'
        f'<p class="story-summary">{summary}</p>'
        '</article></body></html>'
    )


class Live193KboEventCentralityRegressions(unittest.TestCase):
    def test_configured_kbo_event_terms_are_loaded(self) -> None:
        self.assertIn("경기", _topic("kbo_hanwha").event_terms)
        self.assertIn("기록", _topic("kbo_hanwha").event_terms)

    def test_kbo_medical_support_agreement_is_not_baseball_event(self) -> None:
        text = "대전자생한방병원은 한화 이글스와 의료지원 업무협약을 체결했다."
        self.assertFalse(_event_relevant(
            topic_id="kbo_hanwha",
            text=text,
            subject="대전자생한방병원",
            action="의료지원 업무협약을 체결했다",
            object_="한화 이글스",
        ))

    def test_historical_kbo_medical_agreement_case_collection_is_not_baseball_event(self) -> None:
        text = (
            "자생한방병원은 2017년 한화 이글스와 의료지원 협약을 맺고, "
            "2022년 롯데 자이언츠와도 협약을 체결한 사례를 소개했다."
        )
        self.assertFalse(_event_relevant(
            topic_id="kbo_hanwha",
            text=text,
            subject="자생한방병원",
            action="의료지원 협약 사례를 소개했다",
            object_="한화 이글스와 롯데 자이언츠",
        ))

    def test_actual_hanwha_baseball_events_remain_bound(self) -> None:
        cases = (
            (
                "한화 이글스가 프로야구 홈 경기에서 LG를 5대 2로 꺾고 승리했다.",
                "한화 이글스",
                "프로야구 홈 경기에서 LG를 5대 2로 꺾고 승리했다",
            ),
            (
                "한화 이글스 노시환이 8회 결승 홈런을 기록했다.",
                "한화 이글스 노시환",
                "8회 결승 홈런을 기록했다",
            ),
            (
                "한화 이글스 문현빈이 햄스트링 부상으로 엔트리에서 제외됐다.",
                "한화 이글스 문현빈",
                "햄스트링 부상으로 엔트리에서 제외됐다",
            ),
            (
                "한화 이글스가 LG전에 문동주를 선발투수로 예고했다.",
                "한화 이글스",
                "LG전에 문동주를 선발투수로 예고했다",
            ),
            (
                "한화 이글스 김서현이 1이닝 무실점을 기록했다.",
                "한화 이글스 김서현",
                "1이닝 무실점을 기록했다",
            ),
        )
        for text, subject, action in cases:
            with self.subTest(text=text):
                self.assertTrue(_event_relevant(
                    topic_id="kbo_hanwha",
                    text=text,
                    subject=subject,
                    action=action,
                ))


class Live193VisibleStandaloneRegressions(unittest.TestCase):
    def test_actual_subjectless_generated_kbo_stat_fails_visible_contract(self) -> None:
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_CONTEXT_DEPENDENT_SUMMARY"):
            validate_html(_story_html(
                topic="KBO·한화 이글스",
                headline="퓨처스리그 23일 한화전 기록",
                summary="23일 열린 퓨처스리그 한화전에서 3타수 1안타 1득점을 기록했다.",
            ))

    def test_shared_visible_contract_identifies_actual_subjectless_stat(self) -> None:
        visible_quality = importlib.import_module("insight_desk.feed_quality")
        issues = visible_quality.visible_story_issues(
            topic="KBO·한화 이글스",
            headline="퓨처스리그 23일 한화전 기록",
            summary="23일 열린 퓨처스리그 한화전에서 3타수 1안타 1득점을 기록했다.",
        )
        self.assertIn(
            visible_quality.VisibleStoryIssue.CONTEXT_DEPENDENT_SUMMARY,
            issues,
        )

    def test_item_local_visible_gate_precedes_published_slot_consumption(self) -> None:
        source = Path("scripts/phase11_daily_production.py").read_text(encoding="utf-8")
        guard = source.index("visible_story_issues(")
        append = source.index("published.append(")
        increment = source.index('stats["published_entries"] += 1')
        self.assertLess(guard, append)
        self.assertLess(guard, increment)

    def test_subject_explicit_sports_stat_remains_standalone(self) -> None:
        report = validate_html(_story_html(
            topic="KBO·한화 이글스",
            headline="한화 김서현, 퓨처스리그 LG전 1이닝 무실점",
            summary="한화 이글스 김서현은 23일 퓨처스리그 LG전에서 1이닝 무실점을 기록했다.",
        ))
        self.assertEqual(report["status"], "PASS")


class Live193ExplanatoryStateRegressions(unittest.TestCase):
    def test_explanatory_supply_demand_state_is_not_material_event(self) -> None:
        text = "환율을 끌어내리는 힘은 수급에서 두드러지고 있다."
        assessment = _material(
            text,
            subject="환율을 끌어내리는 힘",
            action="수급에서 두드러지고 있다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,),
        )

    def test_general_explanatory_state_family_is_not_material_event(self) -> None:
        cases = (
            ("달러 약세는 환율 하락의 배경으로 작용하고 있다.", "달러 약세", "환율 하락의 배경으로 작용하고 있다"),
            ("외국인 매도는 증시 약세에 영향을 미치고 있다.", "외국인 매도", "증시 약세에 영향을 미치고 있다"),
            ("수급 불균형은 변동성 확대의 주요 요인이다.", "수급 불균형", "변동성 확대의 주요 요인이다"),
        )
        for text, subject, action in cases:
            with self.subTest(text=text):
                assessment = _material(text, subject=subject, action=action)
                self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
                self.assertEqual(
                    assessment.reasons,
                    (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,),
                )

    def test_same_explanatory_visible_summary_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY"):
            validate_html(_story_html(
                topic="경제·투자",
                headline="환율 하락세, 수급 요인 두드러져",
                summary="환율을 끌어내리는 힘은 수급에서 두드러지고 있다.",
            ))

    def test_actual_exchange_rate_move_remains_material(self) -> None:
        assessment = _material(
            "원·달러 환율은 전 거래일보다 6.1원 내린 1386.5원에 마감했다.",
            subject="원·달러 환율",
            action="전 거래일보다 6.1원 내린 1386.5원에 마감했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_attributed_concrete_rate_forecast_remains_material(self) -> None:
        assessment = _material(
            "BNP파리바는 한국은행이 기준금리를 동결할 것으로 내다봤다.",
            subject="BNP파리바",
            action="한국은행이 기준금리를 동결할 것으로 내다봤다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_actual_kpop_release_event_remains_material(self) -> None:
        assessment = _material(
            "튜이드는 첫 EP 앨범을 발매하고 데뷔 쇼케이스를 개최했다.",
            subject="튜이드",
            action="첫 EP 앨범을 발매하고 데뷔 쇼케이스를 개최했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)


if __name__ == "__main__":
    unittest.main()
