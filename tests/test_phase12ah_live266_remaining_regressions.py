from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import unittest

from insight_desk.core import RawArticle, SourceProvenance
from insight_desk.semantic.facts import FactDraft, FactExtractionRequest
from insight_desk.semantic.material import MaterialEventReason, MaterialEventVerdict, assess_material_event
from insight_desk.semantic.pipeline import SemanticPipeline
from insight_desk.story_admission import StoryAdmissionReason, StoryAdmissionStage, evaluate_story_admission


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class _Token:
    tag: str = "VV"


class _PredicateMorphology:
    def analyze(self, text: str):
        del text
        return (_Token(),)


class ExactSecondSentenceExtractor:
    extractor_id = "exact-second-sentence-fixture"

    def extract(self, request: FactExtractionRequest) -> tuple[FactDraft, ...]:
        marker = "이번 경매를 통해"
        start = request.article.body.index(marker)
        end = len(request.article.body)
        return (
            FactDraft(
                draft_id="second",
                subject="구글",
                action="스피릿항공의 내부 업무 자료를 인수하기로 했다",
                evidence_ids=(request.evidence[0].evidence_id,),
                source_start=start,
                source_end=end,
            ),
        )


class ExactCurrentGoogleExtractor:
    extractor_id = "exact-current-google-fixture"

    def extract(self, request: FactExtractionRequest) -> tuple[FactDraft, ...]:
        marker = "구글은 새 AI 모델을 공개했다."
        start = request.article.body.index(marker)
        return (
            FactDraft(
                draft_id="current",
                subject="구글",
                action="새 AI 모델을 공개했다",
                evidence_ids=(request.evidence[0].evidence_id,),
                source_start=start,
                source_end=start + len(marker),
            ),
        )


def article(body: str, *, article_id: str) -> RawArticle:
    return RawArticle(
        article_id=article_id,
        provenance=SourceProvenance(
            source_id="fixture",
            source_name="fixture",
            url=f"https://example.invalid/{article_id}",
            retrieved_via="fixture",
            fetched_at=NOW,
            published_at=NOW,
        ),
        title="AI 데이터 동향",
        body=body,
        topic_ids=("ai_tech",),
    )


class RemainingLive266VisibleRegressions(unittest.TestCase):
    def decide(self, headline: str, summary: str):
        return evaluate_story_admission(
            topic="경제·투자" if "금리" in headline else "AI·테크",
            headline=headline,
            summary=summary,
            source_text=summary,
            stage=StoryAdmissionStage.VISIBLE,
            now=NOW,
        )

    def test_referential_future_process_cannot_replace_current_poc_event(self) -> None:
        decision = self.decide(
            "한컴 AI 에이전트 PoC 분석",
            "한컴은 이번 PoC를 통해 AI 에이전트가 실제 업무에 적용되는 과정과 효과를 면밀히 분석해 에이전틱 OS 및 산업별 에이전트 모델을 고도화할 계획이다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_current_poc_event_may_keep_future_process_as_background(self) -> None:
        decision = self.decide(
            "한컴·남양유업, AI 에이전트 PoC 업무협약 체결",
            "한컴과 남양유업은 25일 AI 에이전트 PoC 업무협약을 체결했다. 이번 PoC를 통해 적용 효과를 분석해 산업별 에이전트 모델을 고도화할 계획이다.",
        )
        self.assertTrue(decision.accepted)

    def test_unattributed_market_state_is_not_a_daily_event(self) -> None:
        decision = self.decide(
            "기준금리 인상 전 시장금리 상승 현상",
            "기준금리가 오르기 이전부터 시장금리가 상승하는 현상이 나타나고 있다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_forecast_noun_cannot_hide_missing_attribution(self) -> None:
        decision = self.decide(
            "한은의 연속 기준금리 인상 전망과 시장금리 상승",
            "한은이 기준금리를 연이어 인상할 것이라는 전망이 시장금리의 상승세를 강화하고 있다.",
        )
        self.assertFalse(decision.accepted)
        self.assertTrue(
            StoryAdmissionReason.NON_EVENT_DESCRIPTION in decision.reasons
            or StoryAdmissionReason.FORECAST_ATTRIBUTION_STANDALONE_UNRESOLVED in decision.reasons
        )

    def test_attributed_current_rate_survey_remains_accepted(self) -> None:
        decision = self.decide(
            "금투협 조사, 8월 기준금리 동결 전망 79%",
            "금융투자협회가 25일 발표한 조사에서 응답자의 79%가 기준금리 동결을 전망했다. 시장에서는 주택과 가계부채 흐름도 함께 주시하고 있다.",
        )
        self.assertTrue(decision.accepted)


class RemainingLive266TemporalBindingRegressions(unittest.TestCase):
    def test_prior_sentence_date_is_preserved_when_same_event_continues_referentially(self) -> None:
        body = (
            "지난 14일 구글은 스피릿항공 데이터 경매의 최종 낙찰자로 선정됐다. "
            "이번 경매를 통해 구글은 스피릿항공의 내부 업무 자료를 인수하기로 했다."
        )
        result = SemanticPipeline().extract_article(
            article(body, article_id="stale-google"),
            topic_id="ai_tech",
            extractor=ExactSecondSentenceExtractor(),
        )
        self.assertEqual(result.facts[0].event_date, "2026-08-14")

        assessment = assess_material_event(
            result.events[0],
            facts={item.fact_id: item for item in result.facts},
            evidence={item.evidence_id: item for item in result.evidence},
            morphology=_PredicateMorphology(),
            now=NOW,
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertIn(
            assessment.reasons[0],
            (MaterialEventReason.STALE_EXPLICIT_PAST_EVENT, MaterialEventReason.STALE_DATED_CONTEXT),
        )

    def test_unrelated_old_event_from_same_company_does_not_date_current_event(self) -> None:
        body = (
            "지난 14일 구글은 검색 광고 정책을 변경했다. "
            "구글은 새 AI 모델을 공개했다."
        )
        result = SemanticPipeline().extract_article(
            article(body, article_id="current-google"),
            topic_id="ai_tech",
            extractor=ExactCurrentGoogleExtractor(),
        )
        self.assertIsNone(result.facts[0].event_date)
        assessment = assess_material_event(
            result.events[0],
            facts={item.fact_id: item for item in result.facts},
            evidence={item.evidence_id: item for item in result.evidence},
            morphology=_PredicateMorphology(),
            now=NOW,
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)


if __name__ == "__main__":
    unittest.main()
