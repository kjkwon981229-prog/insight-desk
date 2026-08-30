from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import unittest

from insight_desk.core import (
    CandidateEvent,
    EvidenceField,
    EvidenceSpan,
    EventFact,
    RenderMode,
    RenderedBriefing,
    RenderedEntry,
)
from insight_desk.feed_quality import visible_story_issues
from insight_desk.semantic.material import (
    MaterialEventReason,
    MaterialEventVerdict,
    assess_material_event,
)
from insight_desk.ui import build_briefing_view_model, render_briefing_html
from scripts.phase11_daily_production import event_topic_relevant, load_topics
from scripts.validate_feed_artifact import validate_html


@dataclass(frozen=True)
class _Token:
    tag: str = "VV"


class _PredicateMorphology:
    def analyze(self, text: str):
        del text
        return (_Token(),)


def _topic(topic_id: str):
    return next(
        item for item in load_topics(Path("config/topics.json"))
        if item.topic_id == topic_id
    )


def _event(
    *,
    topic_id: str,
    text: str,
    subject: str,
    action: str,
    object_: str | None = None,
):
    span = EvidenceSpan(
        evidence_id=f"evidence:196:{topic_id}",
        article_id=f"article:196:{topic_id}",
        field=EvidenceField.BODY,
        start=0,
        end=len(text),
        text=text,
    )
    fact = EventFact(
        fact_id=f"fact:196:{topic_id}",
        subject=subject,
        action=action,
        object=object_,
        evidence_ids=(span.evidence_id,),
    )
    event = CandidateEvent(
        event_id=f"event:196:{topic_id}",
        topic_id=topic_id,
        fact_ids=(fact.fact_id,),
        article_ids=(span.article_id,),
    )
    return event, {fact.fact_id: fact}, {span.evidence_id: span}


def _material(text: str, *, subject: str, action: str, object_: str | None = None):
    event, facts, evidence = _event(
        topic_id="fixture",
        text=text,
        subject=subject,
        action=action,
        object_=object_,
    )
    return assess_material_event(
        event,
        facts=facts,
        evidence=evidence,
        morphology=_PredicateMorphology(),
    )


def _kbo_relevant(*, text: str, subject: str, action: str, object_: str | None = None) -> bool:
    event, facts, evidence = _event(
        topic_id="kbo_hanwha",
        text=text,
        subject=subject,
        action=action,
        object_=object_,
    )
    return event_topic_relevant(
        event=event,
        facts=facts,
        evidence=evidence,
        topic=_topic("kbo_hanwha"),
    )


def _story_html(
    *,
    topic: str,
    headline: str,
    summary: str,
    source_url: str | None = None,
) -> str:
    source = (
        f'<a class="story-source" href="{source_url}">원문 보기</a>'
        if source_url is not None
        else ""
    )
    return (
        '<!doctype html><html><body>'
        '<article class="story-row" data-event-id="event:196">'
        f'<span class="story-topic">{topic}</span>'
        f'<h3>{headline}</h3>'
        f'<p class="story-summary">{summary}</p>'
        f'{source}'
        '</article></body></html>'
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


class Live196KboCentralityRegressions(unittest.TestCase):
    def test_kbo_attendance_photo_cannot_use_subordinate_hanwha_game_as_direct_binding(self) -> None:
        text = (
            "2026 KBO리그가 3년 연속 1000만 관중 돌파를 앞둔 가운데, "
            "지난 11일 서울 잠실야구장에서 한화 이글스와 두산 베어스의 경기가 진행됐다."
        )
        self.assertFalse(_kbo_relevant(
            text=text,
            subject="2026 KBO리그",
            action=(
                "3년 연속 1000만 관중 돌파를 앞둔 가운데, 지난 11일 서울 잠실야구장에서 "
                "한화 이글스와 두산 베어스의 경기가 진행됐다"
            ),
        ))

    def test_actual_hanwha_attendance_record_remains_directly_bound(self) -> None:
        text = "한화 이글스가 홈 경기에서 시즌 누적 100만 관중을 기록했다."
        self.assertTrue(_kbo_relevant(
            text=text,
            subject="한화 이글스",
            action="홈 경기에서 시즌 누적 100만 관중을 기록했다",
        ))

    def test_actual_hanwha_game_result_remains_directly_bound(self) -> None:
        text = "LG 트윈스가 한화 이글스를 5대 2로 꺾고 승리했다."
        self.assertTrue(_kbo_relevant(
            text=text,
            subject="LG 트윈스",
            action="한화 이글스를 5대 2로 꺾고 승리했다",
        ))


class Live196VisibleStandaloneRegressions(unittest.TestCase):
    def test_generic_company_subject_from_capacity_card_fails_visible_contract(self) -> None:
        values = _issue_values(
            topic="AI·테크",
            headline="육상 발전 여유 0.7GW, 수요 1GW 근접",
            summary=(
                "회사가 육상 발전용으로 돌릴 수 있는 여유 생산능력은 연 0.7GW 수준이지만, "
                "데이터센터를 제외한 육상 발전 수요만 해도 이미 1GW에 근접한 것으로 파악됐다."
            ),
        )
        self.assertIn("FEED_QUALITY_CONTEXT_DEPENDENT_SUMMARY", values)

    def test_incomplete_adnominal_headline_fails_visible_contract(self) -> None:
        values = _issue_values(
            topic="경제·투자",
            headline="금덩어리, 화폐 제조 외형 성장 이끈",
            summary="한국은행 발주를 받아 화폐를 만드는 제조 공기업의 외형 성장을 금덩어리가 이끈 셈이다.",
        )
        self.assertIn("FEED_QUALITY_CONTEXT_DEPENDENT_HEADLINE", values)

    def test_actual_vague_victory_setup_fails_visible_contract(self) -> None:
        values = _issue_values(
            topic="KBO·한화 이글스",
            headline="LG 트윈스가 한화 이글스를 상대로 거둔 이번 승리에는 그냥 지나치기 어려운 장면도 있었다",
            summary="하지만 LG 트윈스가 한화 이글스를 상대로 거둔 이번 승리에는 그냥 지나치기 어려운 장면도 있었다.",
        )
        self.assertTrue({
            "FEED_QUALITY_CONTEXT_DEPENDENT_HEADLINE",
            "FEED_QUALITY_CONTEXT_DEPENDENT_SUMMARY",
            "FEED_QUALITY_HEADLINE_SUMMARY_COLLISION",
        } & values)

    def test_unnamed_two_pitchers_fail_headline_and_summary_standalone_contract(self) -> None:
        values = _issue_values(
            topic="KBO·한화 이글스",
            headline="투수는 지난 20일 한화 이글스전에 나란히 등판했지만 모두 홈런을 허용했다",
            summary="두 투수는 지난 20일 한화 이글스전에 나란히 등판했지만 모두 홈런을 허용했다.",
        )
        self.assertIn("FEED_QUALITY_CONTEXT_DEPENDENT_HEADLINE", values)
        self.assertIn("FEED_QUALITY_CONTEXT_DEPENDENT_SUMMARY", values)

    def test_reporter_byline_metadata_fails_visible_contract(self) -> None:
        values = _issue_values(
            topic="엔터·음악·K-POP",
            headline="튜이드 데뷔 쇼케이스 진행",
            summary=(
                "(톱스타뉴스 최규석 기자) 8월 24일 서울 광진구 예스24라이브홀에서 "
                "튜이드의 데뷔 쇼케이스가 진행됐다."
            ),
        )
        self.assertIn("FEED_QUALITY_VISIBLE_METADATA", values)

    def test_named_company_and_named_sports_subjects_remain_standalone(self) -> None:
        cases = (
            (
                "AI·테크",
                "HD현대중공업, 약 20년 만에 엔진 공장 증설 추진",
                "HD현대중공업은 AI 데이터센터 전력 수요에 대응해 약 20년 만에 엔진 공장 증설을 추진한다.",
            ),
            (
                "KBO·한화 이글스",
                "한화 김서현, LG전 1이닝 무실점",
                "한화 이글스 김서현은 LG전에서 1이닝 무실점을 기록했다.",
            ),
        )
        for topic, headline, summary in cases:
            with self.subTest(headline=headline):
                self.assertFalse(_issue_values(topic=topic, headline=headline, summary=summary))


class Live196MaterialityRegressions(unittest.TestCase):
    def test_gold_bar_explanatory_inference_is_not_material_event(self) -> None:
        assessment = _material(
            "한국은행 발주를 받아 화폐를 만드는 제조 공기업의 외형 성장을 금덩어리가 이끈 셈이다.",
            subject="금덩어리",
            action="외형 성장을 금덩어리가 이끈 셈이다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(assessment.reasons, (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,))

    def test_unattributed_rate_possibility_attention_is_not_material_event(self) -> None:
        assessment = _material(
            "현재 기준금리는 연 2.75%이며 시장에서는 0.25%포인트 인상해 3.0%로 올릴 가능성을 주목하고 있다.",
            subject="시장",
            action="0.25%포인트 인상해 3.0%로 올릴 가능성을 주목하고 있다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(assessment.reasons, (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,))

    def test_corporate_funding_cause_interpretation_is_not_material_event(self) -> None:
        assessment = _material(
            "삼성전자, SK하이닉스 등 반도체 기업을 필두로 수출 대기업들의 자금 집행이 잦아진 영향으로 해석된다.",
            subject="수출 대기업들의 자금 집행",
            action="잦아진 영향으로 해석된다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(assessment.reasons, (MaterialEventReason.NON_EVENT_ANALYTICAL_JUDGMENT,))

    def test_actual_numeric_deposit_turnover_record_remains_material(self) -> None:
        assessment = _material(
            "2분기 국내 예금은행의 예금회전율은 4.9회로 26년 만의 최고치를 기록했다.",
            subject="2분기 국내 예금은행의 예금회전율",
            action="4.9회로 26년 만의 최고치를 기록했다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_attributed_concrete_rate_forecast_remains_material(self) -> None:
        assessment = _material(
            "BNP파리바는 한국은행이 기준금리를 동결할 것으로 내다봤다.",
            subject="BNP파리바",
            action="한국은행이 기준금리를 동결할 것으로 내다봤다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.MATERIAL)

    def test_stale_day_only_hanwha_photo_context_is_not_current_event(self) -> None:
        assessment = _material(
            "지난 11일 서울 잠실야구장에서 한화 이글스와 두산 베어스의 경기가 진행됐다.",
            subject="한화 이글스와 두산 베어스의 경기",
            action="진행됐다",
        )
        self.assertIs(assessment.verdict, MaterialEventVerdict.DEFER)
        self.assertEqual(assessment.reasons, (MaterialEventReason.STALE_DATED_CONTEXT,))


class Live196ArtifactValidatorRegressions(unittest.TestCase):
    def test_all_three_explanatory_visible_summaries_fail_validator(self) -> None:
        cases = (
            (
                "금덩어리 매출 영향",
                "한국은행 발주를 받아 화폐를 만드는 제조 공기업의 외형 성장을 금덩어리가 이끈 셈이다.",
            ),
            (
                "기준금리 2.75% 현황",
                "현재 기준금리는 연 2.75%이며 시장에서는 0.25%포인트 인상해 3.0%로 올릴 가능성을 주목하고 있다.",
            ),
            (
                "수출 대기업 자금 집행 잦아진 영향",
                "삼성전자, SK하이닉스 등 반도체 기업을 필두로 수출 대기업들의 자금 집행이 잦아진 영향으로 해석된다.",
            ),
        )
        for headline, summary in cases:
            with self.subTest(headline=headline):
                with self.assertRaisesRegex(ValueError, "FEED_QUALITY_NON_EVENT_ANALYTICAL_SUMMARY"):
                    validate_html(_story_html(
                        topic="경제·투자",
                        headline=headline,
                        summary=summary,
                    ))

    def test_source_audit_requires_same_source_link_in_visible_card(self) -> None:
        audit = {
            "rendered_sources": [
                {
                    "event_id": "event:196",
                    "source_group_key": "source:196",
                    "content_sha256": "content:196",
                    "source_url": "https://example.com/news/live-196",
                }
            ]
        }
        with self.assertRaisesRegex(ValueError, "FEED_QUALITY_SOURCE_LINK_MISSING"):
            validate_html(
                _story_html(
                    topic="AI·테크",
                    headline="HD현대중공업 엔진 공장 증설 추진",
                    summary="HD현대중공업은 AI 데이터센터 수요에 대응해 엔진 공장 증설을 추진한다.",
                ),
                source_audit=audit,
            )

    def test_ui_renders_explicit_source_mapping_as_safe_visible_link(self) -> None:
        briefing = RenderedBriefing(
            briefing_id="briefing:196",
            generated_at=datetime(2026, 8, 24, 17, 40, tzinfo=timezone.utc),
            entries=(
                RenderedEntry(
                    event_id="event:196",
                    headline="HD현대중공업 엔진 공장 증설 추진",
                    summary="HD현대중공업은 AI 데이터센터 수요에 대응해 엔진 공장 증설을 추진한다.",
                    claim_ids=("claim:196:headline", "claim:196:summary"),
                    render_mode=RenderMode.GENERATED,
                ),
            ),
        )
        view = build_briefing_view_model(
            briefing,
            topic_by_event={"event:196": "AI·테크"},
            source_by_event={"event:196": "https://example.com/news/live-196"},
        )
        html = render_briefing_html(view)
        self.assertIn(
            '<a class="story-source" href="https://example.com/news/live-196" '
            'target="_blank" rel="noopener noreferrer">원문 보기</a>',
            html,
        )


if __name__ == "__main__":
    unittest.main()
