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
        evidence_id="evidence:212",
        article_id="article:212",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id="fact:212",
        subject=subject,
        action=action,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:212",
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
        '<article class="story-row" data-event-id="event:212">'
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


class Live212OngoingOperationalStateRegressions(unittest.TestCase):
    _LIVE_HEADLINE = "방사선 모니터링 로봇 등 활용"
    _LIVE_SUMMARY = (
        "24일 한수원에 따르면 해수배관 점검로봇과 IRWST 수중점검로봇, "
        "방사선 모니터링 로봇 등이 원전 현장에서 활용되고 있다."
    )

    def test_live_existing_robot_use_is_not_material_event(self) -> None:
        assessment = _material(
            self._LIVE_SUMMARY,
            subject=(
                "해수배관 점검로봇과 IRWST 수중점검로봇, "
                "방사선 모니터링 로봇 등"
            ),
            action="원전 현장에서 활용되고 있다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,),
        )

    def test_live_existing_robot_use_fails_shared_visible_contract(self) -> None:
        values = _issue_values(
            topic="AI·테크",
            headline=self._LIVE_HEADLINE,
            summary=self._LIVE_SUMMARY,
        )
        self.assertIn("FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY", values)

    def test_live_existing_robot_use_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY",
        ):
            validate_html(_story_html(
                topic="AI·테크",
                headline=self._LIVE_HEADLINE,
                summary=self._LIVE_SUMMARY,
            ))

    def test_new_robot_deployment_remains_material(self) -> None:
        assessment = _material(
            "한수원은 24일 방사선 모니터링 로봇 4대를 고리 1호기 해체 현장에 새로 투입했다.",
            subject="한수원",
            action=(
                "24일 방사선 모니터링 로봇 4대를 고리 1호기 해체 현장에 "
                "새로 투입했다"
            ),
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_new_robot_deployment_remains_visible(self) -> None:
        self.assertFalse(_issue_values(
            topic="AI·테크",
            headline="한수원, 고리 1호기에 방사선 모니터링 로봇 4대 투입",
            summary=(
                "한수원은 24일 방사선 모니터링 로봇 4대를 고리 1호기 "
                "해체 현장에 새로 투입했다."
            ),
        ))


class Live212CountedInstitutionalReferenceRegressions(unittest.TestCase):
    _LIVE_HEADLINE = "로봇 국내 적용 범위 확대 계획"
    _LIVE_SUMMARY = (
        "양사는 리테일 공간 작업 자동화, 의류 폴딩, 공장 운영 등 구체적 "
        "작업을 중심으로 로봇의 국내 적용 범위를 넓혀갈 방침이다."
    )

    def test_live_counted_institutional_reference_fails_shared_contract(self) -> None:
        values = _issue_values(
            topic="AI·테크",
            headline=self._LIVE_HEADLINE,
            summary=self._LIVE_SUMMARY,
        )
        self.assertIn("FEED_QUALITY_CONTEXT_DEPENDENT_SUMMARY", values)

    def test_live_counted_institutional_reference_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_CONTEXT_DEPENDENT_SUMMARY"):
            validate_html(_story_html(
                topic="AI·테크",
                headline=self._LIVE_HEADLINE,
                summary=self._LIVE_SUMMARY,
            ))

    def test_generic_bilateral_reference_also_fails_shared_contract(self) -> None:
        values = _issue_values(
            topic="AI·테크",
            headline="로봇 소프트웨어 공동 개발 추진",
            summary="양측은 실환경 로봇 소프트웨어 공동 개발을 추진한다.",
        )
        self.assertIn("FEED_QUALITY_CONTEXT_DEPENDENT_SUMMARY", values)

    def test_named_companies_plan_remains_visible(self) -> None:
        self.assertFalse(_issue_values(
            topic="AI·테크",
            headline="엑스와이지·갤럭시아, 로봇 국내 적용 범위 확대 계획",
            summary=(
                "엑스와이지와 갤럭시아는 리테일 자동화와 공장 운영을 중심으로 "
                "로봇의 국내 적용 범위를 확대할 계획이다."
            ),
        ))


class Live212PublicationRetrospectiveRegressions(unittest.TestCase):
    _LIVE_HEADLINE = "백투백 금리 인상 및 최종 전망치 반영에 대한 시장 평가"
    _SOURCE_SENTENCE = (
        "본지는 최근 1년 이내 구간에 백투백 인상과 최종 기준금리 전망이 "
        "이미 반영됐다는 시장 평가를 전한 바 있다."
    )
    _LIVE_SUMMARY = (
        "본지는 최근 1년 이내 구간에 백투백 인상과 최종 기준금리 전망이 "
        "이미 반영됐다는 시장의 평가를 전했다."
    )

    def test_live_prior_coverage_is_not_material_event(self) -> None:
        assessment = _material(
            self._SOURCE_SENTENCE,
            subject="본지",
            action=(
                "최근 1년 이내 구간에 백투백 인상과 최종 기준금리 전망이 "
                "이미 반영됐다는 시장 평가를 전한 바 있다"
            ),
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,),
        )

    def test_live_prior_coverage_fails_shared_visible_contract(self) -> None:
        values = _issue_values(
            topic="경제·투자",
            headline=self._LIVE_HEADLINE,
            summary=self._LIVE_SUMMARY,
        )
        self.assertIn("FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY", values)

    def test_live_prior_coverage_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY",
        ):
            validate_html(_story_html(
                topic="경제·투자",
                headline=self._LIVE_HEADLINE,
                summary=self._LIVE_SUMMARY,
            ))

    def test_current_outlet_reporting_event_remains_material(self) -> None:
        assessment = _material(
            "본지는 24일 한국은행이 기준금리를 3.0%로 동결했다고 보도했다.",
            subject="본지",
            action="24일 한국은행이 기준금리를 3.0%로 동결했다고 보도했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_attributed_concrete_rate_forecast_remains_material(self) -> None:
        assessment = _material(
            "BNP파리바는 한국은행이 기준금리를 동결할 것으로 내다봤다.",
            subject="BNP파리바",
            action="한국은행이 기준금리를 동결할 것으로 내다봤다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_actual_exchange_rate_move_remains_material(self) -> None:
        assessment = _material(
            "원·달러 환율이 6.1원 내린 1386.5원에 마감했다.",
            subject="원·달러 환율",
            action="6.1원 내린 1386.5원에 마감했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_actual_kpop_release_and_showcase_remain_material(self) -> None:
        assessment = _material(
            "튜이드는 첫 EP를 발매하고 데뷔 쇼케이스를 개최했다.",
            subject="튜이드",
            action="첫 EP를 발매하고 데뷔 쇼케이스를 개최했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_named_current_sports_stat_remains_visible(self) -> None:
        self.assertFalse(_issue_values(
            topic="KBO·한화 이글스",
            headline="한화, 최근 10경기 2승 8패 기록",
            summary="한화는 최근 치른 10경기에서 2승 8패의 성적을 거두었다.",
        ))


if __name__ == "__main__":
    unittest.main()
