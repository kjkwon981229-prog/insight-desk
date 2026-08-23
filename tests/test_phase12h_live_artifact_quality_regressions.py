from __future__ import annotations

from dataclasses import dataclass
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact
from insight_desk.generation import GenerationRequest
from insight_desk.generation_pipeline import ExtractiveFallbackGenerator
from insight_desk.semantic.material import MaterialEventReason, MaterialEventVerdict, assess_material_event
from scripts.validate_feed_artifact import validate_html


def _story_html(*, headline: str, summary: str) -> str:
    return (
        '<!doctype html><html><body>'
        '<article id="story-1" class="story-row" data-event-id="event:live-regression">'
        '<div class="story-main">'
        '<div class="story-meta"><span class="story-topic">KBO·한화 이글스</span></div>'
        f'<h3>{headline}</h3>'
        f'<p class="story-summary">{summary}</p>'
        '</div></article></body></html>'
    )


@dataclass(frozen=True)
class _Token:
    tag: str = "VV"


class _PredicateMorphology:
    def analyze(self, text: str):
        del text
        return (_Token(),)


def _material_assessment(text: str, *, subject: str, action: str):
    span = EvidenceSpan(
        evidence_id="ev:live-quality",
        article_id="article:live-quality",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id="fact:live-quality",
        subject=subject,
        action=action,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:live-quality",
        topic_id="kbo_hanwha",
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
        evidence_id="ev:live-fallback",
        article_id="article:live-fallback",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id="fact:live-fallback",
        subject=subject,
        action=action,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:live-fallback",
        topic_id="kbo_hanwha",
        fact_ids=(fact.fact_id,),
        article_ids=(span.article_id,),
    )
    return GenerationRequest(
        event=event,
        facts={fact.fact_id: fact},
        evidence={span.evidence_id: span},
    )


class Phase12HLiveArtifactQualityRegressions(unittest.TestCase):
    def test_live_single_sentence_fallback_forms_distinct_exact_headline(self) -> None:
        sentence = (
            "이어 2사 2,3루에서 문정빈이 한화 선발 박준영의 초구 포크볼(135km)을 때려 "
            "좌월 3점 홈런(시즌 15호)을 터뜨렸다."
        )
        action = (
            "한화 선발 박준영의 초구 포크볼(135km)을 때려 "
            "좌월 3점 홈런(시즌 15호)을 터뜨렸다"
        )
        draft = ExtractiveFallbackGenerator().generate(
            _fallback_request(sentence, subject="문정빈", action=action)
        )
        self.assertEqual(
            draft.headline,
            "문정빈이 한화 선발 박준영의 초구 포크볼(135km)을 때려 좌월 3점 홈런(시즌 15호)을 터뜨렸다",
        )
        self.assertEqual(draft.summary, sentence)
        self.assertNotEqual(draft.headline, draft.summary)
        self.assertIn(draft.headline, sentence)

    def test_same_card_headline_summary_collision_fails_product_gate(self) -> None:
        sentence = (
            "이어 2사 2,3루에서 문정빈이 한화 선발 박준영의 초구 포크볼(135km)을 때려 "
            "좌월 3점 홈런(시즌 15호)을 터뜨렸다."
        )
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_HEADLINE_SUMMARY_COLLISION"):
            validate_html(_story_html(headline=sentence, summary=sentence))

    def test_standalone_sports_photo_caption_defers(self) -> None:
        text = (
            "23일 대전 한화생명 볼파크에서 열린 LG 트윈스와의 경기에서 "
            "한화 이글스 김서현이 투구를 펼치고 있다."
        )
        assessment = _material_assessment(
            text,
            subject="한화 이글스 김서현",
            action="투구를 펼치고 있다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(assessment.reasons, (MaterialEventReason.DEPICTIVE_SPORTS_CAPTION,))

    def test_substantive_sports_result_remains_material(self) -> None:
        text = "김서현이 23일 LG전에서 1이닝 2피안타 무실점을 기록했다."
        assessment = _material_assessment(
            text,
            subject="김서현",
            action="1이닝 2피안타 무실점을 기록했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.EVIDENCE_BOUND_EXPLICIT_PREDICATE,),
        )


if __name__ == "__main__":
    unittest.main()
