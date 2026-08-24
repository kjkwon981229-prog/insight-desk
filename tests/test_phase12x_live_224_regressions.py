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
        evidence_id="evidence:224",
        article_id="article:224",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id="fact:224",
        subject=subject,
        action=action,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:224",
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
        '<article class="story-row" data-event-id="event:224">'
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


class Live224RetrospectiveStrategyRegressions(unittest.TestCase):
    _LIVE_HEADLINE = "문 사장, ‘고수익 사업 포트폴리오’ 핵심으로 반도체 기판 지목"
    _LIVE_SUMMARY = (
        "문 사장은 ‘고수익 사업 포트폴리오’를 이끌 핵심 사업으로 ‘수익성’과 "
        "‘성장성’이라는 두 가지 키워드를 모두 충족하는 반도체 기판을 지목했다."
    )

    def test_live_undated_strategy_background_is_not_material_event(self) -> None:
        assessment = _material(
            self._LIVE_SUMMARY,
            subject="문 사장",
            action=(
                "‘고수익 사업 포트폴리오’를 이끌 핵심 사업으로 ‘수익성’과 "
                "‘성장성’이라는 두 가지 키워드를 모두 충족하는 반도체 기판을 지목했다"
            ),
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,),
        )

    def test_live_undated_strategy_background_fails_shared_visible_contract(self) -> None:
        values = _issue_values(
            topic="AI·테크",
            headline=self._LIVE_HEADLINE,
            summary=self._LIVE_SUMMARY,
        )
        self.assertIn("FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY", values)

    def test_live_undated_strategy_background_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY",
        ):
            validate_html(_story_html(
                topic="AI·테크",
                headline=self._LIVE_HEADLINE,
                summary=self._LIVE_SUMMARY,
            ))

    def test_current_quantified_company_result_remains_material(self) -> None:
        assessment = _material(
            "LG이노텍은 24일 상반기 영업이익 5410억원을 기록해 전년보다 296% 증가했다고 밝혔다.",
            subject="LG이노텍",
            action="24일 상반기 영업이익 5410억원을 기록해 전년보다 296% 증가했다고 밝혔다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_current_dated_strategy_investment_decision_remains_material(self) -> None:
        assessment = _material(
            "LG이노텍은 24일 반도체 기판을 핵심 성장 사업으로 정하고 생산라인에 1조원을 투자하기로 결정했다.",
            subject="LG이노텍",
            action=(
                "24일 반도체 기판을 핵심 성장 사업으로 정하고 생산라인에 "
                "1조원을 투자하기로 결정했다"
            ),
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_current_quantified_company_result_remains_visible(self) -> None:
        self.assertFalse(_issue_values(
            topic="AI·테크",
            headline="LG이노텍 상반기 영업이익 5410억원",
            summary=(
                "LG이노텍은 24일 상반기 영업이익 5410억원을 기록해 "
                "전년보다 296% 증가했다고 밝혔다."
            ),
        ))


class Live224AbstractTransformationRegressions(unittest.TestCase):
    _LIVE_HEADLINE = "알파벳 최고경영자, AI 투자로 인한 사업 가능성 재정의 언급"
    _LIVE_SUMMARY = (
        "순다르 피차이 알파벳 최고경영자는 실적자료를 통해 AI 투자가 사업 "
        "전반의 가능성을 다시 정의하고 있다고 밝혔다."
    )

    def test_live_abstract_business_transformation_is_not_material_event(self) -> None:
        assessment = _material(
            self._LIVE_SUMMARY,
            subject="순다르 피차이 알파벳 최고경영자",
            action="실적자료를 통해 AI 투자가 사업 전반의 가능성을 다시 정의하고 있다고 밝혔다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,),
        )

    def test_live_abstract_business_transformation_fails_shared_visible_contract(self) -> None:
        values = _issue_values(
            topic="AI·테크",
            headline=self._LIVE_HEADLINE,
            summary=self._LIVE_SUMMARY,
        )
        self.assertIn("FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY", values)

    def test_live_abstract_business_transformation_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY",
        ):
            validate_html(_story_html(
                topic="AI·테크",
                headline=self._LIVE_HEADLINE,
                summary=self._LIVE_SUMMARY,
            ))

    def test_concrete_capex_guidance_increase_remains_material(self) -> None:
        assessment = _material(
            "알파벳은 2026년 자본지출 가이던스를 1800억~1900억 달러에서 1950억~2050억 달러로 높였다고 밝혔다.",
            subject="알파벳",
            action=(
                "2026년 자본지출 가이던스를 1800억~1900억 달러에서 "
                "1950억~2050억 달러로 높였다고 밝혔다"
            ),
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_concrete_ai_service_launch_remains_material(self) -> None:
        assessment = _material(
            "알파벳은 24일 기업용 AI 에이전트 서비스를 출시했다고 밝혔다.",
            subject="알파벳",
            action="24일 기업용 AI 에이전트 서비스를 출시했다고 밝혔다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_concrete_capex_guidance_increase_remains_visible(self) -> None:
        self.assertFalse(_issue_values(
            topic="AI·테크",
            headline="알파벳, 2026년 자본지출 가이던스 상향",
            summary=(
                "알파벳은 2026년 자본지출 가이던스를 1950억~2050억 "
                "달러로 높였다고 밝혔다."
            ),
        ))


class Live224GenericCivicActorRegressions(unittest.TestCase):
    _LIVE_HEADLINE = "지자체, 공공 CCTV 보존 기간 연장 및 AI 연안 감시체계 확충"
    _LIVE_SUMMARY = (
        "지자체는 공공 목적의 폐쇄회로 영상 보존 기간을 기존보다 연장하는 "
        "방안을 추진하기로 했으며, 인공지능 기술을 활용한 연안 감시 장비를 "
        "조속히 확충할 방침이다."
    )

    def test_live_unnamed_civic_actor_is_context_dependent_material(self) -> None:
        assessment = _material(
            self._LIVE_SUMMARY,
            subject="지자체",
            action=(
                "공공 목적의 폐쇄회로 영상 보존 기간을 기존보다 연장하는 방안을 "
                "추진하기로 했으며, 인공지능 기술을 활용한 연안 감시 장비를 "
                "조속히 확충할 방침이다"
            ),
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.CONTEXT_DEPENDENT_FRAGMENT,),
        )

    def test_live_unnamed_civic_actor_fails_shared_visible_contract(self) -> None:
        values = _issue_values(
            topic="AI·테크",
            headline=self._LIVE_HEADLINE,
            summary=self._LIVE_SUMMARY,
        )
        self.assertIn("FEED_QUALITY_CONTEXT_DEPENDENT_HEADLINE", values)
        self.assertIn("FEED_QUALITY_CONTEXT_DEPENDENT_SUMMARY", values)

    def test_live_unnamed_civic_actor_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "FEED_QUALITY_CONTEXT_DEPENDENT_HEADLINE",
        ):
            validate_html(_story_html(
                topic="AI·테크",
                headline=self._LIVE_HEADLINE,
                summary=self._LIVE_SUMMARY,
            ))

    def test_named_jeju_policy_decision_remains_material(self) -> None:
        assessment = _material(
            "제주도는 공공 CCTV 보존 기간을 연장하고 AI 연안 감시 장비를 확충하기로 결정했다.",
            subject="제주도",
            action="공공 CCTV 보존 기간을 연장하고 AI 연안 감시 장비를 확충하기로 결정했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_named_jeju_policy_decision_remains_visible(self) -> None:
        self.assertFalse(_issue_values(
            topic="AI·테크",
            headline="제주도, CCTV 보존 연장·AI 연안 감시 확충",
            summary=(
                "제주도는 공공 CCTV 보존 기간을 연장하고 AI 연안 감시 "
                "장비를 확충하기로 결정했다."
            ),
        ))

    def test_named_national_government_announcement_remains_material(self) -> None:
        assessment = _material(
            "정부는 24일 전국 연안에 AI 감시 장비 100대를 배치한다고 발표했다.",
            subject="정부",
            action="24일 전국 연안에 AI 감시 장비 100대를 배치한다고 발표했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)


class Live224ConditionalCausalExplainerRegressions(unittest.TestCase):
    _LIVE_HEADLINE = (
        "높아지면 위험을 감수하면서 투자하지 않아도 비교적 높은 이자를 "
        "받을 수 있기 때문이다"
    )
    _LIVE_SUMMARY = (
        "예금 금리가 높아지면 위험을 감수하면서 투자하지 않아도 비교적 "
        "높은 이자를 받을 수 있기 때문이다."
    )

    def test_live_conditional_causal_explainer_is_not_material_event(self) -> None:
        assessment = _material(
            self._LIVE_SUMMARY,
            subject="예금 금리",
            action="높아지면 위험을 감수하면서 투자하지 않아도 비교적 높은 이자를 받을 수 있기 때문이다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.CONDITIONAL_ANALYTICAL_SCENARIO,),
        )

    def test_live_conditional_explainer_fails_shared_visible_contract(self) -> None:
        values = _issue_values(
            topic="경제·투자",
            headline=self._LIVE_HEADLINE,
            summary=self._LIVE_SUMMARY,
        )
        self.assertIn("FEED_QUALITY_CONTEXT_DEPENDENT_HEADLINE", values)
        self.assertIn("FEED_QUALITY_CONDITIONAL_ANALYTICAL_SUMMARY", values)

    def test_live_conditional_explainer_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "FEED_QUALITY_CONTEXT_DEPENDENT_HEADLINE",
        ):
            validate_html(_story_html(
                topic="경제·투자",
                headline=self._LIVE_HEADLINE,
                summary=self._LIVE_SUMMARY,
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
