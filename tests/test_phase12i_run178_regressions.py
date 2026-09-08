from __future__ import annotations

from dataclasses import dataclass
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact
from insight_desk.generation import GenerationRequest
from insight_desk.generation_pipeline import ExtractiveFallbackGenerator, ExtractiveFallbackUnavailable
from insight_desk.semantic.material import MaterialEventReason, MaterialEventVerdict, assess_material_event
from scripts.validate_feed_artifact import validate_html


@dataclass(frozen=True)
class _Token:
    tag: str = "VV"


class _PredicateMorphology:
    def analyze(self, text: str):
        del text
        return (_Token(),)


def _material(text: str, *, subject: str, action: str, topic_id: str = "kbo_hanwha"):
    span = EvidenceSpan(
        evidence_id="ev:178",
        article_id="article:178",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id="fact:178",
        subject=subject,
        action=action,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:178",
        topic_id=topic_id,
        fact_ids=(fact.fact_id,),
        article_ids=(span.article_id,),
    )
    return assess_material_event(
        event,
        facts={fact.fact_id: fact},
        evidence={span.evidence_id: span},
        morphology=_PredicateMorphology(),
    )


def _fallback_request(text: str, *, subject: str, action: str) -> GenerationRequest:
    span = EvidenceSpan(
        evidence_id="ev:fallback178",
        article_id="article:fallback178",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id="fact:fallback178",
        subject=subject,
        action=action,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:fallback178",
        topic_id="kbo_hanwha",
        fact_ids=(fact.fact_id,),
        article_ids=(span.article_id,),
    )
    return GenerationRequest(event=event, facts={fact.fact_id: fact}, evidence={span.evidence_id: span})


def _story(*, topic: str, headline: str, summary: str) -> str:
    return (
        '<!doctype html><html><body>'
        '<article class="story-row" data-event-id="event:178">'
        f'<span class="story-topic">{topic}</span>'
        f'<h3>{headline}</h3>'
        f'<p class="story-summary">{summary}</p>'
        '</article></body></html>'
    )


class Run178HumanAuditRegressions(unittest.TestCase):
    def test_hanwha_inference_only_summary_is_non_event_analysis(self) -> None:
        text = "한화의 긴 경기 시간에 불펜진의 불안이 적지 않은 영향을 미친 것으로 보인다."
        result = _material(
            text,
            subject="한화의 긴 경기 시간",
            action="불펜진의 불안이 적지 않은 영향을 미친 것으로 보인다",
        )
        self.assertIs(result.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(result.reasons, (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,))

    def test_hanwha_inference_only_summary_fails_final_validator(self) -> None:
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY"):
            validate_html(
                _story(
                    topic="KBO·한화 이글스",
                    headline="한화 긴 경기, 불펜진 불안 영향",
                    summary="한화의 긴 경기 시간에 불펜진의 불안이 적지 않은 영향을 미친 것으로 보인다.",
                )
            )

    def test_generic_team_fallback_headline_fails_closed(self) -> None:
        text = (
            "팀은 승차가 거의 없이 앞서거니 뒤서거니 하고 있다.\n"
            "6위 롯데 자이언츠, 7위 한화 이글스, 8위 NC 다이노스 세 팀은 승차가 거의 없이 앞서거니 뒤서거니 하고 있다."
        )
        request = _fallback_request(
            text,
            subject="세 팀",
            action="승차가 거의 없이 앞서거니 뒤서거니 하고 있다",
        )
        with self.assertRaises(ExtractiveFallbackUnavailable):
            ExtractiveFallbackGenerator().generate(request)

    def test_kia_centered_headline_cannot_consume_hanwha_slot(self) -> None:
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_TOPIC_BINDING"):
            validate_html(
                _story(
                    topic="KBO·한화 이글스",
                    headline="KIA 타이거즈 순위 4위 하락",
                    summary="LG 트윈스가 한화 이글스를 12-3으로 승리함에 따라 KIA는 4위로 내려갔다.",
                )
            )

    def test_generic_team_headline_cannot_consume_hanwha_slot(self) -> None:
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_TOPIC_BINDING"):
            validate_html(
                _story(
                    topic="KBO·한화 이글스",
                    headline="팀은 승차가 거의 없이 앞서거니 뒤서거니 하고 있다",
                    summary="6위 롯데 자이언츠, 7위 한화 이글스, 8위 NC 다이노스 세 팀은 승차가 거의 없이 앞서거니 뒤서거니 하고 있다.",
                )
            )

    def test_kpop_generic_director_headline_lacks_visible_music_binding(self) -> None:
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_TOPIC_BINDING"):
            validate_html(
                _story(
                    topic="엔터·음악·K-POP",
                    headline="제작총괄의 첫 연출작 ‘고스트밴드’ 공개",
                    summary="디즈니 애니메이터 출신으로 다양한 프로젝트의 제작총괄을 맡았던 그가 첫 연출작 ‘고스트밴드’에 한국적 정서와 밴드 문화 경험을 녹여냈다.",
                )
            )

    def test_kpop_pronoun_fact_subject_defers_before_generation(self) -> None:
        text = "디즈니 애니메이터 출신으로 다양한 프로젝트의 제작총괄을 맡았던 그가 첫 연출작 고스트밴드에 한국적 정서를 녹여냈다."
        result = _material(
            text,
            subject="그",
            action="첫 연출작 고스트밴드에 한국적 정서를 녹여냈다",
            topic_id="kpop",
        )
        self.assertIs(result.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(result.reasons, (MaterialEventReason.CONTEXT_DEPENDENT_FRAGMENT,))

    def test_kpop_explicit_music_headline_remains_valid(self) -> None:
        report = validate_html(
            _story(
                topic="엔터·음악·K-POP",
                headline="키키, 멜론 뮤직 초이스 수상",
                summary="키키가 TIMA 무대에서 멜론 뮤직 초이스상을 수상했다.",
            )
        )
        self.assertEqual(report["topic_binding_violations"], 0)


if __name__ == "__main__":
    unittest.main()
