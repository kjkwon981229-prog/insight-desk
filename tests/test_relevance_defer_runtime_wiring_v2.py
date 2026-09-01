from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest

from insight_desk.core import (
    CandidateEvent,
    CanonicalEvent,
    CanonicalEvidenceRef,
    EventFact,
    SourceDocument,
)
from insight_desk.production_runtime_v2 import production_v2_runtime
import scripts.phase11_daily_production as production


class RelevanceDeferRuntimeWiringTests(unittest.TestCase):
    def test_legacy_event_relevance_resolution_hook_is_not_reactivated(self) -> None:
        self.assertFalse(hasattr(production._core, "expand_deferred_event_relevance"))

        with production_v2_runtime(production._core):
            self.assertFalse(hasattr(production._core, "expand_deferred_event_relevance"))

        self.assertFalse(hasattr(production._core, "expand_deferred_event_relevance"))

    def test_daily_loop_requeues_only_bounded_expansion_candidates(self) -> None:
        source = Path("scripts/phase11_daily_production_core.py").read_text(encoding="utf-8")
        self.assertIn("expand_deferred_event_relevance(", source)
        self.assertIn("relevance_resolution_expansions", source)
        self.assertIn("queue.append(expanded_candidate)", source)
        self.assertIn("RELEVANCE_RESOLUTION_EXPANSION_LIMIT", source)

    def test_daily_loop_does_not_directly_promote_original_deferred_event(self) -> None:
        source = Path("scripts/phase11_daily_production_core.py").read_text(encoding="utf-8")
        relevance_branch = source.split("event_relevant = event_topic_relevant", 1)[1].split(
            "quality = phase6_engine.evaluate_event", 1
        )[0]
        self.assertIn("continue", relevance_branch)
        self.assertNotIn("event_relevant = True", relevance_branch)
        self.assertNotIn("status=\"published\"", relevance_branch)

    def test_post_understanding_gate_uses_exact_proposition_not_flat_fact(self) -> None:
        proposition = "한화와 NC는 29일 대전에서 맞붙는다."
        fact = EventFact(
            fact_id="fact:flat-projection",
            subject="NC",
            action="맞붙는다",
            evidence_ids=("evidence:flat-projection",),
        )
        event = CandidateEvent(
            event_id="event:flat-projection",
            topic_id="kbo_hanwha",
            fact_ids=(fact.fact_id,),
            article_ids=("article:flat-projection",),
        )
        topic = SimpleNamespace(
            topic_id="kbo_hanwha",
            intent_anchors=("KBO",),
            required_intent_terms=("한화",),
            event_terms=("경기",),
        )

        now = datetime(2026, 9, 1, tzinfo=timezone.utc)
        source = SourceDocument(
            source_id="source:exact-proposition",
            candidate_ids=(event.article_ids[0],),
            publisher="fixture",
            url="https://example.com/exact-proposition",
            title="한화-NC 맞대결",
            body=proposition,
            fetched_at=now,
            publication_time=now,
            retrieved_via="fixture",
            content_sha256=hashlib.sha256(proposition.encode("utf-8")).hexdigest(),
        )
        canonical = CanonicalEvent(
            event_id=event.event_id,
            topic=event.topic_id,
            actor=fact.subject,
            action=fact.action,
            event_type="news_event",
            source_ids=(source.source_id,),
            evidence_refs=(
                CanonicalEvidenceRef(
                    source_id=source.source_id,
                    field="body",
                    start=0,
                    end=len(proposition),
                    text_sha256=hashlib.sha256(proposition.encode("utf-8")).hexdigest(),
                ),
            ),
        )

        with production_v2_runtime(production._core) as registry:
            registry.sources_by_article[event.article_ids[0]] = source
            registry.events_by_id[event.event_id] = canonical
            self.assertTrue(
                production._core.event_topic_relevant(
                    event=event,
                    facts={fact.fact_id: fact},
                    evidence={},
                    topic=topic,
                )
            )

    def test_scattered_article_topic_terms_cannot_bind_an_unrelated_primary_event(self) -> None:
        proposition = "새봄시는 국제정원박람회 운영 계획을 공개했다."
        fact = EventFact(
            fact_id="fact:misleading-flat-projection",
            subject="K-POP 가수",
            action="새 앨범을 공개했다",
            evidence_ids=("evidence:misleading-flat-projection",),
        )
        event = CandidateEvent(
            event_id="event:misleading-flat-projection",
            topic_id="kpop",
            fact_ids=(fact.fact_id,),
            article_ids=("article:misleading-flat-projection",),
        )
        topic = SimpleNamespace(
            topic_id="kpop",
            intent_anchors=("K-POP", "가수", "앨범"),
            required_intent_terms=("가수", "앨범"),
            event_terms=("공개", "앨범", "공연"),
        )
        now = datetime(2026, 9, 1, tzinfo=timezone.utc)
        source = SourceDocument(
            source_id="source:unrelated-primary",
            candidate_ids=(event.article_ids[0],),
            publisher="fixture",
            url="https://example.com/unrelated-primary",
            title="국제정원박람회 개최",
            body=proposition,
            fetched_at=now,
            publication_time=now,
            retrieved_via="fixture",
            content_sha256=hashlib.sha256(proposition.encode("utf-8")).hexdigest(),
        )
        canonical = CanonicalEvent(
            event_id=event.event_id,
            topic=event.topic_id,
            actor="새봄시",
            action="국제정원박람회를 다음 달 개최한다",
            event_type="news_event",
            source_ids=(source.source_id,),
            evidence_refs=(
                CanonicalEvidenceRef(
                    source_id=source.source_id,
                    field="body",
                    start=0,
                    end=len(proposition),
                    text_sha256=hashlib.sha256(proposition.encode("utf-8")).hexdigest(),
                ),
            ),
        )

        with production_v2_runtime(production._core) as registry:
            registry.sources_by_article[event.article_ids[0]] = source
            registry.events_by_id[event.event_id] = canonical
            event_relevant = production._core.event_topic_relevant(
                event=event,
                facts={fact.fact_id: fact},
                evidence={},
                topic=topic,
            )
            self.assertFalse(event_relevant)
            attempt = production._core._attempt(
                topic="kpop",
                query="K-POP",
                domain="example.com",
                stage="event_topic_relevance",
                status="skip",
                reason="configured_literal_missing_in_event_evidence",
            )
            self.assertEqual(attempt["status"], "defer")
            self.assertEqual(attempt["reason"], "resolution_required")


if __name__ == "__main__":
    unittest.main()
