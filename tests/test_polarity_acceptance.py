from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from insight_desk.config import load_topics
from insight_desk.domain.models import EvidenceType, NewsItem
from insight_desk.pipeline.clustering import StoryCluster
from insight_desk.pipeline.selection import select_clusters
from insight_desk.pipeline.semantics import EventFact
from insight_desk.pipeline.synthesis import (
    _event_relation_summary,
    _relation_temporal_mode,
    is_usable_synthesis,
    relation_summary_preserves_fact,
)
from scripts.validate_live_acceptance import validate


def _fact(action: str = "선정", object_text: str = "NVIDIA 협업 프로그램") -> EventFact:
    return EventFact(
        "EVENT_RELATION",
        object_text,
        subject="A사",
        relation=action,
        object=object_text,
    )


def _payload(summary: str) -> dict[str, object]:
    return {
        "selected_stories": [
            {
                "rank": 1,
                "topic_id": "ai_tech",
                "headline": "A사, NVIDIA 협업 프로그램 선정",
                "summary": summary,
                "why_it_matters": "협업 결과가 확인됐다.",
                "event_type": "ANNOUNCEMENT",
                "certainty": "confirmed",
                "source_count": 1,
                "publisher_diversity": 1,
                "concrete_fact_count": 1,
                "final_score": 80,
                "why_selected": ["명시적 협업 결과"],
                "event_signature": "a사|선정|NVIDIA 협업 프로그램",
                "facts": {
                    "event_type": "ANNOUNCEMENT",
                    "event_signature": "a사|선정|NVIDIA 협업 프로그램",
                    "canonical_event_id": "event-1",
                    "conflict_state": "NO_CONFLICT",
                    "subject": "A사",
                    "action": "선정",
                    "object": "NVIDIA 협업 프로그램",
                    "primary_focus_terms": ["A사", "NVIDIA 협업 프로그램"],
                    "event_owner_ids": ["e1"],
                    "fact_evidence_ids": ["e1"],
                    "representative_evidence_id": "e1",
                },
            }
        ]
    }


class PolarityAcceptanceTests(unittest.TestCase):
    def test_relation_preservation_requires_affirmative_commitment(self) -> None:
        fact = _fact()
        headline = "A사, NVIDIA 협업 프로그램 선정"
        self.assertTrue(
            relation_summary_preserves_fact(
                "A사가 NVIDIA 협업 프로그램에 선정됐다.", headline, fact
            )
        )
        self.assertTrue(
            relation_summary_preserves_fact(
                "A사가 NVIDIA 협업 프로그램에 선정될 예정이다.", headline, fact
            )
        )
        self.assertFalse(
            relation_summary_preserves_fact(
                "A사가 NVIDIA 협업 프로그램에 선정되지 않았다.", headline, fact
            )
        )
        self.assertFalse(
            relation_summary_preserves_fact(
                "A사가 NVIDIA 협업 프로그램에 선정될 가능성이 있다.", headline, fact
            )
        )
        self.assertFalse(
            relation_summary_preserves_fact(
                "A사가 NVIDIA 협업 프로그램에 선정됐다.",
                "A사, NVIDIA 협업 프로그램 선정 가능성",
                fact,
            )
        )
        departure = EventFact(
            "EVENT_RELATION", "JYP", subject="채영", relation="떠남", object="JYP"
        )
        self.assertTrue(
            relation_summary_preserves_fact(
                "채영이 JYP를 떠났다.", "채영, JYP 떠남", departure
            )
        )
        self.assertTrue(
            relation_summary_preserves_fact(
                "채영이 JYP를 떠난다고 밝혔다.", "채영, JYP 떠남", departure
            )
        )

    def test_announcement_marker_is_bound_to_relation_clause(self) -> None:
        self.assertEqual(
            _relation_temporal_mode(
                "A사, NVIDIA 협업 프로그램 선정",
                "A사가 NVIDIA 협업 프로그램에 선정됐다고 밝혔다.",
                "선정",
            ),
            "ANNOUNCED",
        )
        self.assertEqual(
            _relation_temporal_mode(
                "A사, NVIDIA 협업 프로그램 선정",
                "A사가 NVIDIA 협업 프로그램에 선정됐다. 다른 회사가 투자하겠다고 밝혔다.",
                "선정",
            ),
            "COMPLETED",
        )

    def test_polarity_matrix_keeps_nonaffirmative_states_nonaffirmative(self) -> None:
        cases = (
            ("선정", "A사", "NVIDIA 협업 프로그램", "A사가 NVIDIA 협업 프로그램에 선정됐다.", "COMPLETED", True),
            ("선정", "A사", "NVIDIA 협업 프로그램", "A사가 NVIDIA 협업 프로그램에 선정될 예정이다.", "FUTURE", True),
            ("선정", "A사", "NVIDIA 협업 프로그램", "A사가 NVIDIA 협업 프로그램에 선정될 가능성이 있다.", "POSSIBILITY", False),
            ("선정", "A사", "NVIDIA 협업 프로그램", "A사가 NVIDIA 협업 프로그램에 선정되지 않았다.", "NEGATED", False),
            ("투자", "A사", "5조원", "A사가 5조원을 투자했다.", "COMPLETED", True),
            ("투자", "A사", "5조원", "A사가 5조원에 투자하기로 했다.", "FUTURE", True),
            ("투자", "A사", "5조원", "A사가 5조원 투자를 검토한다.", "POSSIBILITY", False),
            ("투자", "A사", "5조원", "A사는 5조원을 투자하지 않기로 했다.", "NEGATED", False),
            ("떠남", "채영", "JYP", "채영이 JYP를 떠났다.", "COMPLETED", True),
            ("떠남", "채영", "JYP", "채영이 JYP를 떠난다고 밝혔다.", "ANNOUNCED", True),
            ("떠남", "채영", "JYP", "채영이 JYP를 떠날 가능성이 있다.", "POSSIBILITY", False),
            ("떠남", "채영", "JYP", "채영이 JYP를 떠나지 않는다고 밝혔다.", "NEGATED", False),
            ("착공", "회사", "공장", "회사가 공장 착공식을 열었다.", "COMPLETED", True),
            ("착공", "회사", "공장", "회사가 27일 공장 착공식을 연다.", "FUTURE", True),
            ("착공", "회사", "공장", "회사가 공장 착공을 계획하고 있다.", "UNKNOWN", True),
            ("착공", "회사", "공장", "공장 착공 계획이 확정되지 않았다.", "NEGATED", False),
        )
        for action, subject, object_text, evidence, expected_mode, expected_preserved in cases:
            fact = EventFact(
                "EVENT_RELATION",
                object_text,
                subject=subject,
                relation=action,
                object=object_text,
            )
            headline = f"{subject}, {object_text} {action}"
            summary = _event_relation_summary(headline, evidence, fact)
            self.assertEqual(
                _relation_temporal_mode(headline, evidence, action), expected_mode, evidence
            )
            self.assertEqual(
                relation_summary_preserves_fact(summary, headline, fact),
                expected_preserved,
                evidence,
            )

    def test_temporal_escalation_is_not_rendered(self) -> None:
        fact = _fact()
        possibility = _event_relation_summary(
            "A사, NVIDIA 협업 프로그램 선정",
            "A사가 NVIDIA 협업 프로그램에 선정될 가능성이 있다고 밝혔다.",
            fact,
        )
        negated = _event_relation_summary(
            "A사, NVIDIA 협업 프로그램 선정",
            "A사가 NVIDIA 협업 프로그램에 선정되지 않았다고 밝혔다.",
            fact,
        )
        self.assertNotIn("선정됐다", possibility)
        self.assertNotIn("선정됐다", negated)
        self.assertNotIn("선정됐다", _event_relation_summary(
            "A사, NVIDIA 협업 프로그램 선정 예정",
            "A사가 NVIDIA 협업 프로그램에 선정될 예정이다.",
            fact,
        ))

    def test_selection_contract_rejects_non_affirmative_relation(self) -> None:
        fact = _fact()
        headline = "A사, NVIDIA 협업 프로그램 선정"
        self.assertTrue(
            is_usable_synthesis(
                headline,
                "A사가 NVIDIA 협업 프로그램에 선정됐다.",
                source_count=1,
                relation_fact=fact,
            )
        )
        for summary in (
            "A사가 NVIDIA 협업 프로그램에 선정되지 않았다.",
            "A사가 NVIDIA 협업 프로그램에 선정될 가능성이 있다.",
        ):
            self.assertFalse(
                is_usable_synthesis(
                    headline,
                    summary,
                    source_count=1,
                    relation_fact=fact,
                )
            )

    def test_selection_path_rejects_non_affirmative_owned_relation(self) -> None:
        topics, _ = load_topics(Path("config/topics.json"))
        item = NewsItem(
            evidence_id="polarity-negative",
            topic_id="ai_tech",
            query="NVIDIA",
            title="A사, NVIDIA 협업 프로그램 선정",
            summary="A사가 NVIDIA 협업 프로그램에 선정될 가능성이 있다고 밝혔다.",
            original_url="https://polarity.test/story",
            naver_url="",
            canonical_url="https://polarity.test/story",
            published_at="2026-08-13T07:00:00+09:00",
            source_domain="polarity.test",
            content_hash="polarity-negative",
            score=88.0,
            metadata_title="A사, NVIDIA 협업 프로그램 선정",
            metadata_description="A사가 NVIDIA 협업 프로그램에 선정될 가능성이 있다고 밝혔다.",
            publisher="polarity.test",
            provenance=(EvidenceType.SEARCH_SNIPPET, EvidenceType.ENRICHED_METADATA),
            matched_topic_ids=("ai_tech",),
            retrieval_channels=("SIM",),
            retrieval_queries=("NVIDIA",),
        )
        result = select_clusters(
            (StoryCluster("ai_tech", (item,)),),
            topics,
            limit=10,
        )
        self.assertEqual(result.selected, ())
        self.assertIn("SYNTHESIS_NOT_EDITORIAL_READY", result.audit[0]["selection_reasons"])

    def test_validator_uses_the_same_relation_contract(self) -> None:
        self.assertEqual(
            _validate_payload(_payload("A사가 NVIDIA 협업 프로그램에 선정됐다.")),
            [],
        )
        for summary in (
            "A사가 NVIDIA 협업 프로그램에 선정되지 않았다.",
            "A사가 NVIDIA 협업 프로그램에 선정될 가능성이 있다.",
        ):
            errors = _validate_payload(_payload(summary))
            self.assertTrue(
                any("relation fact polarity" in error for error in errors),
                errors,
            )


def _validate_payload(payload: dict[str, object]) -> list[str]:
    import json

    with TemporaryDirectory() as directory:
        path = Path(directory) / "live-acceptance.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return validate(path)


if __name__ == "__main__":
    unittest.main()
