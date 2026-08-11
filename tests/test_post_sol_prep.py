from __future__ import annotations

import json
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from insight_desk.config import load_topics
from insight_desk.domain.models import CollectorStatus, EvidenceType, NewsItem, RunState, RunStatus
from insight_desk.pipeline.analysis import build_briefing
from insight_desk.pipeline.clustering import StoryCluster
from insight_desk.pipeline.editorial import assess_cluster, daily_freshness_reasons
from insight_desk.pipeline.selection import select_clusters
from insight_desk.pipeline.synthesis import (
    _naturalize_release_onset,
    summary_why_redundant,
    synthesize_cluster,
)
from scripts.validate_live_acceptance import validate


NOW = datetime.fromisoformat("2026-08-12T07:30:00+09:00")


def _item(
    evidence_id: str,
    topic_id: str,
    title: str,
    summary: str,
    published_at: str,
) -> NewsItem:
    return NewsItem(
        evidence_id,
        topic_id,
        "7급 공채" if topic_id == "psat_recruitment" else "음악 차트",
        title,
        summary,
        f"https://publisher-{evidence_id}.test/story",
        f"https://publisher-{evidence_id}.test/story",
        f"https://publisher-{evidence_id}.test/story",
        published_at,
        f"publisher-{evidence_id}.test",
        evidence_id,
        85.0,
        metadata_title=title,
        metadata_description=summary,
        metadata_published_at=published_at,
        provenance=(EvidenceType.SEARCH_SNIPPET, EvidenceType.ENRICHED_METADATA),
        matched_topic_ids=(topic_id,),
        retrieval_channels=("SIM",),
        retrieval_queries=("7급 공채" if topic_id == "psat_recruitment" else "음악 차트",),
    )


class PostSolPrepTests(unittest.TestCase):
    def test_release_onset_naturalization_is_bounded_and_generic(self) -> None:
        for marker in ("컴백", "출시", "발표", "공개"):
            self.assertEqual(_naturalize_release_onset(f"{marker}부터"), f"{marker} 후")
        self.assertEqual(_naturalize_release_onset("컴백 후"), "컴백 후")
        self.assertEqual(_naturalize_release_onset("발매부터"), "발매부터")

    def test_award_summary_uses_natural_release_connector(self) -> None:
        items = (
            _item(
                "chart-result",
                "kpop",
                "스트레이 키즈, THIS & THAT 국내외 음악 차트 1위",
                "스트레이 키즈가 음악 차트 1위에 올랐다.",
                "2026-08-09T08:00:00+09:00",
            ),
            _item(
                "chart-context",
                "kpop",
                "스트레이 키즈, 컴백부터 국내외 차트 1위",
                "컴백부터 국내외 차트 1위를 기록했다.",
                "2026-08-09T08:01:00+09:00",
            ),
        )
        _, summary, _, _, _, _ = synthesize_cluster(
            StoryCluster("kpop", items),
            topic_name="엔터·음악·K-POP",
            trend_metrics=(),
            event_type_override="AWARD_CHART",
        )
        self.assertIn("컴백 후", summary)
        self.assertNotIn("컴백부터", summary)

    def test_summary_why_contract_only_flags_exact_or_near_exact_repetition(self) -> None:
        self.assertTrue(summary_why_redundant("구체적인 결과가 확인됐다.", "구체적인 결과가 확인됐다."))
        self.assertTrue(summary_why_redundant("스트레이 키즈는 차트 1위에 올랐다.", "스트레이 키즈는 차트 1위에 올랐다"))
        self.assertFalse(summary_why_redundant("스트레이 키즈는 차트 1위에 올랐다.", "팬덤과 업계의 관심을 확인할 수 있는 결과다."))

    def test_validator_rejects_summary_why_duplication_but_allows_omission(self) -> None:
        base = {
            "rank": 1,
            "headline": "스트레이 키즈, 음악 차트 1위",
            "summary": "스트레이 키즈는 음악 차트 1위에 올랐다.",
            "event_type": "AWARD_CHART",
            "source_count": 1,
            "concrete_fact_count": 2,
            "topic_id": "kpop",
            "why_selected": ["CONCRETE_EVENT"],
            "event_signature": "AWARD_CHART|스트레이키즈|1위",
            "final_score": 72.0,
        }
        with TemporaryDirectory(prefix="insight-desk-why-duplicate-") as directory:
            path = Path(directory) / "live-acceptance.json"
            path.write_text(json.dumps({"selected_stories": [{**base, "why_it_matters": base["summary"]}]}), encoding="utf-8")
            errors = validate(path)
            self.assertTrue(any("duplicates summary in why_it_matters" in error for error in errors))
            path.write_text(json.dumps({"selected_stories": [{**base, "why_it_matters": ""}]}), encoding="utf-8")
            self.assertFalse(any("duplicates summary in why_it_matters" in error for error in validate(path)))

    def test_generated_story_omits_unsafe_duplicate_why_field(self) -> None:
        topics, _ = load_topics(Path("config/topics.json"))
        item = _item(
            "fresh-chart",
            "kpop",
            "스트레이 키즈, 음악 차트 1위",
            "스트레이 키즈가 음악 차트 1위에 올랐다.",
            "2026-08-12T07:00:00+09:00",
        )
        corroborating = _item(
            "fresh-chart-2",
            "kpop",
            "스트레이 키즈, THIS & THAT 국내외 음악 차트 1위",
            "스트레이 키즈가 국내외 음악 차트 1위에 올랐다.",
            "2026-08-12T07:05:00+09:00",
        )
        context = _item(
            "fresh-chart-3",
            "kpop",
            "스트레이 키즈, 컴백부터 국내외 차트 1위",
            "컴백부터 국내외 차트 1위를 기록했다.",
            "2026-08-12T07:06:00+09:00",
        )
        status = CollectorStatus(1, 1, 0, False, 1)
        state = RunState(
            RunStatus.COMPLETE,
            True,
            NOW.isoformat(),
            "2026-07-13",
            "fixture",
            status,
            status,
        )
        briefing = build_briefing(
            state=state,
            topics=topics,
            news=(item, corroborating, context),
            clusters=(StoryCluster("kpop", (item, corroborating, context)),),
            trend_metrics=(),
            generated_at=NOW,
        )
        self.assertEqual(len(briefing.stories), 1)
        self.assertEqual(briefing.stories[0].why_it_matters, "")

    def test_old_completed_competition_is_not_a_new_daily_story(self) -> None:
        topics, _ = load_topics(Path("config/topics.json"))
        item = _item(
            "old-competition",
            "psat_recruitment",
            "경기도 첫 지방노동감독관 7급 공채 경쟁률 11.7대 1",
            "25명 선발에 292명이 지원해 경쟁률 11.7대 1을 기록했다.",
            "2026-07-29T08:00:00+09:00",
        )
        result = select_clusters(
            (StoryCluster("psat_recruitment", (item,)),),
            topics,
            now=NOW,
        )
        self.assertEqual(result.selected, ())
        self.assertFalse(result.filter_collapse)
        audit = next(row for row in result.audit if row["candidate_key"] == item.canonical_url)
        self.assertIn("FRESHNESS_FAILED", audit["selection_reasons"])
        self.assertIn("STALE_COMPLETED_EVENT", audit["selection_reasons"])

    def test_old_announcement_with_future_deadline_remains_actionable(self) -> None:
        topics, _ = load_topics(Path("config/topics.json"))
        item = _item(
            "future-deadline",
            "psat_recruitment",
            "경기도 지방공무원 7급 공채 경쟁률 11.7대 1",
            "25명 선발에 292명이 지원했다. 원서 접수는 8월 20일 마감되며 시험 일정은 추후 공고된다.",
            "2026-07-29T08:00:00+09:00",
        )
        result = select_clusters(
            (StoryCluster("psat_recruitment", (item,)),),
            topics,
            now=NOW,
        )
        self.assertEqual(len(result.selected), 1)

    def test_old_event_update_is_not_rejected_by_publication_age(self) -> None:
        topics, _ = load_topics(Path("config/topics.json"))
        item = _item(
            "updated-event",
            "psat_recruitment",
            "지방공무원 공채 경쟁률에 새 일정 업데이트",
            "새로운 시험 일정이 오늘 공개됐다.",
            "2026-07-29T08:00:00+09:00",
        )
        cluster = StoryCluster("psat_recruitment", (item,))
        topic = next(topic for topic in topics if topic.id == "psat_recruitment")
        assessment = assess_cluster(cluster, topic, novelty="UPDATE")
        self.assertEqual(
            daily_freshness_reasons(cluster, assessment.event, now=NOW, novelty="UPDATE"),
            (),
        )


if __name__ == "__main__":
    unittest.main()
