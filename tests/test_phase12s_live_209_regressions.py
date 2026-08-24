from __future__ import annotations

from dataclasses import dataclass
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact
from insight_desk.feed_quality import visible_story_issues
from insight_desk.generation import GeneratedDraft, GenerationRequest, validate_preservation
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


def _event_fixture(
    text: str,
    *,
    subject: str,
    action: str,
) -> tuple[CandidateEvent, EventFact, EvidenceSpan]:
    span = EvidenceSpan(
        evidence_id="evidence:209",
        article_id="article:209",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id="fact:209",
        subject=subject,
        action=action,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:209",
        topic_id="fixture",
        fact_ids=(fact.fact_id,),
        article_ids=(span.article_id,),
    )
    return event, fact, span


def _material(text: str, *, subject: str, action: str):
    event, fact, span = _event_fixture(text, subject=subject, action=action)
    return assess_material_event(
        event,
        facts={fact.fact_id: fact},
        evidence={span.evidence_id: span},
        morphology=_PredicateMorphology(),
    )


def _request(text: str, *, subject: str, action: str) -> GenerationRequest:
    event, fact, span = _event_fixture(text, subject=subject, action=action)
    return GenerationRequest(
        event=event,
        facts={fact.fact_id: fact},
        evidence={span.evidence_id: span},
    )


def _story_html(*, topic: str, headline: str, summary: str) -> str:
    return (
        "<!doctype html><html><body>"
        '<article class="story-row" data-event-id="event:209">'
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


class Live209MissingBlockBoundaryRegressions(unittest.TestCase):
    _LIVE_HEADLINE = "외교부, AI 공급망 기업 간담회 개최"
    _LIVE_SUMMARY = (
        "AI 반도체·안전·통신·모델 기업 참석외교부가 24일 인공지능(AI) 공급망 "
        "관련 기업들과 간담회를 열고 국내 AI 기업의 글로벌 경쟁력 강화와 "
        "국제협력 방안을 논의했다고 밝혔다."
    )

    def test_live_subtitle_body_concatenation_fails_shared_contract(self) -> None:
        values = _issue_values(
            topic="AI·테크",
            headline=self._LIVE_HEADLINE,
            summary=self._LIVE_SUMMARY,
        )
        self.assertIn("FEED_QUALITY_MALFORMED_VISIBLE_TEXT", values)

    def test_live_subtitle_body_concatenation_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_MALFORMED_VISIBLE_TEXT"):
            validate_html(_story_html(
                topic="AI·테크",
                headline=self._LIVE_HEADLINE,
                summary=self._LIVE_SUMMARY,
            ))

    def test_explicit_sentence_boundary_remains_visible(self) -> None:
        self.assertFalse(_issue_values(
            topic="AI·테크",
            headline=self._LIVE_HEADLINE,
            summary=(
                "AI 반도체·안전·통신·모델 기업이 참석했다. 외교부가 24일 "
                "AI 공급망 관련 기업들과 간담회를 열었다."
            ),
        ))

    def test_normal_participant_word_is_not_a_false_boundary(self) -> None:
        self.assertFalse(_issue_values(
            topic="AI·테크",
            headline=self._LIVE_HEADLINE,
            summary="외교부 간담회 참석자들은 AI 국제협력 확대 방안에 합의했다.",
        ))


class Live209DefinitionMaterialityRegressions(unittest.TestCase):
    _LIVE_HEADLINE = "백투백 인상의 정의"
    _LIVE_SUMMARY = "백투백 인상은 기준금리를 연속으로 올리는 경우를 의미한다."

    def test_live_glossary_definition_is_not_material_event(self) -> None:
        assessment = _material(
            self._LIVE_SUMMARY,
            subject="백투백 인상",
            action="기준금리를 연속으로 올리는 경우를 의미한다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,),
        )

    def test_live_glossary_definition_fails_shared_visible_contract(self) -> None:
        values = _issue_values(
            topic="경제·투자",
            headline=self._LIVE_HEADLINE,
            summary=self._LIVE_SUMMARY,
        )
        self.assertIn("FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY", values)

    def test_live_glossary_definition_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY",
        ):
            validate_html(_story_html(
                topic="경제·투자",
                headline=self._LIVE_HEADLINE,
                summary=self._LIVE_SUMMARY,
            ))

    def test_actual_exchange_rate_move_remains_material(self) -> None:
        assessment = _material(
            "원·달러 환율이 6.1원 내린 1386.5원에 마감했다.",
            subject="원·달러 환율",
            action="6.1원 내린 1386.5원에 마감했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_attributed_concrete_rate_forecast_remains_material(self) -> None:
        assessment = _material(
            "BNP파리바는 한국은행이 기준금리를 동결할 것으로 내다봤다.",
            subject="BNP파리바",
            action="한국은행이 기준금리를 동결할 것으로 내다봤다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_actual_kpop_release_and_showcase_remain_material(self) -> None:
        assessment = _material(
            "튜이드는 첫 EP를 발매하고 데뷔 쇼케이스를 개최했다.",
            subject="튜이드",
            action="첫 EP를 발매하고 데뷔 쇼케이스를 개최했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)


class Live209TrendStateRegressions(unittest.TestCase):
    _LIVE_HEADLINE = (
        "트럼프, 데이터센터 AI 부 창출 필수성 주장과 공화당 내부 논란"
    )
    _LIVE_SUMMARY = (
        "도널드 트럼프 대통령이 데이터센터가 AI 산업에 필수적이며 막대한 부를 "
        "창출한다고 주장했다. 공화당 내부에서도 데이터센터 설립에 반대하는 "
        "후보들이 늘고 있다."
    )

    def test_unquantified_candidate_trend_is_not_material_event(self) -> None:
        text = "공화당 내부에서도 데이터센터 설립에 반대하는 후보들이 늘고 있다."
        assessment = _material(
            text,
            subject="공화당 내부에서도 데이터센터 설립에 반대하는 후보들",
            action="늘고 있다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,),
        )

    def test_live_statement_plus_trend_fails_shared_visible_contract(self) -> None:
        values = _issue_values(
            topic="AI·테크",
            headline=self._LIVE_HEADLINE,
            summary=self._LIVE_SUMMARY,
        )
        self.assertIn("FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY", values)

    def test_live_statement_plus_trend_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY",
        ):
            validate_html(_story_html(
                topic="AI·테크",
                headline=self._LIVE_HEADLINE,
                summary=self._LIVE_SUMMARY,
            ))

    def test_named_candidate_policy_statement_remains_material(self) -> None:
        assessment = _material(
            "마이크 로저스는 데이터센터 건설을 1년간 유예하는 조치를 지지한다고 밝혔다.",
            subject="마이크 로저스",
            action="데이터센터 건설을 1년간 유예하는 조치를 지지한다고 밝혔다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_quantified_current_change_remains_material(self) -> None:
        assessment = _material(
            "반도체 수출은 8월에 12% 증가했다.",
            subject="반도체 수출",
            action="8월에 12% 증가했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)


class Live209RelativePastSportsRegressions(unittest.TestCase):
    _LIVE_HEADLINE = "한화 이글스 김서현, 지난 시즌 마무리 투수 기록"
    _LIVE_SUMMARY = (
        "한화 이글스에 따르면 김서현은 지난해 데뷔 후 처음으로 마무리 보직을 "
        "맡아 69경기 66이닝 동안 2승 4패 33세이브 2홀드, 평균자책점 3.14를 "
        "기록했다."
    )
    _SOURCE_SENTENCE = (
        "김서현은 지난해 처음 마무리를 맡아 69경기(66이닝) 2승 4패 "
        "33세이브 2홀드 평균자책점 3.14를 기록했다."
    )

    def test_live_previous_season_stat_is_stale_material_event(self) -> None:
        assessment = _material(
            self._SOURCE_SENTENCE,
            subject="김서현",
            action=(
                "지난해 처음 마무리를 맡아 69경기(66이닝) 2승 4패 "
                "33세이브 2홀드 평균자책점 3.14를 기록했다"
            ),
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.STALE_EXPLICIT_PAST_EVENT,),
        )

    def test_live_previous_season_stat_fails_shared_visible_contract(self) -> None:
        values = _issue_values(
            topic="KBO·한화 이글스",
            headline=self._LIVE_HEADLINE,
            summary=self._LIVE_SUMMARY,
        )
        self.assertIn("FEED_QUALITY_STALE_DATED_CONTEXT", values)

    def test_live_previous_season_stat_fails_artifact_validator(self) -> None:
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_STALE_DATED_CONTEXT"):
            validate_html(_story_html(
                topic="KBO·한화 이글스",
                headline=self._LIVE_HEADLINE,
                summary=self._LIVE_SUMMARY,
            ))

    def test_since_last_year_current_exchange_rate_move_remains_visible(self) -> None:
        self.assertFalse(_issue_values(
            topic="경제·투자",
            headline="원·달러 환율 11개월 만의 최저치 기록",
            summary=(
                "원·달러 환율이 지난해 9월 이후 11개월 만에 가장 낮은 수준으로 "
                "하락했다."
            ),
        ))

    def test_last_year_comparison_with_current_game_remains_visible(self) -> None:
        self.assertFalse(_issue_values(
            topic="KBO·한화 이글스",
            headline="한화 김서현, LG전 1이닝 무실점",
            summary=(
                "김서현은 지난해보다 안정된 제구로 23일 LG전에서 1이닝 "
                "무실점을 기록했다."
            ),
        ))

    def test_current_hanwha_record_remains_visible(self) -> None:
        self.assertFalse(_issue_values(
            topic="KBO·한화 이글스",
            headline="한화, 최근 10경기 2승 8패 기록",
            summary="한화는 최근 10경기에서 2승 8패의 성적을 거두었다.",
        ))


class Live209UnsupportedAttributionRegressions(unittest.TestCase):
    def test_generated_attribution_absent_from_cited_evidence_is_rejected(self) -> None:
        request = _request(
            Live209RelativePastSportsRegressions._SOURCE_SENTENCE,
            subject="김서현",
            action=(
                "지난해 처음 마무리를 맡아 69경기(66이닝) 2승 4패 "
                "33세이브 2홀드 평균자책점 3.14를 기록했다"
            ),
        )
        draft = GeneratedDraft(
            event_id=request.event.event_id,
            headline="김서현 지난 시즌 마무리 기록",
            summary=(
                "한화 이글스에 따르면 김서현은 지난해 처음 마무리를 맡아 "
                "69경기 66이닝 동안 2승 4패 33세이브 2홀드, 평균자책점 "
                "3.14를 기록했다."
            ),
            evidence_ids=request.evidence_ids,
        )
        report = validate_preservation(request, draft)
        self.assertFalse(report.accepted)
        self.assertIn(
            "novel_attribution",
            {issue.code.value for issue in report.issues},
        )

    def test_literal_institutional_attribution_remains_preserved(self) -> None:
        source = "한화 이글스에 따르면 김서현은 23일 LG전에서 1이닝 무실점을 기록했다."
        request = _request(
            source,
            subject="김서현",
            action="23일 LG전에서 1이닝 무실점을 기록했다",
        )
        draft = GeneratedDraft(
            event_id=request.event.event_id,
            headline="한화 김서현, LG전 1이닝 무실점",
            summary=source,
            evidence_ids=request.evidence_ids,
        )
        self.assertTrue(validate_preservation(request, draft).accepted)


if __name__ == "__main__":
    unittest.main()
