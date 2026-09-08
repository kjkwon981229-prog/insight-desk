from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from unittest.mock import patch
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact
from insight_desk.feed_quality import stale_day_only_context, visible_story_issues
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


class _FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        value = cls(2026, 8, 24, 11, 36, tzinfo=timezone.utc)
        return value if tz is None else value.astimezone(tz)


@contextmanager
def _at_live_218_time():
    with (
        patch("insight_desk.feed_quality.datetime", _FrozenDateTime),
        patch("insight_desk.semantic.material.datetime", _FrozenDateTime),
        patch("scripts.validate_feed_artifact.datetime", _FrozenDateTime),
    ):
        yield


def _material(text: str, *, subject: str, action: str):
    span = EvidenceSpan(
        evidence_id="evidence:218",
        article_id="article:218",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id="fact:218",
        subject=subject,
        action=action,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:218",
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
        '<article class="story-row" data-event-id="event:218">'
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


class Live218ResidualConstituentReferenceRegressions(unittest.TestCase):
    _LIVE_HEADLINE = "SK하이닉스 포함 AI 반도체 키워드 상위 종목 선정"
    _LIVE_SUMMARY = (
        "삼성전자와 SK하이닉스 외 나머지 1종목은 시가총액 상위 10종목 중 "
        "‘인공지능(AI)반도체’ 키워드 연관도 상위 종목으로 선정한다."
    )

    def test_live_parentless_remaining_constituent_is_context_dependent_material(self) -> None:
        assessment = _material(
            self._LIVE_SUMMARY,
            subject="나머지 1종목",
            action=(
                "시가총액 상위 10종목 중 ‘인공지능(AI)반도체’ 키워드 "
                "연관도 상위 종목으로 선정한다"
            ),
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.CONTEXT_DEPENDENT_FRAGMENT,),
        )

    def test_live_parentless_remaining_constituent_fails_shared_visible_contract(self) -> None:
        values = _issue_values(
            topic="AI·테크",
            headline=self._LIVE_HEADLINE,
            summary=self._LIVE_SUMMARY,
        )
        self.assertIn("FEED_QUALITY_CONTEXT_DEPENDENT_SUMMARY", values)

    def test_live_parentless_remaining_constituent_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "FEED_QUALITY_CONTEXT_DEPENDENT_SUMMARY",
        ):
            validate_html(_story_html(
                topic="AI·테크",
                headline=self._LIVE_HEADLINE,
                summary=self._LIVE_SUMMARY,
            ))

    def test_named_new_etf_listing_remains_material(self) -> None:
        assessment = _material(
            "한국투자신탁운용은 ACE 삼성전자SK하이닉스플러스채권혼합50 ETF를 25일 신규 상장한다.",
            subject="한국투자신탁운용",
            action="ACE 삼성전자SK하이닉스플러스채권혼합50 ETF를 25일 신규 상장한다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_named_etf_constituents_remain_material(self) -> None:
        assessment = _material(
            "ACE 반도체채권혼합 ETF는 삼성전자와 SK하이닉스, 삼성전기 3종목을 편입한다.",
            subject="ACE 반도체채권혼합 ETF",
            action="삼성전자와 SK하이닉스, 삼성전기 3종목을 편입한다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_named_etf_constituents_remain_visible(self) -> None:
        self.assertFalse(_issue_values(
            topic="AI·테크",
            headline="ACE 반도체채권혼합 ETF, 삼성전자·SK하이닉스·삼성전기 편입",
            summary=(
                "ACE 반도체채권혼합 ETF는 삼성전자와 SK하이닉스, "
                "삼성전기 3종목을 편입한다."
            ),
        ))


class Live218AnalyticalDependencyRegressions(unittest.TestCase):
    _LIVE_HEADLINE = "카카오AI, 에이전트 사업 성과가 목표 달성 관건"
    _LIVE_SUMMARY = (
        "카카오AI의 목표 달성 여부가 AI 에이전트 사업의 성과에 달려 있다고 분석했다."
    )

    def test_live_goal_dependency_analysis_is_not_material_event(self) -> None:
        assessment = _material(
            self._LIVE_SUMMARY,
            subject="카카오AI의 목표 달성 여부",
            action="AI 에이전트 사업의 성과에 달려 있다고 분석했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,),
        )

    def test_live_goal_dependency_analysis_fails_shared_visible_contract(self) -> None:
        values = _issue_values(
            topic="AI·테크",
            headline=self._LIVE_HEADLINE,
            summary=self._LIVE_SUMMARY,
        )
        self.assertIn("FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY", values)

    def test_live_goal_dependency_analysis_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY",
        ):
            validate_html(_story_html(
                topic="AI·테크",
                headline=self._LIVE_HEADLINE,
                summary=self._LIVE_SUMMARY,
            ))

    def test_named_target_price_cut_remains_material(self) -> None:
        assessment = _material(
            "다올투자증권은 24일 카카오 목표주가를 6만원에서 4만5000원으로 낮췄다.",
            subject="다올투자증권",
            action="24일 카카오 목표주가를 6만원에서 4만5000원으로 낮췄다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_current_named_split_decision_remains_material(self) -> None:
        assessment = _material(
            "카카오는 24일 회사를 카카오X와 카카오AI로 인적분할하기로 결의했다.",
            subject="카카오",
            action="24일 회사를 카카오X와 카카오AI로 인적분할하기로 결의했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_attributed_concrete_rate_forecast_remains_material(self) -> None:
        assessment = _material(
            "BNP파리바는 한국은행이 기준금리를 동결할 것으로 내다봤다.",
            subject="BNP파리바",
            action="한국은행이 기준금리를 동결할 것으로 내다봤다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)


class Live218BareDaySportsFreshnessRegressions(unittest.TestCase):
    _LIVE_HEADLINE = "한화전 김태군 투런 홈런 결승타"
    _LIVE_SUMMARY = (
        "김태군이 20일 한화와의 경기에서 투런 홈런을 기록하며 결승타의 주인공이 됐다."
    )

    def test_live_bare_day_old_game_is_stale_material_event(self) -> None:
        with _at_live_218_time():
            assessment = _material(
                self._LIVE_SUMMARY,
                subject="김태군",
                action="20일 한화와의 경기에서 투런 홈런을 기록하며 결승타의 주인공이 됐다",
            )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.STALE_DATED_CONTEXT,),
        )

    def test_live_bare_day_old_game_fails_shared_visible_contract(self) -> None:
        with _at_live_218_time():
            values = _issue_values(
                topic="KBO·한화 이글스",
                headline=self._LIVE_HEADLINE,
                summary=self._LIVE_SUMMARY,
            )
        self.assertIn("FEED_QUALITY_STALE_DATED_CONTEXT", values)

    def test_live_bare_day_old_game_matches_shared_stale_predicate(self) -> None:
        self.assertTrue(stale_day_only_context(
            self._LIVE_SUMMARY,
            now=_FrozenDateTime.now(timezone.utc),
        ))

    def test_live_bare_day_old_game_fails_artifact_validator(self) -> None:
        with _at_live_218_time():
            with self.assertRaisesRegex(
                ValueError,
                "FEED_QUALITY_STALE_DATED_CONTEXT",
            ):
                validate_html(_story_html(
                    topic="KBO·한화 이글스",
                    headline=self._LIVE_HEADLINE,
                    summary=self._LIVE_SUMMARY,
                ))

    def test_23rd_game_inside_72_hours_remains_material(self) -> None:
        with _at_live_218_time():
            assessment = _material(
                "LG는 23일 한화와의 경기에서 12-3으로 승리했다.",
                subject="LG",
                action="23일 한화와의 경기에서 12-3으로 승리했다",
            )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_23rd_game_inside_72_hours_remains_visible(self) -> None:
        with _at_live_218_time():
            self.assertFalse(_issue_values(
                topic="KBO·한화 이글스",
                headline="LG, 23일 한화전 12-3 승리",
                summary="LG는 23일 한화와의 경기에서 12-3으로 승리했다.",
            ))

    def test_twenty_day_duration_is_not_misread_as_calendar_date(self) -> None:
        self.assertFalse(stale_day_only_context(
            "김태군은 20일 동안 타격 훈련을 진행했다.",
            now=_FrozenDateTime.now(timezone.utc),
        ))

    def test_twenty_days_later_is_not_misread_as_calendar_date(self) -> None:
        self.assertFalse(stale_day_only_context(
            "한화는 20일 뒤 LG와 연습 경기를 치른다.",
            now=_FrozenDateTime.now(timezone.utc),
        ))


if __name__ == "__main__":
    unittest.main()
