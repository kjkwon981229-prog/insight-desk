from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact
from insight_desk.semantic.material import MaterialEventReason, MaterialEventVerdict, assess_material_event
from scripts.phase11_daily_production import load_topics, topic_relevant
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
        evidence_id="ev:phase12j",
        article_id="article:phase12j",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id="fact:phase12j",
        subject=subject,
        action=action,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:phase12j",
        topic_id="ai_tech",
        fact_ids=(fact.fact_id,),
        article_ids=(span.article_id,),
    )
    return assess_material_event(
        event,
        facts={fact.fact_id: fact},
        evidence={span.evidence_id: span},
        morphology=_PredicateMorphology(),
    )


def _story_html(summary: str, *, topic: str = "AI·테크") -> str:
    return (
        '<!doctype html><html><body>'
        '<article class="story-row" data-event-id="event:phase12j">'
        f'<span class="story-topic">{topic}</span>'
        '<h3>검증용 독립 헤드라인</h3>'
        f'<p class="story-summary">{summary}</p>'
        '</article></body></html>'
    )


class Phase12JLiveAcceptanceRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ai = next(
            topic for topic in load_topics(Path("config/topics.json")) if topic.topic_id == "ai_tech"
        )

    def test_live_agriculture_agenda_with_incidental_ai_is_not_ai_central(self) -> None:
        text = (
            "문 의원은 농업용수 공급기반 확충, 농지매입, 밭기반 정비와 농업과학기술 확대, "
            "농촌지역 인공지능(AI) 확산 등에 대해 구체적 계획을 요구했다."
        )
        self.assertFalse(topic_relevant(title="농업 정책 계획 요구", body=text, topic=self.ai))

    def test_live_multi_industry_school_tour_with_ai_as_one_item_is_not_ai_central(self) -> None:
        text = (
            "충남 서산시는 고교생들이 항공, 인공지능(AI), 바이오 등 미래산업 현장을 "
            "직접 체험하는 기업 탐방 프로그램을 운영했다."
        )
        self.assertFalse(topic_relevant(title="미래산업 기업 탐방", body=text, topic=self.ai))

    def test_strong_ai_based_service_event_remains_ai_relevant(self) -> None:
        self.assertTrue(
            topic_relevant(
                title="AI 포털 공개",
                body="기관이 AI 기반 서비스와 연구 성과를 모은 포털을 공개했다.",
                topic=self.ai,
            )
        )

    def test_this_portal_anaphora_defers_before_generation(self) -> None:
        text = "이번 포털에는 그동안 개발한 AI 기반 서비스와 연구 성과가 담겼다."
        result = _material(text, subject="이번 포털", action="그동안 개발한 AI 기반 서비스와 연구 성과가 담겼다")
        self.assertIs(result.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(result.reasons, (MaterialEventReason.CONTEXT_DEPENDENT_FRAGMENT,))
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_CONTEXT_DEPENDENT_SUMMARY"):
            validate_html(_story_html(text))

    def test_generic_fan_vote_anaphora_defers_before_generation(self) -> None:
        text = "팬들의 꾸준한 투표 참여가 이어져 여전한 관심과 응원 열기를 보여줬다."
        result = _material(text, subject="팬들의 꾸준한 투표 참여", action="이어져 여전한 관심과 응원 열기를 보여줬다")
        self.assertIs(result.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(result.reasons, (MaterialEventReason.CONTEXT_DEPENDENT_FRAGMENT,))

    def test_conditional_macro_analysis_is_not_a_material_event(self) -> None:
        text = "반도체 업황 둔화 시 세수 감소와 복지·의무지출이 쉽게 줄어들지 않는다."
        result = _material(text, subject="세수 감소와 복지·의무지출", action="쉽게 줄어들지 않는다")
        self.assertIs(result.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(result.reasons, (MaterialEventReason.CONDITIONAL_ANALYTICAL_SCENARIO,))
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_CONDITIONAL_ANALYTICAL_SUMMARY"):
            validate_html(_story_html(text, topic="경제·투자"))

    def test_actual_policy_announcement_with_condition_remains_material(self) -> None:
        text = "정부는 장애 발생 시 이용자를 지원하는 보상안을 발표했다."
        result = _material(text, subject="정부", action="장애 발생 시 이용자를 지원하는 보상안을 발표했다")
        self.assertIs(result.verdict, MaterialEventVerdict.MATERIAL)

    def test_old_dated_release_context_defers_before_generation(self) -> None:
        old = datetime.now(timezone.utc) - timedelta(days=10)
        date_text = f"{old.month}월{old.day}일"
        text = f"{date_text} 공개된 다큐멘터리에서 RM은 영어 가사 비중이 커진 점을 우려했다."
        result = _material(text, subject="RM", action="영어 가사 비중이 커진 점을 우려했다")
        self.assertIs(result.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(result.reasons, (MaterialEventReason.STALE_DATED_CONTEXT,))
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_STALE_DATED_CONTEXT"):
            validate_html(_story_html(text, topic="엔터·음악·K-POP"))

    def test_stale_date_embedded_source_url_fails_acceptance(self) -> None:
        audit = {
            "rendered_sources": [
                {
                    "event_id": "event:phase12j",
                    "source_group_key": "source:phase12j",
                    "content_sha256": "a" * 64,
                    "source_url": "https://example.com/article/202001010543Q",
                }
            ]
        }
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_STALE_SOURCE_URL"):
            validate_html(
                _story_html("기관이 AI 기반 서비스를 공개했다."),
                source_audit=audit,
            )


if __name__ == "__main__":
    unittest.main()
