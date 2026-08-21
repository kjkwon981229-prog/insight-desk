from __future__ import annotations

import unittest

from insight_desk.domain.models import EvidenceType, NewsItem, Topic
from insight_desk.pipeline.clustering import StoryCluster
from insight_desk.pipeline.editorial import assess_event
from insight_desk.pipeline.synthesis import synthesize_cluster


def _item(
    evidence_id: str,
    topic_id: str,
    title: str,
    summary: str,
    url: str,
    *,
    enriched: bool = False,
) -> NewsItem:
    provenance = (EvidenceType.SEARCH_SNIPPET,)
    if enriched:
        provenance += (EvidenceType.ENRICHED_METADATA,)
    return NewsItem(
        evidence_id=evidence_id,
        topic_id=topic_id,
        query="KBO" if topic_id == "kbo_hanwha" else "가요계",
        title=title,
        summary=summary,
        original_url=url,
        naver_url="",
        canonical_url=url,
        published_at="2026-08-21T18:23:00+09:00",
        source_domain=url.split('/')[2],
        content_hash=evidence_id,
        score=70.0,
        metadata_title=title if enriched else "",
        metadata_description=summary if enriched else "",
        provenance=provenance,
        matched_topic_ids=(topic_id,),
        retrieval_channels=("SIM",),
    )


def _kbo_topic() -> Topic:
    return Topic(
        "kbo_hanwha",
        "KBO·한화 이글스",
        True,
        True,
        50,
        ("KBO", "프로야구"),
        candidate_budget=6,
        intent_anchors=("KBO", "프로야구", "한화", "야구"),
        event_terms=("경기", "승리", "선발", "트레이드", "일정"),
    )


def _kpop_topic() -> Topic:
    # Mirror config/topics.json so the regression cannot pass by injecting a
    # test-only chart or artist signal.
    return Topic(
        "kpop",
        "엔터·음악·K-POP",
        True,
        False,
        70,
        ("K-POP", "HYBE", "음원 차트", "음반 시장"),
        candidate_budget=40,
        intent_anchors=(
            "K-POP", "케이팝", "HYBE", "하이브", "SM", "JYP", "YG", "가수", "그룹",
            "앨범", "음원", "차트", "음악방송", "음악중심", "공연", "콘서트", "컴백", "데뷔",
            "블랙핑크", "BTS", "아이브", "뉴진스", "세븐틴", "트로트",
        ),
        event_terms=(
            "발표", "공개", "앨범", "음원", "차트", "컴백", "데뷔", "공연", "콘서트", "수상",
            "계약", "매출", "음반", "기록",
        ),
    )


class LiveResidualRegressionTests(unittest.TestCase):
    def test_discussion_of_expansion_plan_is_not_industry_change(self) -> None:
        item = _item(
            "sportschosun-kbo-discussion",
            "kbo_hanwha",
            '日야구 고위 관계자 KBO 방문, 허구연 총재와 "야구 인기 확대방안" 논의',
            "20일 KBO를 방문했다. 구리야마 히데키 닛폰햄 CBO는 허구연 총재와 야구 인기 확대 방안을 논의했다.",
            "https://www.sportschosun.com/baseball/2026-08-21/202608210100126560008034",
        )
        assessment = assess_event(StoryCluster("kbo_hanwha", (item,)), _kbo_topic())
        self.assertEqual(assessment.event_type, "OTHER")
        self.assertFalse(assessment.passed)

    def test_historical_wbc_championship_credential_is_not_a_current_sports_result(self) -> None:
        item = _item(
            "sportschosun-wbc-champion-manager-visit",
            "kbo_hanwha",
            'WBC 우승 감독의 KBO 방문, 허구연 총재와 "야구 인기 확대방안" 논의',
            "20일 KBO를 방문했다. 구리야마 히데키 닛폰햄 CBO는 허구연 총재와 야구 인기 확대 방안을 논의했다.",
            "https://www.sportschosun.com/baseball/2026-08-21/202608210100126560008034",
            enriched=True,
        )
        assessment = assess_event(StoryCluster("kbo_hanwha", (item,)), _kbo_topic())
        self.assertEqual(assessment.event_type, "OTHER")
        self.assertFalse(assessment.passed)

    def test_comeback_date_is_not_absorbed_into_subject_or_repeated(self) -> None:
        item = _item(
            "kwon-eunbi-comeback",
            "kpop",
            "권은비, 9월 3일 가요계 컴백 확정…소속사 이적 후 첫 귀환(공식)",
            "가수 권은비가 약 1년 4개월 만에 신곡을 발매한다. 소속사 RBW는 20일 공식 SNS를 통해 권은비의 새 디지털 싱글 '데자부(DEJAVU)' 로고 모션을 공개하고 9월 3일 컴백 소식을 알렸다.",
            "http://www.joynews24.com/view/1996925",
            enriched=True,
        )
        cluster = StoryCluster("kpop", (item,))
        event = assess_event(cluster, _kpop_topic())
        headline, summary, _, _, facts, _ = synthesize_cluster(
            cluster,
            topic_name="엔터·음악·K-POP",
            trend_metrics=(),
            event_type_override=event.event_type,
            event_signature_override=event.canonical_event.event_signature if event.canonical_event else "",
            canonical_event_override=event.canonical_event,
        )
        compact_headline = headline.replace(" ", "")
        compact_summary = summary.replace(" ", "")
        self.assertEqual(event.event_type, "SCHEDULED_EVENT")
        self.assertEqual(facts.subject, "권은비")
        self.assertEqual(compact_headline.count("9월3일"), 1)
        self.assertEqual(compact_summary.count("9월3일"), 1)
        self.assertEqual(summary, "권은비의 컴백은 9월3일로 예정돼 있다.")

    # Exact 2026-08-21 live recall miss: a bounded committee launch is material.
    def test_kbo_committee_launch_is_a_bound_announcement(self) -> None:
        source_summary = "KBO는 21일 한국야구 명예의 전당 선정위원회를 공식 출범했다고 밝혔다."
        item = _item(
            "kbo-hall-of-fame-committee-launch",
            "kbo_hanwha",
            "KBO, 한국야구 명예의 전당 선정위원회 출범",
            source_summary,
            "https://www.yna.co.kr/view/AKR20260821144000007?input=1195m",
            enriched=True,
        )
        cluster = StoryCluster("kbo_hanwha", (item,))
        event = assess_event(cluster, _kbo_topic())
        self.assertEqual(event.event_type, "ANNOUNCEMENT")
        self.assertTrue(event.passed)
        self.assertIsNotNone(event.canonical_event)
        assert event.canonical_event is not None
        self.assertEqual(event.canonical_event.subject, "KBO")
        self.assertEqual(event.canonical_event.action, "출범")
        self.assertEqual(event.canonical_event.object, "한국야구 명예의 전당 선정위원회")

        headline, summary, _, _, facts, _ = synthesize_cluster(
            cluster,
            topic_name="KBO·한화 이글스",
            trend_metrics=(),
            event_type_override=event.event_type,
            event_signature_override=event.canonical_event.event_signature,
            canonical_event_override=event.canonical_event,
        )
        self.assertEqual(headline, "KBO, 한국야구 명예의 전당 선정위원회 출범")
        self.assertEqual(summary, source_summary)
        self.assertEqual(facts.subject, "KBO")
        self.assertEqual(facts.action, "출범")
        self.assertEqual(facts.object, "한국야구 명예의 전당 선정위원회")

    # Exact 2026-08-21 human-audit P1: the chart/platform name must not be
    # absorbed into the song/entity subject.
    def test_bigbang_song_chart_platform_is_not_absorbed_into_subject(self) -> None:
        item = _item(
            "N074",
            "kpop",
            "빅뱅 신곡 빅 멜론 차트 톱100 차트 1위 유지",
            "빅뱅의 신곡 '빅(BiiiG)'이 멜론 톱100 차트 1위에 올랐다.",
            "https://news.jtbc.co.kr/article/NB12314522?influxDiv=NAVER",
            enriched=True,
        )
        cluster = StoryCluster("kpop", (item,))
        event = assess_event(cluster, _kpop_topic())
        self.assertEqual(event.event_type, "AWARD_CHART")
        self.assertTrue(event.passed)
        self.assertIsNotNone(event.canonical_event)
        assert event.canonical_event is not None
        self.assertIn("빅뱅", event.canonical_event.subject)
        self.assertIn("빅", event.canonical_event.subject)
        self.assertNotIn("멜론", event.canonical_event.subject)
        self.assertNotIn("차트", event.canonical_event.subject)
        self.assertIn("1", event.canonical_event.event_signature)

        headline, summary, _, _, facts, _ = synthesize_cluster(
            cluster,
            topic_name="엔터·음악·K-POP",
            trend_metrics=(),
            event_type_override=event.event_type,
            event_signature_override=event.canonical_event.event_signature,
            canonical_event_override=event.canonical_event,
        )
        self.assertNotIn("신곡 빅 멜론이", summary)
        self.assertIn("빅뱅", summary)
        self.assertIn("빅", summary)
        self.assertIn("1위", summary)
        self.assertNotIn("멜론", facts.subject)
        self.assertNotIn("차트", facts.subject)


if __name__ == "__main__":
    unittest.main()
