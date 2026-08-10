from __future__ import annotations

import json
import unittest
from pathlib import Path

from insight_desk.domain.models import EvidenceType, NewsItem, TrendMetric
from insight_desk.pipeline.clustering import StoryCluster
from insight_desk.pipeline.synthesis import synthesize_cluster


def _item(
    evidence_id: str,
    title: str,
    summary: str,
    domain: str,
    *,
    provenance: tuple[EvidenceType, ...] = (EvidenceType.SEARCH_SNIPPET,),
) -> NewsItem:
    return NewsItem(
        evidence_id,
        "topic",
        "query",
        title,
        summary,
        f"https://{domain}/story/{evidence_id}",
        "",
        f"https://{domain}/story/{evidence_id}",
        "2026-08-09T08:00:00+09:00",
        domain,
        evidence_id,
        10.0,
        provenance=provenance,
    )


class SynthesisTests(unittest.TestCase):
    def test_representative_case_matrix_is_safe_to_synthesize(self) -> None:
        cases = json.loads(
            (Path(__file__).resolve().parents[1] / "fixtures/synthesis_cases.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(cases), 10)
        for case_name, case in cases.items():
            items = []
            for index, raw in enumerate(case["items"], 1):
                provenance = (EvidenceType.SEARCH_SNIPPET,)
                if raw.get("official"):
                    provenance += (EvidenceType.OFFICIAL_SOURCE,)
                items.append(
                    _item(
                        f"{case_name}-{index}",
                        raw["title"],
                        raw.get("summary", ""),
                        raw["domain"],
                        provenance=provenance,
                    )
                )
            _, summary, _, _, _, _ = synthesize_cluster(
                StoryCluster("topic", tuple(items)), topic_name=case["topic"], trend_metrics=()
            )
            self.assertNotIn("...", summary, case_name)
            self.assertNotIn("…", summary, case_name)

    def test_statistic_is_fact_first_and_preserves_key_number(self) -> None:
        cluster = StoryCluster(
            "topic",
            (
                _item(
                    "N001",
                    "올해 원달러 환율 변동폭 47원 금융위기 후 최고",
                    "한국은행 통계를 인용해 월평균 변동폭이 47원으로 집계됐다고 전했다.",
                    "bok.or.kr",
                ),
                _item(
                    "N002",
                    "원달러 월평균 변동폭 47원 금융위기 이후 최대",
                    "월평균 수치가 47원이라는 같은 흐름을 전했다.",
                    "news.example",
                ),
            ),
        )
        headline, summary, evidence, watch, facts, certainty = synthesize_cluster(
            cluster, topic_name="경제", trend_metrics=()
        )
        self.assertEqual(facts.event_type, "MARKET")
        self.assertIn("47원", headline)
        self.assertIn("47원", summary)
        self.assertNotIn("...", summary)
        self.assertNotIn("…", summary)
        self.assertIn("공식 자료", evidence)
        self.assertEqual(certainty.value, "confirmed")
        self.assertEqual(watch, ("다음 월간 통계와 변동폭",))

    def test_release_summary_preserves_subject_date_and_release_fact(self) -> None:
        cluster = StoryCluster(
            "topic",
            (
                _item(
                    "bigbang-release",
                    "빅뱅, 19일 데뷔 20주년 기념 BiiG 발매",
                    "빅뱅이 19일 신곡을 발표한다고 전했다.",
                    "music.example",
                ),
            ),
        )
        headline, summary, _, _, facts, _ = synthesize_cluster(cluster, topic_name="K-POP", trend_metrics=())
        self.assertIn("발매", headline)
        self.assertIn("빅뱅이", summary)
        self.assertIn("19일", summary)
        self.assertIn("신곡", summary)
        self.assertIn("발매", summary)
        self.assertEqual(facts.date, "19일")

    def test_ndf_quote_preserves_the_full_supported_quote(self) -> None:
        cluster = StoryCluster(
            "topic",
            (
                _item(
                    "N-NDF",
                    "원 · 달러 NDF 1407.2/1407.6원, 8.15원 하락",
                    "원 · 달러 NDF가 하락했다.",
                    "market.example",
                ),
            ),
        )
        _, summary, _, _, facts, _ = synthesize_cluster(cluster, topic_name="경제", trend_metrics=())
        self.assertIn("1407.2", summary)
        self.assertIn("1407.6원", summary)
        self.assertIn("8.15원 하락", summary)
        self.assertIn("1407.2", facts.key_numbers)

    def test_secondary_event_facts_do_not_contaminate_interruption_story(self) -> None:
        cluster = StoryCluster(
            "topic",
            (
                _item(
                    "heat",
                    "KBO 폭염으로 경기 중단",
                    "폭염 영향으로 경기가 중단됐다.",
                    "sports.example",
                ),
                _item(
                    "appearance",
                    "가수 민니, 11일 두산-한화전 시구",
                    "11일 잠실 경기에서 시구한다.",
                    "ent.example",
                ),
            ),
        )
        _, summary, _, _, facts, _ = synthesize_cluster(cluster, topic_name="KBO", trend_metrics=())
        self.assertEqual(facts.event_type, "SPORTS_INTERRUPTION")
        self.assertNotEqual(facts.action, "시구")
        self.assertNotEqual(facts.date, "11일")
        self.assertNotEqual(facts.location, "잠실")
        self.assertNotIn("잠실", summary)

    def test_scheduled_event_extracts_date_and_location(self) -> None:
        cluster = StoryCluster(
            "topic",
            (
                _item("N003", "민니 11일 두산-한화전 시구", "11일 잠실야구장에서 시구 예정이다.", "sports.example"),
                _item("N004", "민니, 11일 잠실 두산-한화전 시구", "행사 일정과 장소를 전했다.", "ent.example"),
            ),
        )
        headline, summary, _, watch, facts, _ = synthesize_cluster(cluster, topic_name="문화", trend_metrics=())
        self.assertEqual(facts.event_type, "SPORTS_EVENT")
        self.assertEqual(facts.date, "11일")
        self.assertEqual(facts.location, "잠실")
        self.assertEqual(headline, "민니 11일 시구")
        self.assertIn("11일", summary)
        self.assertIn("잠실", summary)
        self.assertTrue(watch)

    def test_truncated_lead_prefix_preserves_scheduled_event_date(self) -> None:
        item = _item(
            "monsta-truncated-lead",
            "몬스타엑스, 9월 가요계 컴백 확정…'더 페이즈' 발매",
            "그룹 몬스타엑스가 오는 9월 4일 미니 앨범을 발매하며 가요계 컴백을 예고했다. 소속사는 커밍순 영상을...",
            "music.example",
        )
        _, summary, _, _, facts, _ = synthesize_cluster(
            StoryCluster("kpop", (item,)), topic_name="K-POP", trend_metrics=()
        )
        self.assertEqual(facts.date, "9월4일")
        self.assertIn("9월4일", summary)
        self.assertNotIn("9", facts.key_numbers)
        self.assertNotIn("커밍순", summary)

    def test_completed_concert_does_not_turn_publication_date_into_event_date(self) -> None:
        item = _item(
            "yunho-concert-report",
            "동방신기 유노윤호, 마카오 콘서트도 대성황…현지어 소통까지",
            "8월 10일 소속사 SM 엔터테인먼트에 따르면 유노윤호는 8일 마카오 브로드웨이 시어터에서 공연을 진행했다. 이날...",
            "music.example",
        )
        _, summary, _, _, facts, _ = synthesize_cluster(
            StoryCluster("kpop", (item,)), topic_name="K-POP", trend_metrics=()
        )
        self.assertEqual(facts.date, "8일")
        self.assertIn("성황리에 진행됐다", summary)
        self.assertNotIn("8월10일", summary)

    def test_comeback_without_schedule_does_not_invent_a_schedule(self) -> None:
        item = _item(
            "wayv-comeback",
            'WayV, "Vision Wings"로 여덟 번째 미니앨범 컴백',
            "WayV가 새 미니앨범으로 활동을 시작한다. 오늘 오후 6시 전곡 음원이 공개된다...",
            "music.example",
        )
        _, summary, _, _, _, _ = synthesize_cluster(
            StoryCluster("kpop", (item,)), topic_name="K-POP", trend_metrics=()
        )
        self.assertEqual(summary, "WayV의 컴백이 확인됐다.")

    def test_market_headline_does_not_append_a_clipped_change_fragment(self) -> None:
        cluster = StoryCluster(
            "economy",
            (
                _item(
                    "kospi-open",
                    "美증시 상승 마감에 코스피·코스닥 상승 출발",
                    "코스피와 코스닥이 각각 0.76%, 1.11% 상승 출발했다.",
                    "market.example",
                ),
            ),
        )
        headline, _, _, _, _, _ = synthesize_cluster(cluster, topic_name="경제", trend_metrics=())
        self.assertNotIn("마감에 코스피", headline)

    def test_market_strength_preserves_direction_in_headline_and_summary(self) -> None:
        cluster = StoryCluster(
            "economy",
            (
                _item(
                    "kospi-strength",
                    "코스피 美 훈풍에 장 초반 1%대 강세",
                    "코스피가 장 초반 1%대 강세를 보였다.",
                    "market.example",
                ),
            ),
        )
        headline, summary, _, _, _, _ = synthesize_cluster(cluster, topic_name="경제", trend_metrics=())
        self.assertIn("강세", headline)
        self.assertIn("상승했다", summary)

    def test_song_announcement_preserves_release_date_and_fact(self) -> None:
        cluster = StoryCluster(
            "topic",
            (
                _item(
                    "bigbang-announcement",
                    "빅뱅, 데뷔 20주년 4년4개월만 신곡 빅 발표",
                    "그룹 빅뱅이 데뷔 20주년을 맞는 오는 19일 새 디지털 싱글을 발표한다고 전했다.",
                    "music.example",
                ),
            ),
        )
        headline, summary, _, _, facts, _ = synthesize_cluster(cluster, topic_name="K-POP", trend_metrics=())
        self.assertIn("신곡", headline)
        self.assertIn("19일", summary)
        self.assertIn("신곡", summary)
        self.assertEqual(facts.event_type, "PRODUCT_RELEASE")

    def test_representative_headline_does_not_switch_to_secondary_market_fact(self) -> None:
        cluster = StoryCluster(
            "economy",
            (
                _item(
                    "market-core",
                    "코스피·코스닥 동반 상승 출발",
                    "코스피와 코스닥이 상승 출발했다.",
                    "core.example",
                ),
                _item(
                    "market-secondary",
                    "코스피 6306.33 개장, 원·달러 환율 1410.8원",
                    "코스피 개장과 환율이 함께 제시됐다.",
                    "secondary.example",
                ),
            ),
        )
        headline, summary, _, _, facts, _ = synthesize_cluster(
            cluster, topic_name="경제", trend_metrics=()
        )
        self.assertEqual(facts.subject, "코스피")
        self.assertNotIn("환율", headline + summary)

    def test_headline_ellipsis_is_removed_and_title_type_wins_over_description_noise(self) -> None:
        cluster = StoryCluster(
            "topic",
            (
                _item(
                    "N009",
                    "올해 원달러 환율 변동폭 47원…금융위기 후 최고",
                    "관련 정책 변화가 발표됐다고 전했다.",
                    "market.example",
                ),
                _item(
                    "N010",
                    "원달러 월평균 변동폭 47원 금융위기 이후 최대",
                    "같은 수치를 보도했다.",
                    "finance.example",
                ),
            ),
        )
        headline, summary, _, _, facts, _ = synthesize_cluster(
            cluster, topic_name="경제", trend_metrics=()
        )
        self.assertEqual(facts.event_type, "MARKET")
        self.assertNotIn("…", headline)
        self.assertIn("47원", headline)
        self.assertNotIn("정책 변화가 발표됐다", summary)

    def test_generic_event_uses_a_natural_schedule_sentence(self) -> None:
        cluster = StoryCluster(
            "topic",
            (
                _item(
                    "N011",
                    "민형배 시장-김산 무안군수 회동… 군공항 이전·반도체 클러스터 상생",
                    "9일 광주에서 관련 일정이 공개됐다.",
                    "local.example",
                ),
            ),
        )
        headline, summary, _, _, facts, _ = synthesize_cluster(
            cluster, topic_name="정책", trend_metrics=()
        )
        self.assertEqual(headline, "민형배 시장-김산 무안군수 회동 일정")
        self.assertEqual(summary, "민형배 시장-김산 무안군수 회동 일정이 9일 광주에서 예정돼 있다.")
        self.assertEqual(facts.action, "공개")

    def test_numeric_headline_drops_clickbait_after_the_change_marker(self) -> None:
        cluster = StoryCluster(
            "topic",
            (
                _item(
                    "N012",
                    "네비우스(NBIS), 엔비디아가 지분 쓸어담고 170% 급등 월가 더 오른다",
                    "주가가 크게 올랐다고 전했다.",
                    "market.example",
                ),
            ),
        )
        headline, summary, _, _, facts, _ = synthesize_cluster(
            cluster, topic_name="시장", trend_metrics=()
        )
        self.assertEqual(headline, "네비우스(NBIS) 170% · 급등")
        self.assertEqual(summary, "네비우스(NBIS)는 170%로 급등했다.")
        self.assertEqual(facts.key_changes[0], "급등")
        self.assertNotIn("월가 더 오른다", headline + summary)

    def test_single_low_information_story_does_not_get_generic_follow_up(self) -> None:
        cluster = StoryCluster(
            "topic",
            (_item("N005", "지역 행사 소식 전달", "현장 소식이 전해졌다.", "local.example"),),
        )
        _, summary, evidence, watch, facts, certainty = synthesize_cluster(
            cluster, topic_name="지역", trend_metrics=()
        )
        self.assertEqual(facts.event_type, "OTHER")
        self.assertFalse(watch)
        self.assertIn("한 건", evidence)
        self.assertEqual(certainty.value, "uncertain")
        self.assertNotIn("후속 공식 발표", summary)
        self.assertNotIn("관련 내용이 확인됐다", summary)
        self.assertIn("추가 확인이 필요하다", summary)

    def test_truncated_source_artifacts_never_become_facts_or_headline(self) -> None:
        cluster = StoryCluster(
            "topic",
            (
                _item(
                    "N013",
                    "영탁, 명곡 완전 재해석… 트로트의 진짜 맛",
                    "... 코스피도 이틀째 하락했다. 7일 코...",
                    "music.example",
                ),
            ),
        )
        headline, summary, _, _, facts, _ = synthesize_cluster(cluster, topic_name="문화", trend_metrics=())
        displayed = headline + summary + " ".join(facts.key_changes)
        self.assertNotIn("...", displayed)
        self.assertNotIn("…", displayed)
        self.assertEqual(headline, "영탁 관련 보도")

    def test_conflicting_numeric_reports_are_flagged_for_confirmation(self) -> None:
        cluster = StoryCluster(
            "topic",
            (
                _item("N006", "기업 매출 100억원 기록", "분기 매출이 100억원이라고 전했다.", "a.example"),
                _item("N007", "기업 매출 120억원 기록", "분기 매출을 120억원으로 보도했다.", "b.example"),
            ),
        )
        _, summary, _, _, facts, _ = synthesize_cluster(cluster, topic_name="기업", trend_metrics=())
        self.assertEqual(facts.event_type, "EARNINGS")
        self.assertIn("추가 확인", summary)
        self.assertTrue(facts.uncertainty)

    def test_trend_state_uses_only_topic_metrics(self) -> None:
        metric = TrendMetric(
            "group",
            "검색어",
            "topic",
            "batch-a",
            80.0,
            40.0,
            50.0,
            40.0,
            100.0,
            1.0,
            "상승",
        )
        cluster = StoryCluster("topic", (_item("N008", "검색어 발표", "새 발표가 나왔다.", "a.example"),))
        _, _, _, _, facts, _ = synthesize_cluster(cluster, topic_name="테스트", trend_metrics=(metric,))
        self.assertEqual(facts.trend_state, "상승")


if __name__ == "__main__":
    unittest.main()
