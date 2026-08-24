from __future__ import annotations

from dataclasses import dataclass
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact
from insight_desk.semantic.material import MaterialEventReason, MaterialEventVerdict, assess_material_event
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
        evidence_id="evidence:189",
        article_id="article:189",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id="fact:189",
        subject=subject,
        action=action,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:189",
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
        '<!doctype html><html><body>'
        '<article class="story-row" data-event-id="event:189">'
        f'<span class="story-topic">{topic}</span>'
        f'<h3>{headline}</h3>'
        f'<p class="story-summary">{summary}</p>'
        '</article></body></html>'
    )


class Live189MaterialityRegressions(unittest.TestCase):
    def test_conditional_revaluation_opinion_is_not_event(self) -> None:
        text = "증권가는 실제 AI 서비스 이용자가 늘고 수익화 성과가 실적으로 확인돼야 재평가가 가능하다고 봤다."
        assessment = _material(
            text,
            subject="증권가",
            action="실제 AI 서비스 이용자가 늘고 수익화 성과가 실적으로 확인돼야 재평가가 가능하다고 봤다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(assessment.reasons, (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,))

    def test_market_attention_state_is_not_event(self) -> None:
        text = "한국은행의 8월 기준금리 결정에 시장의 관심이 쏠리고 있습니다."
        assessment = _material(
            text,
            subject="한국은행의 8월 기준금리 결정",
            action="시장의 관심이 쏠리고 있습니다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(assessment.reasons, (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,))

    def test_song_attribute_description_is_not_event(self) -> None:
        text = "데뷔 타이틀 곡 ‘선 키스(SUN KISS)’는 소울과 일렉트로닉을 결합한 소울트로닉 장르로, 와일드한 트랙과 여유로운 탑라인이 대비를 이루며 햇살에 반짝이는 넓은 바다와 같은 튜이드의 매력을 은유한다."
        assessment = _material(
            text,
            subject="데뷔 타이틀 곡 ‘선 키스(SUN KISS)’",
            action="소울과 일렉트로닉을 결합한 소울트로닉 장르로, 와일드한 트랙과 여유로운 탑라인이 대비를 이루며 햇살에 반짝이는 넓은 바다와 같은 튜이드의 매력을 은유한다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(assessment.reasons, (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,))

    def test_date_led_subjectless_sports_stat_is_context_fragment(self) -> None:
        text = "23일 출전한 퓨처스리그 한화전에서 3타수 1안타 1득점의 성적을 거뒀다."
        assessment = _material(
            text,
            subject="퓨처스리그 한화전",
            action="3타수 1안타 1득점의 성적을 거뒀다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(assessment.reasons, (MaterialEventReason.CONTEXT_DEPENDENT_FRAGMENT,))

    def test_concrete_rate_forecast_remains_material(self) -> None:
        text = "BNP파리바는 한국은행이 이달 열리는 금융통화위원회에서 기준금리를 동결할 것이라고 내다봤다."
        assessment = _material(
            text,
            subject="BNP파리바",
            action="한국은행이 이달 열리는 금융통화위원회에서 기준금리를 동결할 것이라고 내다봤다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_concrete_music_release_event_remains_material(self) -> None:
        text = "튜이드는 24일 첫 번째 EP 앨범을 발매하고 데뷔 쇼케이스를 개최했다."
        assessment = _material(
            text,
            subject="튜이드",
            action="24일 첫 번째 EP 앨범을 발매하고 데뷔 쇼케이스를 개최했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)


class Live189ArtifactBackstopRegressions(unittest.TestCase):
    def test_revaluation_opinion_visible_summary_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY"):
            validate_html(_story_html(
                topic="AI·테크",
                headline="증권가 AI 서비스 재평가 조건",
                summary="증권가는 실제 AI 서비스 이용자가 늘고 수익화 성과가 실적으로 확인돼야 재평가가 가능하다고 봤다.",
            ))

    def test_market_attention_visible_summary_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY"):
            validate_html(_story_html(
                topic="경제·투자",
                headline="한국은행 8월 기준금리 결정에 시장 관심",
                summary="한국은행의 8월 기준금리 결정에 시장의 관심이 쏠리고 있습니다.",
            ))

    def test_song_description_visible_summary_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY"):
            validate_html(_story_html(
                topic="엔터·음악·K-POP",
                headline="튜이드 데뷔곡 '선 키스' 사운드 특징",
                summary="데뷔 타이틀 곡 ‘선 키스(SUN KISS)’는 소울과 일렉트로닉을 결합한 소울트로닉 장르로, 와일드한 트랙과 여유로운 탑라인이 대비를 이루며 튜이드의 매력을 은유한다.",
            ))

    def test_subjectless_sports_stat_visible_summary_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_CONTEXT_DEPENDENT_SUMMARY"):
            validate_html(_story_html(
                topic="KBO·한화 이글스",
                headline="퓨처스리그 한화전 3타수 1안타 1득점 기록",
                summary="23일 출전한 퓨처스리그 한화전에서 3타수 1안타 1득점의 성적을 거뒀다.",
            ))

    def test_concrete_forecast_visible_summary_still_passes(self) -> None:
        report = validate_html(_story_html(
            topic="경제·투자",
            headline="BNP파리바, 한국은행 기준금리 동결 전망",
            summary="BNP파리바는 한국은행이 이달 열리는 금융통화위원회에서 기준금리를 동결할 것이라고 내다봤다.",
        ))
        self.assertEqual(report["status"], "PASS")

    def test_concrete_music_event_visible_summary_still_passes(self) -> None:
        report = validate_html(_story_html(
            topic="엔터·음악·K-POP",
            headline="튜이드, 첫 EP 앨범 데뷔 쇼케이스 개최",
            summary="튜이드는 24일 첫 번째 EP 앨범을 발매하고 데뷔 쇼케이스를 개최했다.",
        ))
        self.assertEqual(report["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
