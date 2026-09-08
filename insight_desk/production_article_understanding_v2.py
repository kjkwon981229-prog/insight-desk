from __future__ import annotations

"""Production-only article-level Event Understanding compatibility boundary.

The legacy semantic extractor emits one CandidateEvent per extracted fact. This wrapper executes
after the canonical compatibility pipeline has produced that evidence-bound result but before the
daily loop sees any events. It preserves evidence/facts unchanged, exposes the article-level PRIMARY
event selected by the Event Understanding owner, and preserves UNRESOLVED events so the
Orchestrator can request bounded additional source evidence rather than silently dropping them.

This is intentionally removable: a qualified Event Understanding provider will replace the legacy
bridge and this compatibility wrapper together.
"""

from types import ModuleType

from insight_desk.core.event_understanding_v2 import ArticleEventRole, UnderstandingStatus
from insight_desk.production_event_understanding_compat_v2 import (
    assess_compatibility_article_understanding,
)
from insight_desk.semantic.pipeline import SemanticArticleResult
from insight_desk.semantic.tooling import KiwiMorphologyHelper


def _optional_morphology():
    try:
        return KiwiMorphologyHelper()
    except RuntimeError:
        return None


def install_article_understanding_semantic_pipeline(core_module: ModuleType) -> None:
    """Wrap the currently installed production SemanticPipeline with article-level centrality."""

    inner_pipeline_type = core_module.SemanticPipeline
    if getattr(inner_pipeline_type, "_INSIGHT_DESK_ARTICLE_UNDERSTANDING_OWNER", False):
        return

    class ArticleUnderstandingSemanticPipeline:
        _INSIGHT_DESK_ARTICLE_UNDERSTANDING_OWNER = True

        def __init__(self, *args, **kwargs) -> None:
            self._inner = inner_pipeline_type(*args, **kwargs)
            self._morphology = _optional_morphology()

        def extract_article(self, article, *, topic_id: str, extractor):
            result = self._inner.extract_article(
                article,
                topic_id=topic_id,
                extractor=extractor,
            )
            if not result.events:
                return result

            facts = {fact.fact_id: fact for fact in result.facts}
            evidence = {span.evidence_id: span for span in result.evidence}
            decisions = assess_compatibility_article_understanding(
                article=article,
                events=result.events,
                facts=facts,
                evidence=evidence,
                morphology=self._morphology,
                now=article.provenance.fetched_at,
            )
            primary_event_ids = {
                event_id
                for event_id, decision in decisions.items()
                if decision.status is UnderstandingStatus.RESOLVED
                and decision.article_role is ArticleEventRole.PRIMARY
                and decision.publishable_event
            }
            unresolved_event_ids = {
                event_id
                for event_id, decision in decisions.items()
                if decision.status is UnderstandingStatus.UNRESOLVED
            }
            retained_event_ids = primary_event_ids | unresolved_event_ids
            return SemanticArticleResult(
                article_id=result.article_id,
                extractor_id=result.extractor_id,
                evidence=result.evidence,
                facts=result.facts,
                events=tuple(
                    event for event in result.events if event.event_id in retained_event_ids
                ),
            )

    core_module.SemanticPipeline = ArticleUnderstandingSemanticPipeline
