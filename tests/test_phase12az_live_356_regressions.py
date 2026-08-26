from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact
from insight_desk.generation import (
    GeneratedDraft,
    GenerationContractError,
    GenerationRequest,
    validate_story_admission,
)
from insight_desk.story_admission import (
    StoryAdmissionReason,
    StoryAdmissionStage,
    evaluate_story_admission,
)


NOW = datetime(2026, 8, 26, 5, 20, tzinfo=timezone.utc)


def visible(*, topic: str, headline: str, summary: str):
    return evaluate_story_admission(
        topic=topic,
        headline=headline,
        summary=summary,
        source_text=summary,
        stage=StoryAdmissionStage.VISIBLE,
        now=NOW,
    )


def research_generation_case(*, evidence_text: str) -> tuple[GenerationRequest, GeneratedDraft]:
    span = EvidenceSpan(
        evidence_id="ev:356-research",
        article_id="article:356-research",
        field=EvidenceField.BODY,
        start=0,
        end=len(evidence_text),
        text=evidence_text,
    )
    fact = EventFact(
        fact_id="fact:356-research",
        subject="카운터포인트리서치",
        action="올해 서버용 D램 48%, HBM 9%를 차지할 것으로 전망했다",
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id="event:356-research",
        topic_id="economy",
        fact_ids=(fact.fact_id,),
        article_ids=(span.article_id,),
    )
    request = GenerationRequest(
        event=event,
        facts={fact.fact_id: fact},
        evidence={span.evidence_id: span},
    )
    draft = GeneratedDraft(
        event_id=event.event_id,
        headline="올해 서버용 D램 48%·HBM 9% 점유 전망",
        summary=(
            "카운터포인트리서치에 따르면 올해 세계 D램 출하량 중 서버용 D램은 48%, "
            "고대역폭 메모리(HBM)는 9%를 차지할 것으로 전망된다."
        ),
        evidence_ids=(span.evidence_id,),
    )
    return request, draft


class Live356ProductParentEventRegressions(unittest.TestCase):
    def test_static_product_definition_cannot_replace_current_launch_event(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="크로스마크다운에디터 AI 서비스 활용 솔루션",
            summary=(
                "크로스마크다운에디터는 공공기관과 기업의 AI 서비스 활용을 겨냥한 "
                "문서 작성·가공 솔루션이다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.NON_EVENT_DESCRIPTION, decision.reasons)

    def test_named_current_product_launch_announcement_remains_event(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="지란지교소프트, 크로스마크다운에디터 4분기 출시 발표",
            summary=(
                "지란지교소프트는 26일 크로스마크다운에디터를 올해 4분기 "
                "정식 출시한다고 밝혔다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live356ResearchFreshnessRegressions(unittest.TestCase):
    def test_old_research_evidence_cannot_be_made_current_by_date_free_generation(self) -> None:
        request, draft = research_generation_case(
            evidence_text=(
                "카운터포인트리서치는 지난 6월 29일 공개한 보고서에서 올해 세계 D램 "
                "출하량 중 서버용 D램이 48%, HBM이 9%를 차지할 것으로 전망했다."
            )
        )
        with self.assertRaisesRegex(GenerationContractError, "FRESHNESS"):
            validate_story_admission(request, draft)

    def test_current_research_release_remains_publishable(self) -> None:
        request, draft = research_generation_case(
            evidence_text=(
                "카운터포인트리서치는 26일 공개한 보고서에서 올해 세계 D램 출하량 중 "
                "서버용 D램이 48%, HBM이 9%를 차지할 것으로 전망했다."
            )
        )
        validate_story_admission(request, draft)


class Live356RankingHeadlineRegressions(unittest.TestCase):
    def test_actorless_vote_metric_headline_is_not_standalone(self) -> None:
        decision = visible(
            topic="엔터·음악·K-POP",
            headline=(
                "트로트 가왕 54만5400표, 남자가수 56만8470표, 예능출연자 43만440표, "
                "K-POP KING 45만3630표, 최고미남 44만40표, CF킹 43만9620표로 "
                "6개 부문 TOP3에 들었다"
            ),
            summary=(
                "장민호는 트로트 가왕 54만5400표, 남자가수 56만8470표, "
                "예능출연자 43만440표, K-POP KING 45만3630표, 최고미남 44만40표, "
                "CF킹 43만9620표로 6개 부문 TOP3에 들었다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_named_vote_ranking_headline_remains_standalone(self) -> None:
        decision = visible(
            topic="엔터·음악·K-POP",
            headline="장민호, 6개 투표 부문 TOP3",
            summary="장민호는 26일 집계된 팬 투표에서 6개 부문 TOP3에 들었다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live356AlbumIdentityRegressions(unittest.TestCase):
    def test_tracklist_without_artist_or_album_identity_is_not_standalone(self) -> None:
        decision = visible(
            topic="엔터·음악·K-POP",
            headline="앨범 수록곡 6곡 공개",
            summary=(
                "‘Two Fools’, ‘Stuck’, ‘Bad For You’, ‘Bloody Paradise’, ‘Checkmate’, "
                "‘Highlight’ 등 6곡이 앨범에 수록됐다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_named_current_album_release_with_tracklist_remains_event(self) -> None:
        decision = visible(
            topic="엔터·음악·K-POP",
            headline="엔하이픈, 미니 8집 THE SIN : BLISS 발매",
            summary=(
                "엔하이픈은 26일 미니 8집 'THE SIN : BLISS'를 발매했다. "
                "앨범에는 ‘Two Fools’, ‘Stuck’ 등 6곡이 수록됐다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)

    def test_named_current_tracklist_announcement_remains_event(self) -> None:
        decision = visible(
            topic="엔터·음악·K-POP",
            headline="엔하이픈, THE SIN : BLISS 트랙리스트 공개",
            summary=(
                "엔하이픈은 26일 미니 8집 'THE SIN : BLISS'의 트랙리스트를 공개하고 "
                "수록곡 6곡을 소개했다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


if __name__ == "__main__":
    unittest.main()
