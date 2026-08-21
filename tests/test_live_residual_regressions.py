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
    return Topic(
        "kpop",
        "엔터·음악·K-POP",
        True,
        True,
        50,
        ("가요계", "K-POP"),
        candidate_budget=6,
        intent_anchors=("가수", "K-POP", "가요계", "컴백"),
        event_terms=("컴백", "발매", "신곡", "싱글", "공연", "콘서트"),
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


if __name__ == "__main__":
    unittest.main()
