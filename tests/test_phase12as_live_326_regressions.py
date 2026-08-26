from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact, RenderMode
from insight_desk.generation import (
    GeneratedDraft,
    GenerationContractError,
    GenerationRequest,
    validate_generated_actor_preservation,
)
from insight_desk.generation_pipeline import (
    ExtractiveFallbackUnavailable,
    GenerationAttemptKind,
    GenerationAttemptStatus,
    _bounded_source_excerpt,
    generate_with_recovery,
)
from insight_desk.story_admission import (
    StoryAdmissionReason,
    StoryAdmissionStage,
    evaluate_story_admission,
)


NOW = datetime(2026, 8, 26, 2, 30, tzinfo=timezone.utc)


def visible(*, topic: str, headline: str, summary: str):
    return evaluate_story_admission(
        topic=topic,
        headline=headline,
        summary=summary,
        source_text=summary,
        stage=StoryAdmissionStage.VISIBLE,
        now=NOW,
    )


def generation_request(*, subject: str, evidence_text: str) -> GenerationRequest:
    span = EvidenceSpan(
        evidence_id="ev:326",
        article_id="article:326",
        field=EvidenceField.BODY,
        start=0,
        end=len(evidence_text),
        text=evidence_text,
    )
    fact = EventFact(
        fact_id="fact:326",
        subject=subject,
        action="기록했다",
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:326",
        topic_id="ai_tech",
        fact_ids=(fact.fact_id,),
        article_ids=(span.article_id,),
    )
    return GenerationRequest(
        event=event,
        facts={fact.fact_id: fact},
        evidence={span.evidence_id: span},
    )


def generated(*, headline: str, summary: str) -> GeneratedDraft:
    return GeneratedDraft(
        event_id="event:326",
        headline=headline,
        summary=summary,
        evidence_ids=("ev:326",),
    )


class _FixedGenerator:
    def __init__(self, draft: GeneratedDraft):
        self.draft = draft

    def generate(self, request: GenerationRequest) -> GeneratedDraft:
        del request
        return self.draft


class Live326DiscourseCompletenessRegressions(unittest.TestCase):
    def test_live_orphan_metric_demonstrative_is_not_standalone(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="앤스로픽, AI 모델 업무 수치 산출",
            summary="앤스로픽은 AI 모델로 수행할 수 있는 업무 전체를 놓고 이 수치를 산출하고 있다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_paraphrased_orphan_metric_reference_is_not_standalone(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="앤스로픽, AI 업무 자동화 분석",
            summary="앤스로픽은 AI 업무 자동화를 분석하며 해당 비율을 산출했다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_quantified_metric_antecedent_resolves_later_demonstrative(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="앤스로픽, AI 업무 자동화 비율 18% 산출",
            summary=(
                "앤스로픽은 자동화 가능한 업무 비율을 18%로 산출했다. "
                "이 수치는 전체 업무를 기준으로 계산됐다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)

    def test_same_head_antecedent_resolves_generic_demonstrative(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="애플, 신규 AI 모델 공개",
            summary="애플은 신규 AI 모델을 공개했다. 이 모델은 개발자에게 먼저 제공된다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live326GeneratedActorPreservationRegressions(unittest.TestCase):
    EVIDENCE = (
        "엔비디아는 데이터센터 매출이 두 배 이상 증가한 데 힘입어 "
        "7개 분기 만에 가장 빠른 성장 속도를 기록했다."
    )
    ACTORLESS_HEADLINE = "데이터센터 매출 급증에 따른 7개 분기 만의 최대 성장"
    ACTORLESS_SUMMARY = (
        "데이터센터 매출이 두 배 이상 증가한 것에 힘입어 "
        "7개 분기 만에 가장 빠른 성장 속도를 기록했다."
    )

    def test_provider_rewrite_cannot_drop_all_evidence_bound_event_actors(self) -> None:
        request = generation_request(subject="엔비디아", evidence_text=self.EVIDENCE)
        draft = generated(
            headline=self.ACTORLESS_HEADLINE,
            summary=self.ACTORLESS_SUMMARY,
        )
        with self.assertRaises(GenerationContractError):
            validate_generated_actor_preservation(request, draft)

    def test_provider_rewrite_with_named_event_actor_remains_valid(self) -> None:
        request = generation_request(subject="엔비디아", evidence_text=self.EVIDENCE)
        draft = generated(
            headline="엔비디아, 데이터센터 매출 증가로 성장 가속",
            summary=(
                "엔비디아는 데이터센터 매출이 두 배 이상 증가한 데 힘입어 "
                "7개 분기 만에 가장 빠른 성장 속도를 기록했다."
            ),
        )
        validate_generated_actor_preservation(request, draft)

    def test_recovery_boundary_rejects_actorless_alternate_before_publish(self) -> None:
        request = generation_request(subject="엔비디아", evidence_text=self.EVIDENCE)
        actorless = generated(
            headline=self.ACTORLESS_HEADLINE,
            summary=self.ACTORLESS_SUMMARY,
        )
        result = generate_with_recovery(
            request,
            primary=None,
            alternate=_FixedGenerator(actorless),
        )
        self.assertIs(result.render_mode, RenderMode.EXTRACTIVE_FALLBACK)
        self.assertIs(result.attempts[0].kind, GenerationAttemptKind.ALTERNATE)
        self.assertIs(result.attempts[0].status, GenerationAttemptStatus.OUTPUT_CONTRACT_REJECTED)
        self.assertIn("엔비디아", result.draft.combined_text)


class Live326HeadlineAndTemporalRegressions(unittest.TestCase):
    def test_live_date_led_kbo_statline_without_performer_is_not_standalone(self) -> None:
        decision = visible(
            topic="KBO·한화 이글스",
            headline=(
                "25일 인천 SSG랜더스필드에서 열린 ‘2026 신한은행 SOL Bank KBO리그’ "
                "한화 이글스와의 경기에 3번 좌익수로 선발출장해 5타수 2안타 2타점을 기록했다"
            ),
            summary=(
                "에레디아는 25일 인천 SSG랜더스필드에서 열린 ‘2026 신한은행 SOL Bank KBO리그’ "
                "한화 이글스와의 경기에 3번 좌익수로 선발출장해 5타수 2안타 2타점을 기록했다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_named_kbo_performer_statline_remains_standalone(self) -> None:
        decision = visible(
            topic="KBO·한화 이글스",
            headline="에레디아, 25일 한화전 5타수 2안타 2타점",
            summary="에레디아는 25일 한화전에서 5타수 2안타 2타점을 기록했다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)

    def test_previous_season_performance_alone_is_stale_background(self) -> None:
        decision = visible(
            topic="KBO·한화 이글스",
            headline="한화 김서현, 지난 시즌 33세이브 활약",
            summary=(
                "김서현은 지난 시즌 69경기에 등판해 66이닝 동안 2승 4패 2홀드 33세이브, "
                "평균자책점 3.14를 기록하며 한화의 한국시리즈 준우승을 이끌었다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.FRESHNESS, decision.reasons)

    def test_current_event_can_keep_previous_season_background(self) -> None:
        decision = visible(
            topic="KBO·한화 이글스",
            headline="한화 김서현, 26일 1군 복귀",
            summary=(
                "김서현은 26일 한화 1군 엔트리에 복귀했다. "
                "지난 시즌에는 69경기에서 33세이브를 기록했다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


class StructuralPublicationBoundaryRegressions(unittest.TestCase):
    def test_exact_source_boundary_never_treats_interpunct_as_safe_cut(self) -> None:
        source = ("A" * 76) + " 온·오프라인 팬 접점을 확대했다"
        self.assertGreater(len(source), 80)
        try:
            excerpt = _bounded_source_excerpt(source, max_chars=80)
        except ExtractiveFallbackUnavailable:
            return
        self.assertFalse(excerpt.endswith("·"), excerpt)

    def test_renderer_has_no_domain_same_event_authority(self) -> None:
        source = Path("insight_desk/rendering.py").read_text(encoding="utf-8")
        self.assertNotIn("semantic.baseball_identity", source)
        self.assertNotIn("kbo_visible_result_redundant", source)


if __name__ == "__main__":
    unittest.main()
