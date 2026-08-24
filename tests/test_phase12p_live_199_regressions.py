from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import patch
import sys
import unittest

from insight_desk.acquisition.runtime import TrafilaturaExtractor
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
        evidence_id="evidence:199:economy",
        article_id="article:199:economy",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id="fact:199:economy",
        subject=subject,
        action=action,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:199:economy",
        topic_id="economy",
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
        '<article class="story-row" data-event-id="event:199">'
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


class Live199VisibleContainerRegressions(unittest.TestCase):
    def test_ai_category_without_parent_competition_fails_visible_contract(self) -> None:
        values = _issue_values(
            topic="AI·테크",
            headline="한국도로공사, AI 활용 디자인 분야 신설",
            summary=(
                "한국도로공사가 올해 생성형 AI를 활용해 디자인을 구현하는 "
                "'AI활용' 분야를 신설했다."
            ),
        )
        self.assertIn("FEED_QUALITY_CONTEXT_DEPENDENT_HEADLINE", values)
        self.assertIn("FEED_QUALITY_CONTEXT_DEPENDENT_SUMMARY", values)

    def test_ai_category_without_parent_competition_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_CONTEXT_DEPENDENT"):
            validate_html(_story_html(
                topic="AI·테크",
                headline="한국도로공사, AI 활용 디자인 분야 신설",
                summary=(
                    "한국도로공사가 올해 생성형 AI를 활용해 디자인을 구현하는 "
                    "'AI활용' 분야를 신설했다."
                ),
            ))

    def test_named_parent_competition_category_remains_standalone(self) -> None:
        self.assertFalse(_issue_values(
            topic="AI·테크",
            headline="한국도로공사, 도로경관디자인 대전에 AI 활용 분야 신설",
            summary=(
                "한국도로공사가 제15회 도로경관디자인 대전에 생성형 AI를 활용하는 "
                "'AI활용' 분야를 신설했다."
            ),
        ))

    def test_named_award_event_remains_standalone(self) -> None:
        self.assertFalse(_issue_values(
            topic="AI·테크",
            headline="AI 서리예측 서비스, 전북 적극행정 경진대회 최우수상",
            summary=(
                "전북 농업기술원 원예과의 AI 기반 농장별 서리예측 서비스가 "
                "2026년 하반기 적극행정 우수사례 경진대회 최우수상을 수상했다."
            ),
        ))


class Live199AnalyticalConsequenceRegressions(unittest.TestCase):
    _LIVE_SUMMARY = (
        "· 원/미국달러: 1382.40원 (전일 -4.1원 / 주간 -30.6원)\n"
        "· 원/위안: 205.52원 (전일 -0.8원 / 주간 -4.7원)\n"
        "· 원/일본엔(100엔): 870.44원 (전일 -6.0원 / 주간 -16.9원)\n"
        "· 원/유로: 1615.49원 (전일 -12.2원 / 주간 -16.4원)\n"
        "국고채 5년 금리 하락은 고정형 주담대 금리에 내림세 신호로 작용할 수 있다."
    )

    def test_conditional_mortgage_rate_consequence_is_not_material_event(self) -> None:
        assessment = _material(
            self._LIVE_SUMMARY,
            subject="국고채 5년 금리 하락",
            action="고정형 주담대 금리에 내림세 신호로 작용할 수 있다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,),
        )

    def test_mixed_fx_and_mortgage_analysis_fails_shared_visible_contract(self) -> None:
        values = _issue_values(
            topic="경제·투자",
            headline="환율 (8월 24일 15:30 기준)",
            summary=self._LIVE_SUMMARY,
        )
        self.assertIn("FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY", values)

    def test_mixed_fx_and_mortgage_analysis_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY"):
            validate_html(_story_html(
                topic="경제·투자",
                headline="환율 (8월 24일 15:30 기준)",
                summary=self._LIVE_SUMMARY,
            ))

    def test_actual_exchange_rate_move_remains_material(self) -> None:
        assessment = _material(
            "원·달러 환율은 전 거래일보다 4.1원 내린 1382.40원에 마감했다.",
            subject="원·달러 환율",
            action="전 거래일보다 4.1원 내린 1382.40원에 마감했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_attributed_concrete_rate_forecast_remains_material(self) -> None:
        assessment = _material(
            "BNP파리바는 한국은행이 기준금리를 동결할 것으로 내다봤다.",
            subject="BNP파리바",
            action="한국은행이 기준금리를 동결할 것으로 내다봤다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)


class Live199InlineSourceFidelityRegressions(unittest.TestCase):
    _SOURCE_SENTENCE = (
        "미국 연방준비제도(Fed·연준)가 통화정책 경로를 전환한 가운데, "
        "미국 30년 만기 국채 금리가 5.3%에 도달했다."
    )

    @staticmethod
    def _inline_span_html() -> str:
        sentence = (
            "미국 연방준비제도"
            '<span style="box-sizing: border-box; letter-spacing: 0pt;">(Fed·</span>'
            "연준"
            '<span style="box-sizing: border-box; letter-spacing: 0pt;">)</span>'
            "가 통화정책 경로를 전환한 가운데"
            '<span style="box-sizing: border-box; letter-spacing: 0pt;">, </span>'
            "미국 "
            '<span style="box-sizing: border-box; letter-spacing: 0pt;">30</span>'
            "년 만기 국채 금리가 "
            '<span style="box-sizing: border-box; letter-spacing: 0pt;">5.3%</span>'
            "에 도달했다"
            '<span style="box-sizing: border-box; letter-spacing: 0pt;">.</span>'
        )
        return (
            "<html><head><title>미국 장기 국채 금리</title></head><body><article>"
            + "".join(f"<p>{sentence}</p>" for _ in range(12))
            + "</article></body></html>"
        )

    def test_trafilatura_route_avoids_destructive_precision_mode(self) -> None:
        calls: list[dict[str, object]] = []

        def extract(html: str, **kwargs: object) -> str:
            del html
            calls.append(kwargs)
            if kwargs.get("favor_precision") is True:
                return (
                    "미국 연방준비제도연준가 통화정책 경로를 전환한 가운데미국 "
                    "년 만기 국채 금리가 에 도달했다"
                )
            return self._SOURCE_SENTENCE

        fake_module = SimpleNamespace(extract=extract)
        with patch.dict(sys.modules, {"trafilatura": fake_module}):
            extracted = TrafilaturaExtractor().extract(
                self._inline_span_html(),
                url="https://example.com/live-199-inline-spans",
            )

        self.assertIsNot(calls[0].get("favor_precision"), True)
        self.assertIn(self._SOURCE_SENTENCE, extracted.body)
        for literal in ("(Fed·연준)", "30년", "5.3%", "가운데, 미국"):
            with self.subTest(literal=literal):
                self.assertIn(literal, extracted.body)

    def test_live_numeric_holes_fail_shared_visible_contract(self) -> None:
        values = _issue_values(
            topic="경제·투자",
            headline="가운데미국 년 만기 국채 금리가 에 도달했다",
            summary=(
                "미국 연방준비제도연준가 통화정책 경로를 사전 안내하던 "
                "선제지침포워드 가이던스을 성명서에서 제거하며 소통 방식을 대대적으로 "
                "전환한 가운데미국 년 만기 국채 금리가 에 도달했다"
            ),
        )
        self.assertIn("FEED_QUALITY_MALFORMED_VISIBLE_TEXT", values)

    def test_live_numeric_holes_fail_artifact_validator(self) -> None:
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_MALFORMED_VISIBLE_TEXT"):
            validate_html(_story_html(
                topic="경제·투자",
                headline="가운데미국 년 만기 국채 금리가 에 도달했다",
                summary=(
                    "미국 연방준비제도연준가 통화정책 경로를 사전 안내하던 "
                    "선제지침포워드 가이던스을 성명서에서 제거하며 소통 방식을 대대적으로 "
                    "전환한 가운데미국 년 만기 국채 금리가 에 도달했다"
                ),
            ))

    def test_subordinate_gaunde_headline_fails_standalone_contract(self) -> None:
        values = _issue_values(
            topic="경제·투자",
            headline="가운데, 미국 30년 만기 국채 금리가 5.3%에 도달",
            summary=self._SOURCE_SENTENCE,
        )
        self.assertIn("FEED_QUALITY_CONTEXT_DEPENDENT_HEADLINE", values)

    def test_complete_treasury_yield_event_remains_standalone(self) -> None:
        self.assertFalse(_issue_values(
            topic="경제·투자",
            headline="미국 30년 만기 국채 금리 5.3% 도달",
            summary="미국 30년 만기 국채 금리가 5.3%에 도달했다.",
        ))


class Live199KboHeadlineRegressions(unittest.TestCase):
    _LIVE_HEADLINE = (
        "23일 대전 한화생명 볼파크에서 열린 LG 트윈스와 경기에서 구원투수로 "
        "등판해 1이닝 2피안타 1탈삼진 무실점을 기록했다"
    )
    _LIVE_SUMMARY = (
        "김서현은 23일 대전 한화생명 볼파크에서 열린 LG 트윈스와 경기에서 "
        "구원투수로 등판해 1이닝 2피안타 1탈삼진 무실점을 기록했다."
    )

    def test_date_led_subjectless_kim_seohyun_headline_fails_shared_contract(self) -> None:
        values = _issue_values(
            topic="KBO·한화 이글스",
            headline=self._LIVE_HEADLINE,
            summary=self._LIVE_SUMMARY,
        )
        self.assertIn("FEED_QUALITY_CONTEXT_DEPENDENT_HEADLINE", values)

    def test_date_led_subjectless_kim_seohyun_headline_fails_validator(self) -> None:
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_CONTEXT_DEPENDENT_HEADLINE"):
            validate_html(_story_html(
                topic="KBO·한화 이글스",
                headline=self._LIVE_HEADLINE,
                summary=self._LIVE_SUMMARY,
            ))

    def test_named_kim_seohyun_stat_remains_standalone(self) -> None:
        self.assertFalse(_issue_values(
            topic="KBO·한화 이글스",
            headline="한화 김서현, LG전 1이닝 무실점",
            summary=self._LIVE_SUMMARY,
        ))


if __name__ == "__main__":
    unittest.main()
