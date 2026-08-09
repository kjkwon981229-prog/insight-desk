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
