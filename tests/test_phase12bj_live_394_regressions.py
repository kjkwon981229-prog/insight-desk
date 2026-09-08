from __future__ import annotations

from datetime import datetime, timezone
import unittest

from insight_desk.core import CandidateEvent, EvidenceField, EvidenceSpan, EventFact
from insight_desk.generation import GeneratedDraft, GenerationRequest, PreservationIssueCode, validate_preservation
from insight_desk.story_admission import StoryAdmissionReason, StoryAdmissionStage, evaluate_story_admission


NOW = datetime(2026, 8, 26, 13, 5, tzinfo=timezone.utc)


def visible(*, topic: str, headline: str, summary: str):
    return evaluate_story_admission(
        topic=topic,
        headline=headline,
        summary=summary,
        source_text=summary,
        stage=StoryAdmissionStage.VISIBLE,
        now=NOW,
    )


def request_for(*, event_id: str, topic_id: str, source: str, subject: str, action: str) -> GenerationRequest:
    evidence_id = f"ev:{event_id}"
    article_id = f"article:{event_id}"
    fact_id = f"fact:{event_id}"
    span = EvidenceSpan(
        evidence_id=evidence_id,
        article_id=article_id,
        field=EvidenceField.BODY,
        start=0,
        end=len(source),
        text=source,
    )
    fact = EventFact(
        fact_id=fact_id,
        subject=subject,
        action=action,
        evidence_ids=(evidence_id,),
    )
    event = CandidateEvent(
        event_id=event_id,
        topic_id=topic_id,
        fact_ids=(fact_id,),
        article_ids=(article_id,),
    )
    return GenerationRequest(
        event=event,
        facts={fact_id: fact},
        evidence={evidence_id: span},
    )


class Live394GenericLegislatorIdentityRegressions(unittest.TestCase):
    def test_live_surname_only_legislator_is_not_standalone_identity(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="김 의원, AI 합성 '디지털 레플리카' 규제 법안 발의",
            summary=(
                "김 의원은 AI 기술을 악용한 유명인 얼굴·목소리 합성 및 허위 광고를 규제하기 위해 "
                "'부정경쟁방지 및 영업비밀보호에 관한 법률 일부개정법률안'을 대표발의했다고 26일 밝혔다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_generalized_surname_only_legislator_is_not_standalone_identity(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="박 의원, AI 허위광고 규제 법안 발의",
            summary="박 의원은 26일 AI 합성 허위광고를 규제하는 법률 개정안을 대표발의했다고 밝혔다.",
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_full_legislator_name_remains_publishable(self) -> None:
        decision = visible(
            topic="AI·테크",
            headline="김성원 의원, AI 합성 '디지털 레플리카' 규제 법안 발의",
            summary="김성원 의원은 26일 AI 합성 유명인 초상·음성 악용을 규제하는 법률 개정안을 대표발의했다고 밝혔다.",
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live394FractionalSportsActorLossRegressions(unittest.TestCase):
    def test_live_fractional_innings_headline_cannot_drop_pitcher_actor(self) -> None:
        decision = visible(
            topic="KBO·한화 이글스",
            headline=(
                "26일 인천 SSG랜더스필드에서 열린 2026 신한 SOL KBO리그 한화 이글스와의 홈 경기에 "
                "선발 등판해 5⅓이닝 동안 89개의 공을 던지며 2피안타 4사사구 2탈삼진 무실점을 기록했다"
            ),
            summary=(
                "최민준은 26일 인천 SSG랜더스필드에서 열린 2026 신한 SOL KBO리그 한화 이글스와의 홈 경기에 "
                "선발 등판해 5⅓이닝 동안 89개의 공을 던지며 2피안타 4사사구 2탈삼진 무실점을 기록했다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_generalized_fractional_innings_headline_cannot_drop_pitcher_actor(self) -> None:
        decision = visible(
            topic="KBO·한화 이글스",
            headline=(
                "26일 대전 한화생명 볼파크에서 열린 KBO리그 홈 경기에 선발 등판해 "
                "6⅔이닝 동안 4피안타 8탈삼진 무실점을 기록했다"
            ),
            summary=(
                "한화 투수 김민수는 26일 대전 한화생명 볼파크에서 열린 KBO리그 홈 경기에 선발 등판해 "
                "6⅔이닝 동안 4피안타 8탈삼진 무실점을 기록했다."
            ),
        )
        self.assertFalse(decision.accepted)
        self.assertIn(StoryAdmissionReason.STANDALONE_COMPLETENESS, decision.reasons)

    def test_fractional_innings_with_explicit_pitcher_actor_remains_publishable(self) -> None:
        decision = visible(
            topic="KBO·한화 이글스",
            headline=(
                "26일 최민준은 인천 SSG랜더스필드에서 열린 KBO리그 한화 이글스와의 홈 경기에 선발 등판해 "
                "5⅓이닝 2피안타 2탈삼진 무실점을 기록했다"
            ),
            summary=(
                "최민준은 26일 인천 SSG랜더스필드에서 열린 KBO리그 한화 이글스와의 홈 경기에 선발 등판해 "
                "5⅓이닝 2피안타 2탈삼진 무실점을 기록했다."
            ),
        )
        self.assertTrue(decision.accepted, decision.reasons)


class Live394NovelReportingAttributionRegressions(unittest.TestCase):
    def test_live_game_result_cannot_invent_club_side_reporting_actor(self) -> None:
        source = (
            "이숭용 감독이 이끄는 SSG는 26일 인천SSG랜더스필드에서 열린 2026 신한 SOL KBO리그 "
            "한화 이글스와의 정규시즌 13차전에서 6-1로 승리하며 2연승을 달렸다."
        )
        item = request_for(
            event_id="event:live394-ssg",
            topic_id="kbo_hanwha",
            source=source,
            subject="SSG",
            action="한화 이글스와의 정규시즌 13차전에서 6-1로 승리하며 2연승을 달렸다",
        )
        draft = GeneratedDraft(
            event_id=item.event.event_id,
            headline="SSG, 한화전 승리로 2연승 및 위닝시리즈 확보",
            summary=(
                "26일 인천SSG랜더스필드에서 열린 2026 신한 SOL KBO리그 한화 이글스와의 정규시즌 13차전에서 "
                "SSG가 6-1로 승리하며 2연승과 위닝시리즈를 달성했다고 이숭용 감독이 이끄는 구단 측이 밝혔다."
            ),
            evidence_ids=item.evidence_ids,
        )
        report = validate_preservation(item, draft)
        self.assertFalse(report.accepted)
        self.assertIn(PreservationIssueCode.NOVEL_ATTRIBUTION, {issue.code for issue in report.issues})

    def test_generalized_observed_result_cannot_be_promoted_to_invented_reporting(self) -> None:
        source = "A 감독이 이끄는 홈팀은 26일 상대팀을 3-1로 꺾고 2연승을 달렸다."
        item = request_for(
            event_id="event:invented-reporting-generalized",
            topic_id="kbo_hanwha",
            source=source,
            subject="홈팀",
            action="26일 상대팀을 3-1로 꺾고 2연승을 달렸다",
        )
        draft = GeneratedDraft(
            event_id=item.event.event_id,
            headline="홈팀, 상대팀전 3-1 승리",
            summary="홈팀이 26일 상대팀을 3-1로 꺾고 2연승을 달렸다고 A 감독이 이끄는 구단 측이 밝혔다.",
            evidence_ids=item.evidence_ids,
        )
        report = validate_preservation(item, draft)
        self.assertFalse(report.accepted)
        self.assertIn(PreservationIssueCode.NOVEL_ATTRIBUTION, {issue.code for issue in report.issues})

    def test_source_supported_reporting_actor_remains_accepted(self) -> None:
        source = "홈팀 구단 측은 26일 상대팀을 3-1로 꺾고 2연승을 달렸다고 밝혔다."
        item = request_for(
            event_id="event:supported-reporting-positive",
            topic_id="kbo_hanwha",
            source=source,
            subject="홈팀 구단 측",
            action="26일 상대팀을 3-1로 꺾고 2연승을 달렸다고 밝혔다",
        )
        draft = GeneratedDraft(
            event_id=item.event.event_id,
            headline="홈팀, 상대팀전 3-1 승리",
            summary=source,
            evidence_ids=item.evidence_ids,
        )
        report = validate_preservation(item, draft)
        self.assertTrue(report.accepted, report.issues)


if __name__ == "__main__":
    unittest.main()
