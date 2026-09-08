from __future__ import annotations

from dataclasses import dataclass
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact
from insight_desk.feed_quality import visible_story_issues
from insight_desk.semantic.material import (
    MaterialEventReason,
    MaterialEventVerdict,
    assess_material_event,
)
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
        evidence_id="evidence:221",
        article_id="article:221",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id="fact:221",
        subject=subject,
        action=action,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:221",
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


def _story_html(*, topic: str, headline: str, summary: str) -> str:
    return (
        "<!doctype html><html><body>"
        '<article class="story-row" data-event-id="event:221">'
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


class Live221EnduringRequirementRegressions(unittest.TestCase):
    _LIVE_HEADLINE = "정비 현장 책임 지속"
    _LIVE_SUMMARY = (
        "학교 측은 자동화와 인공지능 기술이 발전하더라도 정비 현장에서는 "
        "전문적인 판단과 점검, 이에 따른 책임이 계속 요구된다고 설명했다"
    )

    def test_live_enduring_requirement_is_not_material_event(self) -> None:
        assessment = _material(
            self._LIVE_SUMMARY,
            subject="학교 측",
            action=(
                "자동화와 인공지능 기술이 발전하더라도 정비 현장에서는 전문적인 "
                "판단과 점검, 이에 따른 책임이 계속 요구된다고 설명했다"
            ),
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,),
        )

    def test_live_enduring_requirement_fails_shared_visible_contract(self) -> None:
        values = _issue_values(
            topic="AI·테크",
            headline=self._LIVE_HEADLINE,
            summary=self._LIVE_SUMMARY,
        )
        self.assertIn("FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY", values)

    def test_live_enduring_requirement_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY",
        ):
            validate_html(_story_html(
                topic="AI·테크",
                headline=self._LIVE_HEADLINE,
                summary=self._LIVE_SUMMARY,
            ))

    def test_actual_course_transfer_remains_material(self) -> None:
        assessment = _material(
            "인하항공은 2026학년도 2학기 항공정비사 면허과정에 총 13명이 편입했다고 24일 밝혔다.",
            subject="인하항공",
            action="2026학년도 2학기 항공정비사 면허과정에 총 13명이 편입했다고 24일 밝혔다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_current_ai_safety_assignment_announcement_remains_material(self) -> None:
        assessment = _material(
            "국토부는 24일 항공정비 현장에 AI 안전점검 책임자를 의무 배치한다고 발표했다.",
            subject="국토부",
            action="24일 항공정비 현장에 AI 안전점검 책임자를 의무 배치한다고 발표했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_named_continuing_operation_decision_remains_material(self) -> None:
        assessment = _material(
            "학교는 내년에도 AI 정비 실습장을 계속 운영하기로 결정했다.",
            subject="학교",
            action="내년에도 AI 정비 실습장을 계속 운영하기로 결정했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)


class Live221GenericEvaluativeClassificationRegressions(unittest.TestCase):
    _LIVE_HEADLINE = "기준금리 결정 전 기대 변화와 기관 수급에 민감하게 움직이는 구간으로 꼽힌다"
    _LIVE_SUMMARY = (
        "단기 IRS는 기준금리 결정 전 기대 변화와 기관 수급에 민감하게 "
        "움직이는 구간으로 꼽힌다."
    )

    def test_live_generic_irs_characteristic_is_not_material_event(self) -> None:
        assessment = _material(
            self._LIVE_SUMMARY,
            subject="단기 IRS",
            action="기준금리 결정 전 기대 변화와 기관 수급에 민감하게 움직이는 구간으로 꼽힌다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,),
        )

    def test_live_generic_irs_characteristic_fails_shared_visible_contract(self) -> None:
        values = _issue_values(
            topic="경제·투자",
            headline=self._LIVE_HEADLINE,
            summary=self._LIVE_SUMMARY,
        )
        self.assertIn("FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY", values)

    def test_live_generic_irs_characteristic_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY",
        ):
            validate_html(_story_html(
                topic="경제·투자",
                headline=self._LIVE_HEADLINE,
                summary=self._LIVE_SUMMARY,
            ))

    def test_actual_irs_move_remains_material(self) -> None:
        assessment = _material(
            "24일 1년 IRS 금리는 전 거래일보다 3.50bp 내린 3.4275%를 기록했다.",
            subject="1년 IRS 금리",
            action="전 거래일보다 3.50bp 내린 3.4275%를 기록했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_attributed_concrete_rate_forecast_remains_material(self) -> None:
        assessment = _material(
            "BNP파리바는 한국은행이 기준금리를 동결할 것으로 내다봤다.",
            subject="BNP파리바",
            action="한국은행이 기준금리를 동결할 것으로 내다봤다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_actual_long_bond_yield_move_remains_visible(self) -> None:
        self.assertFalse(_issue_values(
            topic="경제·투자",
            headline="미국 30년 만기 국채 금리 5.3% 도달",
            summary="미국 30년 만기 국채 금리가 5.3%를 기록했다.",
        ))


if __name__ == "__main__":
    unittest.main()
