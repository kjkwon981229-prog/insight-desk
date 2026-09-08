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
        evidence_id="evidence:203",
        article_id="article:203",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id="fact:203",
        subject=subject,
        action=action,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:203",
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
        '<article class="story-row" data-event-id="event:203">'
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


class Live203EditorialRelationRegressions(unittest.TestCase):
    _LIVE_SUMMARY = (
        "삼성전자와 SK하이닉스가 광주에 건설하겠다는 반도체 공장도, "
        "포스코 포항제철소의 수소환원제철소 역시 원전과 필수불가결하게 연결된다."
    )

    def test_live_nuclear_dependency_editorial_is_not_material_event(self) -> None:
        assessment = _material(
            self._LIVE_SUMMARY,
            subject="삼성전자와 SK하이닉스가 광주에 건설하겠다는 반도체 공장",
            action=(
                "포스코 포항제철소의 수소환원제철소 역시 원전과 "
                "필수불가결하게 연결된다"
            ),
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,),
        )

    def test_general_indispensable_relation_family_is_not_material_event(self) -> None:
        cases = (
            (
                "AI 데이터센터는 안정적인 전력 공급과 필수불가결하게 연결된다.",
                "AI 데이터센터",
                "안정적인 전력 공급과 필수불가결하게 연결된다",
            ),
            (
                "첨단 제조업은 전력망 확충과 불가분의 관계에 있다.",
                "첨단 제조업",
                "전력망 확충과 불가분의 관계에 있다",
            ),
            (
                "반도체 산업의 성장은 원전 확대 필요성으로 귀결된다.",
                "반도체 산업의 성장",
                "원전 확대 필요성으로 귀결된다",
            ),
        )
        for text, subject, action in cases:
            with self.subTest(text=text):
                assessment = _material(text, subject=subject, action=action)
                self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
                self.assertEqual(
                    assessment.reasons,
                    (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,),
                )

    def test_same_editorial_summary_fails_shared_visible_contract(self) -> None:
        values = _issue_values(
            topic="AI·테크",
            headline="SK하이닉스·포스코 시설, 원전과 필수불가결 연결",
            summary=self._LIVE_SUMMARY,
        )
        self.assertIn("FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY", values)

    def test_same_editorial_summary_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY"):
            validate_html(_story_html(
                topic="AI·테크",
                headline="SK하이닉스·포스코 시설, 원전과 필수불가결 연결",
                summary=self._LIVE_SUMMARY,
            ))

    def test_actual_semiconductor_factory_announcement_remains_material(self) -> None:
        assessment = _material(
            "SK하이닉스는 광주 AI 반도체 공장 건설 계획을 발표했다.",
            subject="SK하이닉스",
            action="광주 AI 반도체 공장 건설 계획을 발표했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_actual_nuclear_plant_decision_remains_material(self) -> None:
        assessment = _material(
            "한국수력원자력은 영덕 신규 원전 2기 건설 계획을 확정했다.",
            subject="한국수력원자력",
            action="영덕 신규 원전 2기 건설 계획을 확정했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_actual_treasury_yield_move_remains_material(self) -> None:
        assessment = _material(
            "미국 30년 만기 국채 금리가 5.3%에 도달했다.",
            subject="미국 30년 만기 국채 금리",
            action="5.3%에 도달했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)


class Live203ReporterMetadataRegressions(unittest.TestCase):
    _LIVE_SUMMARY = (
        "교보생명이 신종자본증권 발행을 위한 투자자 모집을 실시해 5000억원 "
        "조달을 확정했다고 금융소비자뉴스 홍윤정 기자가 전했다."
    )

    def test_trailing_reporter_attribution_fails_shared_visible_contract(self) -> None:
        values = _issue_values(
            topic="경제·투자",
            headline="교보생명, 5000억원 규모 신종자본증권 발행 확정",
            summary=self._LIVE_SUMMARY,
        )
        self.assertIn("FEED_QUALITY_VISIBLE_METADATA", values)

    def test_trailing_reporter_attribution_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_VISIBLE_METADATA"):
            validate_html(_story_html(
                topic="경제·투자",
                headline="교보생명, 5000억원 규모 신종자본증권 발행 확정",
                summary=self._LIVE_SUMMARY,
            ))

    def test_leading_bracketed_byline_remains_rejected(self) -> None:
        values = _issue_values(
            topic="엔터·음악·K-POP",
            headline="튜이드 데뷔 쇼케이스 개최",
            summary=(
                "[톱스타뉴스 최규석 기자] 튜이드가 첫 EP 데뷔 쇼케이스를 개최했다."
            ),
        )
        self.assertIn("FEED_QUALITY_VISIBLE_METADATA", values)

    def test_institutional_attribution_is_not_reporter_metadata(self) -> None:
        self.assertFalse(_issue_values(
            topic="경제·투자",
            headline="금융위원회, 공매도 제도 개선안 발표",
            summary="금융위원회는 공매도 제도 개선안을 발표했다고 밝혔다.",
        ))

    def test_actual_kpop_event_remains_material(self) -> None:
        assessment = _material(
            "튜이드는 첫 EP 앨범을 발매하고 데뷔 쇼케이스를 개최했다.",
            subject="튜이드",
            action="첫 EP 앨범을 발매하고 데뷔 쇼케이스를 개최했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_named_sports_stat_remains_standalone(self) -> None:
        self.assertFalse(_issue_values(
            topic="KBO·한화 이글스",
            headline="한화 김서현, LG전 1이닝 무실점",
            summary=(
                "김서현은 23일 LG 트윈스와의 경기에 구원 등판해 "
                "1이닝 2피안타 1탈삼진 무실점을 기록했다."
            ),
        ))


if __name__ == "__main__":
    unittest.main()
