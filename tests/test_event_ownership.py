from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from insight_desk.config import load_topics
from insight_desk.domain.models import EvidenceType, NewsItem
from insight_desk.pipeline.clustering import StoryCluster
from insight_desk.pipeline.editorial import assess_cluster, assess_event, event_owned_items
from insight_desk.pipeline.selection import select_clusters
from insight_desk.pipeline.semantics import policy_roles, same_canonical_event
from insight_desk.pipeline.synthesis import synthesize_cluster
from scripts.validate_live_acceptance import validate as validate_live_acceptance

FIXTURE = Path(__file__).with_name("fixtures") / "run92_event_ownership_replay.json"


def _item(record: dict[str, object]) -> NewsItem:
    evidence_id = str(record["id"])
    domain = str(record["domain"])
    title = str(record["title"])
    lead = str(record["lead"])
    topic_id = str(record["topic_id"])
    query = str(record["query"])
    return NewsItem(
        evidence_id=evidence_id,
        topic_id=topic_id,
        query=query,
        title=title,
        summary=lead,
        original_url=f"https://{domain}/{evidence_id}",
        naver_url="",
        canonical_url=f"https://{domain}/{evidence_id}",
        published_at="2026-08-11T09:00:00+09:00",
        source_domain=domain,
        content_hash=evidence_id,
        score=float(record.get("score", 80.0)),
        metadata_title=title,
        metadata_description=lead,
        publisher=domain,
        provenance=(EvidenceType.SEARCH_SNIPPET, EvidenceType.ENRICHED_METADATA),
        matched_topic_ids=(topic_id,),
        retrieval_channels=("SIM",),
        retrieval_queries=(query,),
    )


class EventFactOwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.records = {str(record["id"]): record for record in cls.payload["items"]}
        cls.topics, _ = load_topics(Path("config/topics.json"))

    def _topic(self, topic_id: str):
        return next(topic for topic in self.topics if topic.id == topic_id)

    def test_run92_attendance_title_cannot_be_reclassified_by_foreign_lead(self) -> None:
        attendance = _item(self.records["attendance-milestone"])
        cluster = StoryCluster("kbo_hanwha", (attendance,))
        event = assess_event(cluster, self._topic("kbo_hanwha"))
        canonical = event.canonical_event
        assert canonical is not None

        self.assertEqual(event.event_type, "SPORTS_ATTENDANCE")
        self.assertNotEqual(event.event_type, "SPORTS_INTERRUPTION")
        self.assertEqual(canonical.evidence_detail, "")
        self.assertEqual(canonical.date, "")
        self.assertEqual(canonical.evidence_owner_ids, (attendance.evidence_id,))
        resumption = _item(self.records["weather-resumption"])
        resumption_event = assess_event(
            StoryCluster("kbo_hanwha", (resumption,)),
            self._topic("kbo_hanwha"),
        ).canonical_event
        assert resumption_event is not None
        self.assertNotEqual(canonical.canonical_event_id, resumption_event.canonical_event_id)
        self.assertFalse(same_canonical_event(canonical, resumption_event))
        assessment = assess_cluster(cluster, self._topic("kbo_hanwha"))
        self.assertFalse(assessment.evidence.metadata_complete)
        self.assertFalse(assessment.qualified)

    def test_run92_foreign_event_facts_are_excluded_from_resumption(self) -> None:
        attendance = _item(self.records["attendance-milestone"])
        resumption = _item(self.records["weather-resumption"])
        cluster = StoryCluster("kbo_hanwha", (resumption, attendance))
        event = assess_event(cluster, self._topic("kbo_hanwha"))
        canonical = event.canonical_event
        assert canonical is not None

        self.assertEqual(event.event_type, "SPORTS_INTERRUPTION")
        self.assertEqual(canonical.evidence_owner_ids, (resumption.evidence_id,))
        self.assertEqual(
            tuple(item.evidence_id for item in event_owned_items(cluster, canonical)),
            (resumption.evidence_id,),
        )
        headline, summary, _, _, facts, _ = synthesize_cluster(
            cluster,
            topic_name="KBO·한화 이글스",
            trend_metrics=(),
            canonical_event_override=canonical,
        )
        rendered = " ".join(
            (headline, summary, " ".join(facts.key_numbers), " ".join(facts.key_changes))
        )
        self.assertNotIn("900", rendered)
        self.assertNotIn("2026", rendered)
        self.assertEqual(facts.action, "재개")
        self.assertEqual(facts.cause, "HEAT")
        self.assertEqual(facts.source_count, 1)
        self.assertEqual(facts.event_owner_ids, (resumption.evidence_id,))
        self.assertEqual(facts.fact_evidence_ids, (resumption.evidence_id,))
        self.assertEqual(facts.representative_evidence_id, resumption.evidence_id)

        selected = select_clusters((cluster,), self.topics, limit=10)
        self.assertEqual(len(selected.selected), 1)
        self.assertEqual(selected.selected_reviews[0]["source_count"], 1)
        self.assertEqual(
            selected.selected_reviews[0]["representative_evidence_id"],
            resumption.evidence_id,
        )

    def test_same_event_sources_still_corroborate(self) -> None:
        first = _item(self.records["weather-resumption"])
        second = _item(self.records["weather-resumption-corroboration"])
        cluster = StoryCluster("kbo_hanwha", (first, second))
        event = assess_event(cluster, self._topic("kbo_hanwha"))
        canonical = event.canonical_event
        assert canonical is not None
        first_canonical = assess_event(
            StoryCluster("kbo_hanwha", (first,)),
            self._topic("kbo_hanwha"),
        ).canonical_event
        second_canonical = assess_event(
            StoryCluster("kbo_hanwha", (second,)),
            self._topic("kbo_hanwha"),
        ).canonical_event
        assert first_canonical is not None
        assert second_canonical is not None

        self.assertEqual(set(canonical.evidence_owner_ids), {first.evidence_id, second.evidence_id})
        self.assertTrue(same_canonical_event(first_canonical, second_canonical))
        _, summary, _, _, facts, _ = synthesize_cluster(
            cluster,
            topic_name="KBO·한화 이글스",
            trend_metrics=(),
            canonical_event_override=canonical,
        )
        self.assertIn("재개", summary)
        self.assertEqual(facts.source_count, 2)
        self.assertEqual(
            set(facts.fact_evidence_ids),
            {first.evidence_id, second.evidence_id},
        )

    def test_policy_actor_condition_object_and_action_remain_separate(self) -> None:
        first = _item(self.records["policy-rate-stance"])
        second = _item(self.records["policy-rate-stance-corroboration"])
        cluster = StoryCluster("economy", (first, second))
        event = assess_event(cluster, self._topic("economy"))
        canonical = event.canonical_event
        assert canonical is not None

        self.assertEqual(canonical.actor, "유상대 한국은행 부총재")
        self.assertEqual(canonical.subject, canonical.actor)
        self.assertEqual(canonical.condition, "경기충격 없다면")
        self.assertEqual(canonical.object, "기준금리")
        self.assertEqual(canonical.action, "추가 인상 가능성 언급")
        self.assertEqual(set(canonical.evidence_owner_ids), {first.evidence_id, second.evidence_id})
        _, summary, _, _, facts, _ = synthesize_cluster(
            cluster,
            topic_name="경제·투자",
            trend_metrics=(),
            canonical_event_override=canonical,
        )
        self.assertIn("기준금리를", summary)
        self.assertNotIn("기준금리 를", summary)
        self.assertIn("경기 충격이 없다면", summary)
        self.assertNotIn(facts.condition, facts.subject)
        self.assertNotEqual(facts.action, facts.object)

    def test_unknown_policy_roles_remain_empty(self) -> None:
        roles = policy_roles("한국은행 관계자 발언", "시장 상황을 지켜보고 있다.")
        self.assertEqual(roles.condition, "")
        self.assertEqual(roles.object, "")
        self.assertEqual(roles.action, "")

    def test_old_run92_machine_artifact_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="insight-run92-replay-") as directory:
            path = Path(directory) / "live-acceptance.json"
            path.write_text(
                json.dumps(
                    {"selected_stories": self.payload["old_selected_stories"]},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            errors = validate_live_acceptance(path)

        self.assertTrue(any("evidence owners" in error for error in errors))
        self.assertTrue(any("weather cause occupies the action role" in error for error in errors))
        self.assertTrue(any("policy noun occupies the action role" in error for error in errors))
        self.assertTrue(any("conditional clause was not separated" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
