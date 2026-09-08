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
        evidence_id="evidence:215",
        article_id="article:215",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id="fact:215",
        subject=subject,
        action=action,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:215",
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
        '<article class="story-row" data-event-id="event:215">'
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


class Live215AudienceInterestForecastRegressions(unittest.TestCase):
    _LIVE_HEADLINE = "소형 휴머노이드 로봇 조종 체험"
    _LIVE_SUMMARY = (
        "소형 휴머노이드 로봇은 조종 체험도 가능해 어린이 관람객의 "
        "흥미를 돋울 것으로 전망된다."
    )

    def test_live_audience_interest_forecast_is_not_material_event(self) -> None:
        assessment = _material(
            self._LIVE_SUMMARY,
            subject="소형 휴머노이드 로봇",
            action="조종 체험도 가능해 어린이 관람객의 흥미를 돋울 것으로 전망된다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,),
        )

    def test_live_audience_interest_forecast_fails_shared_visible_contract(self) -> None:
        values = _issue_values(
            topic="AI·테크",
            headline=self._LIVE_HEADLINE,
            summary=self._LIVE_SUMMARY,
        )
        self.assertIn("FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY", values)

    def test_live_audience_interest_forecast_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY",
        ):
            validate_html(_story_html(
                topic="AI·테크",
                headline=self._LIVE_HEADLINE,
                summary=self._LIVE_SUMMARY,
            ))

    def test_actual_robot_festa_schedule_remains_material(self) -> None:
        assessment = _material(
            "수원시는 수원AI로봇페스타를 9월 12일 수원컨벤션센터에서 개최한다고 밝혔다.",
            subject="수원시",
            action=(
                "수원AI로봇페스타를 9월 12일 수원컨벤션센터에서 개최한다고 밝혔다"
            ),
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_actual_robot_festa_schedule_remains_visible(self) -> None:
        self.assertFalse(_issue_values(
            topic="AI·테크",
            headline="수원 AI로봇페스타, 9월 12일 개최",
            summary=(
                "수원시는 수원AI로봇페스타를 9월 12일 수원컨벤션센터에서 "
                "개최한다고 밝혔다."
            ),
        ))

    def test_attributed_concrete_rate_forecast_remains_material(self) -> None:
        assessment = _material(
            "BNP파리바는 한국은행이 기준금리를 동결할 것으로 내다봤다.",
            subject="BNP파리바",
            action="한국은행이 기준금리를 동결할 것으로 내다봤다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)


class Live215PossessionStateRegressions(unittest.TestCase):
    _LIVE_HEADLINE = "광주 AI 인프라·인재 확보"
    _LIVE_SUMMARY = (
        "광주에는 AI 데이터센터, NPU(신경망처리장치) 센터, 실증 밸리 등 "
        "강력한 AI 인프라와 인재가 보유되어 있다."
    )

    def test_live_existing_infrastructure_inventory_is_not_material_event(self) -> None:
        assessment = _material(
            self._LIVE_SUMMARY,
            subject="광주",
            action=(
                "AI 데이터센터, NPU(신경망처리장치) 센터, 실증 밸리 등 "
                "강력한 AI 인프라와 인재가 보유되어 있다"
            ),
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,),
        )

    def test_live_existing_infrastructure_inventory_fails_shared_visible_contract(self) -> None:
        values = _issue_values(
            topic="AI·테크",
            headline=self._LIVE_HEADLINE,
            summary=self._LIVE_SUMMARY,
        )
        self.assertIn("FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY", values)

    def test_live_existing_infrastructure_inventory_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY",
        ):
            validate_html(_story_html(
                topic="AI·테크",
                headline=self._LIVE_HEADLINE,
                summary=self._LIVE_SUMMARY,
            ))

    def test_new_ai_server_acquisition_remains_material(self) -> None:
        assessment = _material(
            "광주시는 24일 AI 추론 서버 100대를 새로 확보했다.",
            subject="광주시",
            action="24일 AI 추론 서버 100대를 새로 확보했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_new_ai_center_opening_remains_visible(self) -> None:
        self.assertFalse(_issue_values(
            topic="AI·테크",
            headline="광주시, AI 실증센터 개소",
            summary="광주시는 24일 AI 실증센터를 새로 열고 운영을 시작했다.",
        ))

    def test_concrete_company_expansion_plan_remains_material(self) -> None:
        assessment = _material(
            "씨지인사이드는 케미컬 배스 공정 산업 전반으로 AI 플랫폼을 확대할 계획이다.",
            subject="씨지인사이드",
            action="케미컬 배스 공정 산업 전반으로 AI 플랫폼을 확대할 계획이다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)


class Live215GenericMarketCharacteristicRegressions(unittest.TestCase):
    _LIVE_HEADLINE = "단기 IRS의 시장 민감도 특징"
    _LIVE_SUMMARY = (
        "단기 IRS는 기준금리 결정에 따른 기대 변화와 기관 수급 상황에 "
        "민감하게 반응하는 구간이다."
    )

    def test_live_generic_market_characteristic_is_not_material_event(self) -> None:
        assessment = _material(
            self._LIVE_SUMMARY,
            subject="단기 IRS",
            action=(
                "기준금리 결정에 따른 기대 변화와 기관 수급 상황에 "
                "민감하게 반응하는 구간이다"
            ),
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,),
        )

    def test_live_generic_market_characteristic_fails_shared_visible_contract(self) -> None:
        values = _issue_values(
            topic="경제·투자",
            headline=self._LIVE_HEADLINE,
            summary=self._LIVE_SUMMARY,
        )
        self.assertIn("FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY", values)

    def test_live_generic_market_characteristic_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY",
        ):
            validate_html(_story_html(
                topic="경제·투자",
                headline=self._LIVE_HEADLINE,
                summary=self._LIVE_SUMMARY,
            ))

    def test_actual_irs_market_move_remains_material(self) -> None:
        assessment = _material(
            "1년 IRS 금리는 3.50bp 내린 3.4275%로 마감했다.",
            subject="1년 IRS 금리",
            action="3.50bp 내린 3.4275%로 마감했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_actual_irs_market_move_remains_visible(self) -> None:
        self.assertFalse(_issue_values(
            topic="경제·투자",
            headline="1년 IRS 금리 3.50bp 하락",
            summary="1년 IRS 금리는 24일 3.50bp 내린 3.4275%로 마감했다.",
        ))


class Live215OrphanedFirstContentRegressions(unittest.TestCase):
    _SOURCE_SENTENCE = (
        "개장 첫 콘텐츠로는 빅뱅 데뷔 20주년을 기념한 미디어 전시가 마련됐습니다."
    )
    _LIVE_HEADLINE = "빅뱅 데뷔 20주년 기념 미디어 전시 개장"
    _LIVE_SUMMARY = (
        "빅뱅 데뷔 20주년을 기념하는 미디어 전시가 첫 콘텐츠로 마련됐습니다."
    )

    def test_parentless_opening_content_source_fact_is_context_dependent(self) -> None:
        assessment = _material(
            self._SOURCE_SENTENCE,
            subject="빅뱅 데뷔 20주년을 기념한 미디어 전시",
            action="마련됐습니다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.CONTEXT_DEPENDENT_FRAGMENT,),
        )

    def test_live_orphaned_first_content_fails_shared_visible_contract(self) -> None:
        values = _issue_values(
            topic="엔터·음악·K-POP",
            headline=self._LIVE_HEADLINE,
            summary=self._LIVE_SUMMARY,
        )
        self.assertIn("FEED_QUALITY_CONTEXT_DEPENDENT_SUMMARY", values)

    def test_live_orphaned_first_content_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "FEED_QUALITY_CONTEXT_DEPENDENT_SUMMARY",
        ):
            validate_html(_story_html(
                topic="엔터·음악·K-POP",
                headline=self._LIVE_HEADLINE,
                summary=self._LIVE_SUMMARY,
            ))

    def test_named_parent_and_child_event_remain_material(self) -> None:
        assessment = _material(
            "K-문화스테이션은 개장 첫 콘텐츠로 빅뱅 20주년 미디어 전시를 마련했다.",
            subject="K-문화스테이션",
            action="개장 첫 콘텐츠로 빅뱅 20주년 미디어 전시를 마련했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_named_parent_and_child_event_remain_visible(self) -> None:
        self.assertFalse(_issue_values(
            topic="엔터·음악·K-POP",
            headline="K-문화스테이션 개장, 빅뱅 20주년 전시 공개",
            summary=(
                "서울시는 K-문화스테이션을 개장하고 첫 콘텐츠로 빅뱅 "
                "20주년 미디어 전시를 공개했다."
            ),
        ))

    def test_first_ep_release_and_showcase_remain_visible(self) -> None:
        self.assertFalse(_issue_values(
            topic="엔터·음악·K-POP",
            headline="튜이드, 첫 EP 앨범 데뷔 쇼케이스 개최",
            summary=(
                "튜이드는 첫 EP 'TUNE & PLAY'를 발매하고 데뷔 쇼케이스를 "
                "개최했다."
            ),
        ))


if __name__ == "__main__":
    unittest.main()
