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

    def test_context_dependent_ytn_fragment_defers_before_generation(self) -> None:
        text = "여기에 오는 27일 한국은행의 기준금리를 결정에도 관심이 쏠립니다."
        assessment = _material_assessment(
            text,
            subject="한국은행의 기준금리",
            action="결정에도 관심이 쏠립니다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.CONTEXT_DEPENDENT_FRAGMENT,),
        )

    def test_live_dealer_antecedent_fragment_defers(self) -> None:
        text = (
            "이 딜러는 한은의 예상대로 법인세수와 반도체 대기업의 대규모 성과급 지급 등으로 인해 "
            "내년에 수요측 물가 압력이 본격화한다면 1차례 인상으로는 긴축의 강도가 충분하지 않을 수 있다고 덧붙였다."
        )
        assessment = _material_assessment(
            text,
            subject="이 딜러",
            action="덧붙였다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(assessment.reasons, (MaterialEventReason.CONTEXT_DEPENDENT_FRAGMENT,))

    def test_live_afterward_fragment_defers(self) -> None:
        text = "이후 KBO는 올해 피치클록 기준을 더 엄격하게 조정했다."
        assessment = _material_assessment(
            text,
            subject="KBO",
            action="피치클록 기준을 더 엄격하게 조정했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(assessment.reasons, (MaterialEventReason.CONTEXT_DEPENDENT_FRAGMENT,))

    def test_live_deictic_economy_situation_fragment_defers(self) -> None:
        text = "채권시장은 한은의 이번 8월 금융통화위원회 기준금리 인상을 위한 사전 포석으로 이번 상황을 해석하고 있다."
        assessment = _material_assessment(
            text,
            subject="채권시장",
            action="이번 상황을 해석하고 있다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(assessment.reasons, (MaterialEventReason.CONTEXT_DEPENDENT_FRAGMENT,))

    def test_live_bare_anniversary_voting_fragment_defers(self) -> None:
        text = "데뷔 20주년을 맞은 가운데 팬들의 꾸준한 투표 참여가 이어지며 여전한 관심과 응원 열기를 보여줬다."
        assessment = _material_assessment(
            text,
            subject="팬들의 꾸준한 투표 참여",
            action="이어지며 여전한 관심과 응원 열기를 보여줬다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(assessment.reasons, (MaterialEventReason.CONTEXT_DEPENDENT_FRAGMENT,))

    def test_live_concessive_normative_ai_statement_defers(self) -> None:
        text = "로봇과 인공지능이 고도화되더라도 여행객을 맞이하고 진정성 있는 경험을 제공하는 주체는 인간이어야 함을 분명히 했다."
        assessment = _material_assessment(
            text,
            subject="여행객을 맞이하고 진정성 있는 경험을 제공하는 주체",
            action="인간이어야 함을 분명히 했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.CONDITIONAL_ANALYTICAL_SCENARIO,),
        )

    def test_concessive_normative_policy_announcement_remains_material(self) -> None:
        text = "AI가 고도화되더라도 인간이 최종 책임 주체이어야 한다는 원칙을 정부가 발표했다."
        assessment = _material_assessment(
            text,
            subject="정부",
            action="발표했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_live_bare_kpop_ranking_fragments_defer(self) -> None:
        cases = (
            ("그룹 아홉이 최고의 루키로 등극했다.", "그룹 아홉", "최고의 루키로 등극했다"),
            ("그룹 유니스가 새로운 최고의 루키로 등극했다.", "그룹 유니스", "새로운 최고의 루키로 등극했다"),
            ("그룹 플레이브가 13주 연속 1위에 올랐다.", "그룹 플레이브", "13주 연속 1위에 올랐다"),
        )
        for text, subject, action in cases:
            with self.subTest(text=text):
                assessment = _material_assessment(text, subject=subject, action=action)
                self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
                self.assertEqual(
                    assessment.reasons,
                    (MaterialEventReason.CONTEXT_DEPENDENT_FRAGMENT,),
                )

    def test_complete_kpop_ranking_context_remains_material(self) -> None:
        text = "K탑스타 투표 최고의 루키(남) 부문에서 아홉이 1위를 차지했다."
        assessment = _material_assessment(
            text,
            subject="아홉",
            action="1위를 차지했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_live_stale_sports_retrospective_defers(self) -> None:
        text = (
            "김재현의 역전 만루포를 뛰어넘은 극적인 장면이 2018년 6월 30일 "
            "한화생명이글스파크에서 열린 롯데 자이언츠와 한화 이글스 경기에서 나왔다."
        )
        assessment = _material_assessment(
            text,
            subject="극적인 장면",
            action="경기에서 나왔다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.STALE_SPORTS_RETROSPECTIVE,),
        )

    def test_context_dependent_summary_fails_product_gate(self) -> None:
        summaries = (
            "여기에 오는 27일 한국은행의 기준금리를 결정에도 관심이 쏠립니다.",
            "이 딜러는 내년에 수요측 물가 압력이 본격화할 수 있다고 덧붙였다.",
            "이후 KBO는 올해 피치클록 기준을 더 엄격하게 조정했다.",
            "채권시장은 한은의 이번 8월 금융통화위원회 기준금리 인상을 위한 사전 포석으로 이번 상황을 해석하고 있다.",
            "데뷔 20주년을 맞은 가운데 팬들의 꾸준한 투표 참여가 이어지며 여전한 관심과 응원 열기를 보여줬다.",
            "그룹 아홉이 최고의 루키로 등극했다.",
            "그룹 유니스가 새로운 최고의 루키로 등극했다.",
            "그룹 플레이브가 13주 연속 1위에 올랐다.",
        )
        for summary in summaries:
            with self.subTest(summary=summary):
                with self.assertRaisesRegex(ValueError, "FEED_QUALITY_CONTEXT_DEPENDENT_SUMMARY"):
                    validate_html(
                        _story_html(
                            headline="독립 문맥 검증용 제목",
                            summary=summary,
                        )
                    )

    def test_concessive_normative_ai_summary_fails_product_gate(self) -> None:
        summary = "로봇과 인공지능이 고도화되더라도 여행객을 맞이하고 진정성 있는 경험을 제공하는 주체는 인간이어야 함을 분명히 했다."
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_CONDITIONAL_ANALYTICAL_SUMMARY"):
            validate_html(
                _story_html(
                    headline="여행 맞이 주체, 인간이 정수임",
                    summary=summary,
                )
            )

    def test_hanwha_topic_rejects_generic_kbo_visible_cards(self) -> None:
        cases = (
            (
                "가을 야구 진출 경쟁 가열",
                "프로야구가 가을 야구 진출 티켓을 두고 더욱 뜨거운 경쟁을 이어가고 있다고 전했다.",
            ),
            (
                "키움, 김재현 끝내기 만루홈런으로 KIA전 8-7 승리",
                "23일 서울 고척스카이돔에서 열린 2026 신한SOL KBO리그 KIA와의 홈경기에서 키움이 김재현의 끝내기 만루홈런을 앞세워 8-7로 승리했다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(headline=headline):
                with self.assertRaisesRegex(ValueError, "FEED_QUALITY_TOPIC_BINDING"):
                    validate_html(_story_html(headline=headline, summary=summary))

    def test_stale_sports_retrospective_fails_product_gate(self) -> None:
        summary = (
            "김재현의 역전 만루포를 뛰어넘은 극적인 장면이 2018년 6월 30일 "
            "한화생명이글스파크에서 열린 롯데 자이언츠와 한화 이글스 경기에서 나왔다."
        )
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_STALE_SPORTS_RETROSPECTIVE"):
            validate_html(
                _story_html(
                    headline="과거 경기 장면",
                    summary=summary,
                )
            )

    def test_non_event_hanwha_analysis_judgment_defers(self) -> None:
        text = "한화 이글스의 올 시즌 부진은 단순히 선수들의 부상이나 경기력 저하만으로 설명하기 어렵다."
        assessment = _material_assessment(
            text,
            subject="한화 이글스의 올 시즌 부진",
            action="단순히 선수들의 부상이나 경기력 저하만으로 설명하기 어렵다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(
            assessment.reasons,
            (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,),
        )

    def test_non_event_hanwha_analysis_fails_product_gate(self) -> None:
        summary = "한화 이글스의 올 시즌 부진은 단순히 선수들의 부상이나 경기력 저하만으로 설명하기 어렵다."
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY"):
            validate_html(
                _story_html(
                    headline="올 시즌 부진은 단순히 선수들의 부상이나 경기력 저하만으로 설명하기 어렵다",
                    summary=summary,
                )
            )

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
