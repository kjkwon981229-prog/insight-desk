from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from unittest.mock import patch
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


class _FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        value = cls(2026, 8, 24, 12, 49, tzinfo=timezone.utc)
        return value if tz is None else value.astimezone(tz)


@contextmanager
def _at_live_227_time():
    with (
        patch("insight_desk.feed_quality.datetime", _FrozenDateTime),
        patch("insight_desk.semantic.material.datetime", _FrozenDateTime),
        patch("scripts.validate_feed_artifact.datetime", _FrozenDateTime),
    ):
        yield


def _material(text: str, *, subject: str, action: str):
    span = EvidenceSpan(
        evidence_id="evidence:227",
        article_id="article:227",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id="fact:227",
        subject=subject,
        action=action,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:227",
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
        '<article class="story-row" data-event-id="event:227">'
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


class Live227StaleQuarterRegressions(unittest.TestCase):
    _LIVE_HEADLINE = "1분기 AI 관련 기반상품 교역 40% 이상 증가"
    _LIVE_SUMMARY = (
        "1분기 AI 관련 기반상품 교역이 40% 이상 증가했고, UNCTAD 집계에 "
        "따르면 반도체가 25%, ICT 제품이 14%, 배터리가 15% 늘었다."
    )

    def test_live_first_quarter_background_is_stale_material_event(self) -> None:
        with _at_live_227_time():
            assessment = _material(
                self._LIVE_SUMMARY,
                subject="1분기 AI 관련 기반상품 교역",
                action=(
                    "40% 이상 증가했고, UNCTAD 집계에 따르면 반도체가 25%, "
                    "ICT 제품이 14%, 배터리가 15% 늘었다"
                ),
            )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.STALE_DATED_CONTEXT,),
        )

    def test_live_first_quarter_background_fails_shared_visible_contract(self) -> None:
        with _at_live_227_time():
            values = _issue_values(
                topic="AI·테크",
                headline=self._LIVE_HEADLINE,
                summary=self._LIVE_SUMMARY,
            )
        self.assertIn("FEED_QUALITY_STALE_DATED_CONTEXT", values)

    def test_live_first_quarter_background_fails_artifact_validator(self) -> None:
        with _at_live_227_time():
            with self.assertRaisesRegex(
                ValueError,
                "FEED_QUALITY_STALE_DATED_CONTEXT",
            ):
                validate_html(_story_html(
                    topic="AI·테크",
                    headline=self._LIVE_HEADLINE,
                    summary=self._LIVE_SUMMARY,
                ))

    def test_current_third_quarter_measurement_remains_material(self) -> None:
        with _at_live_227_time():
            assessment = _material(
                "3분기 AI 서버 수출은 현재까지 전년 동기보다 18% 증가했다.",
                subject="3분기 AI 서버 수출",
                action="현재까지 전년 동기보다 18% 증가했다",
            )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_current_dated_half_year_result_remains_material(self) -> None:
        with _at_live_227_time():
            assessment = _material(
                "LG이노텍은 24일 상반기 영업이익 5410억원을 기록했다고 밝혔다.",
                subject="LG이노텍",
                action="24일 상반기 영업이익 5410억원을 기록했다고 밝혔다",
            )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_current_third_quarter_measurement_remains_visible(self) -> None:
        with _at_live_227_time():
            self.assertFalse(_issue_values(
                topic="AI·테크",
                headline="3분기 AI 서버 수출 18% 증가",
                summary="3분기 AI 서버 수출은 현재까지 전년 동기보다 18% 증가했다.",
            ))


class Live227EducationalRateExplainerRegressions(unittest.TestCase):
    _SOURCE_OPENING = (
        "한국은행이 기준금리를 올렸다는 소식부터 주택담보대출 금리, 예금 "
        "금리까지 우리 생활 곳곳에서 금리를 접할 수 있다."
    )
    _LIVE_HEADLINE = "한국은행 기준금리 인상과 생활 속 금리 영향"
    _LIVE_SUMMARY = (
        "한국은행의 기준금리 인상 소식을 비롯해 주택담보대출 금리 및 예금 "
        "금리 등 일상생활 전반에서 금리의 영향이 나타나고 있다."
    )

    def test_live_educational_range_is_not_material_event(self) -> None:
        assessment = _material(
            self._SOURCE_OPENING,
            subject="한국은행",
            action=(
                "기준금리를 올렸다는 소식부터 주택담보대출 금리, 예금 금리까지 "
                "우리 생활 곳곳에서 금리를 접할 수 있다"
            ),
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,),
        )

    def test_live_vague_rate_impact_fails_shared_visible_contract(self) -> None:
        values = _issue_values(
            topic="경제·투자",
            headline=self._LIVE_HEADLINE,
            summary=self._LIVE_SUMMARY,
        )
        self.assertIn("FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY", values)

    def test_live_vague_rate_impact_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY",
        ):
            validate_html(_story_html(
                topic="경제·투자",
                headline=self._LIVE_HEADLINE,
                summary=self._LIVE_SUMMARY,
            ))

    def test_actual_bok_rate_move_remains_material(self) -> None:
        assessment = _material(
            "한국은행은 24일 기준금리를 2.75%에서 3.00%로 인상했다.",
            subject="한국은행",
            action="24일 기준금리를 2.75%에서 3.00%로 인상했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_attributed_concrete_rate_forecast_remains_material(self) -> None:
        assessment = _material(
            "BNP파리바는 한국은행이 기준금리를 동결할 것으로 내다봤다.",
            subject="BNP파리바",
            action="한국은행이 기준금리를 동결할 것으로 내다봤다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_named_ai_certification_event_remains_material(self) -> None:
        assessment = _material(
            "이광호 팀장은 24일 정부의 AI 챔피언 인증을 취득했다.",
            subject="이광호 팀장",
            action="24일 정부의 AI 챔피언 인증을 취득했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)


class Live227ParentlessPerformerLineupRegressions(unittest.TestCase):
    _SOURCE_SENTENCE = (
        "무대에는 가수 하비를 비롯해 이정남&김강주, 힙합&케이팝(K-POP) "
        "가수 주아펄이 출연한다."
    )
    _LIVE_HEADLINE = "가수 주아펄 등 무대 출연"
    _LIVE_SUMMARY = (
        "가수 하비, 이정남&김강주와 함께 힙합 및 케이팝 가수 주아펄이 "
        "무대에 출연한다."
    )

    def test_parentless_source_lineup_is_context_dependent_material(self) -> None:
        assessment = _material(
            self._SOURCE_SENTENCE,
            subject="가수 주아펄",
            action="출연한다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.CONTEXT_DEPENDENT_FRAGMENT,),
        )

    def test_live_parentless_lineup_fails_shared_visible_contract(self) -> None:
        values = _issue_values(
            topic="엔터·음악·K-POP",
            headline=self._LIVE_HEADLINE,
            summary=self._LIVE_SUMMARY,
        )
        self.assertIn("FEED_QUALITY_CONTEXT_DEPENDENT_HEADLINE", values)
        self.assertIn("FEED_QUALITY_CONTEXT_DEPENDENT_SUMMARY", values)

    def test_live_parentless_lineup_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "FEED_QUALITY_CONTEXT_DEPENDENT_HEADLINE",
        ):
            validate_html(_story_html(
                topic="엔터·음악·K-POP",
                headline=self._LIVE_HEADLINE,
                summary=self._LIVE_SUMMARY,
            ))

    def test_named_concert_schedule_remains_material(self) -> None:
        assessment = _material(
            "가평군은 피크닉 콘서트를 8월 29일 음악역1939 야외 잔디광장에서 개최한다.",
            subject="가평군",
            action="피크닉 콘서트를 8월 29일 음악역1939 야외 잔디광장에서 개최한다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_named_concert_lineup_remains_visible(self) -> None:
        self.assertFalse(_issue_values(
            topic="엔터·음악·K-POP",
            headline="가평 피크닉 K-POP 콘서트, 주아펄 등 출연",
            summary=(
                "가평군 피크닉 콘서트에는 가수 하비와 이정남&김강주, "
                "K-POP 가수 주아펄이 8월 29일 출연한다."
            ),
        ))

    def test_actual_kpop_release_and_showcase_remain_visible(self) -> None:
        self.assertFalse(_issue_values(
            topic="엔터·음악·K-POP",
            headline="튜이드, 첫 EP 발매·데뷔 쇼케이스 개최",
            summary=(
                "튜이드는 24일 첫 EP ‘튠 앤 플레이’를 발매하고 "
                "데뷔 쇼케이스를 개최했다."
            ),
        ))


if __name__ == "__main__":
    unittest.main()
