from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from insight_desk.core import CandidateEvent, EventFact, EvidenceField, EvidenceSpan
from insight_desk.core.event_understanding_v2 import ArticleEventRole, TopicRelation, UnderstandingStatus
from insight_desk.production_event_understanding_compat_v2 import CompatibilityEventUnderstandingDecision
from insight_desk.production_event_understanding_compat_v2 import _is_context_dependent_subject
from insight_desk.production_replay_v2 import _recorded_edges
from insight_desk.semantic.pipeline import SemanticArticleResult
from scripts import phase11_daily_production as production


class ScheduledUnderstandingRoutingTests(unittest.TestCase):
    def test_deictic_subject_detection_requires_a_word_or_morpheme_boundary(self):
        for subject in ("그룹 TUNEXX(튜넥스)", "그린에너지", "이들이라는책출판사"):
            with self.subTest(subject=subject):
                self.assertFalse(_is_context_dependent_subject(subject))
        for subject in ("그", "그는", "그들", "그들의 계획", "이러한 기관", "해당 기업"):
            with self.subTest(subject=subject):
                self.assertTrue(_is_context_dependent_subject(subject))

    def test_unresolved_event_reaches_resolution_without_canonical_or_generation(self):
        case = {
            "candidate_id": "unresolved-source",
            "topic_id": "economy",
            "query": "한국은행 기준금리",
            "source_url": "https://example.com/unresolved-source",
            "source_name": "fixture",
            "search_title": "한국은행 기준금리 결정",
            "source_excerpt": "한국은행은 기준금리 결정을 발표했다.",
        }

        class EvidencePipeline:
            def extract_article(self, article, *, topic_id, extractor):
                span = EvidenceSpan.from_article(
                    evidence_id="evidence:unresolved", article=article,
                    field=EvidenceField.BODY, start=0, end=len(article.body),
                )
                fact = EventFact(fact_id="fact:unresolved", subject="한국은행",
                                 action="발표했다", evidence_ids=(span.evidence_id,))
                event = CandidateEvent(event_id="event:unresolved", topic_id=topic_id,
                                       fact_ids=(fact.fact_id,), article_ids=(article.article_id,))
                return SemanticArticleResult(article_id=article.article_id, extractor_id="fixture",
                                             evidence=(span,), facts=(fact,), events=(event,))

        unresolved = CompatibilityEventUnderstandingDecision(
            status=UnderstandingStatus.UNRESOLVED, article_role=ArticleEventRole.CONTEXT,
            topic_relation=TopicRelation.UNRESOLVED, publishable_event=False,
            reasons=("article_centrality_conflict",),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                _recorded_edges(cases=(case,), replay_clock=datetime(2026, 9, 3, tzinfo=timezone.utc)),
                patch("insight_desk.production_event_understanding_lifecycle_v2.LegacySemanticPipeline", EvidencePipeline),
                patch("insight_desk.production_event_understanding_lifecycle_v2.assess_compatibility_article_understanding",
                      return_value={"event:unresolved": unresolved}),
                patch.object(production._core, "build_resilient_fact_extractor", return_value=SimpleNamespace(route_stats={})),
                patch("insight_desk.production_relevance_v2.ConfiguredLiteralRelevanceOwner.decide_canonical_proposition",
                      side_effect=AssertionError("unresolved event reached canonical relevance")),
                patch.object(production._core, "produce_phase7_entry_candidate") as generate,
            ):
                state = production.run_production(topics_path=Path("config/topics.json"),
                                                 output_dir=root / "site", state_path=root / "state.json",
                                                 audit_path=root / "audit.json")
            audit = json.loads((root / "audit.json").read_text())
            self.assertFalse(state["publish"])
            self.assertEqual(audit["canonical_contract"]["canonical_events"], 0)
            generate.assert_not_called()
            self.assertEqual(audit["topic_stats"]["economy"]["event_understanding_resolution_expansions"], 1)
            self.assertTrue(any(row["stage"] == "event_understanding" and
                                row.get("reason") == "article_centrality_conflict"
                                for row in audit["attempts"]))


if __name__ == "__main__":
    unittest.main()
