from __future__ import annotations

"""Article-level event understanding for Canonical V2 production.

This owner resolves only high-confidence editorial precedence before CanonicalEvent creation.
It does not classify topic relevance, materiality, identity, generation quality, or publication.
When the article does not contain an explicit current/future event anchor, all extracted event
candidates are preserved so uncertainty cannot silently collapse recall.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from insight_desk.core import RawArticle
from insight_desk.semantic.pipeline import SemanticArticleResult, SemanticPipeline


_CURRENT_EVENT_LAG = timedelta(days=1)


def _iso_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


@dataclass(slots=True)
class PrimaryEventUnderstandingOwner:
    """Choose article-primary candidates only when temporal precedence is explicit.

    A publication-day or previous-day event (and a future scheduled event) is a strong current
    article anchor. If at least one such candidate exists, older/undated candidates remain context
    facts but are not eligible to outrank the explicit current event in downstream publication.

    If no strong current anchor exists, the result is returned unchanged. This deliberately keeps
    historical features, retrospective articles, and unresolved multi-event articles available for
    later semantic resolution instead of buying precision through recall loss.
    """

    articles_seen: int = 0
    resolved_primary: int = 0
    unresolved_preserved: int = 0

    def select(
        self,
        article: RawArticle,
        result: SemanticArticleResult,
    ) -> SemanticArticleResult:
        self.articles_seen += 1
        if len(result.events) <= 1 or article.provenance.published_at is None:
            self.unresolved_preserved += 1
            return result

        facts = {fact.fact_id: fact for fact in result.facts}
        cutoff = article.provenance.published_at.date() - _CURRENT_EVENT_LAG
        current_event_ids: set[str] = set()

        for event in result.events:
            # Current production extraction is one-fact-per-candidate. If that invariant changes,
            # this owner refuses to guess until the richer event contract is explicitly designed.
            if len(event.fact_ids) != 1:
                self.unresolved_preserved += 1
                return result
            fact = facts.get(event.fact_ids[0])
            if fact is None:
                self.unresolved_preserved += 1
                return result
            event_date = _iso_date(fact.event_date)
            if event_date is not None and event_date >= cutoff:
                current_event_ids.add(event.event_id)

        if not current_event_ids or len(current_event_ids) == len(result.events):
            self.unresolved_preserved += 1
            return result

        self.resolved_primary += 1
        return SemanticArticleResult(
            article_id=result.article_id,
            extractor_id=result.extractor_id,
            evidence=result.evidence,
            facts=result.facts,
            events=tuple(
                event for event in result.events if event.event_id in current_event_ids
            ),
        )


class EventUnderstandingSemanticPipeline:
    """SemanticPipeline adapter that applies article-level understanding exactly once."""

    def __init__(
        self,
        *args,
        owner: PrimaryEventUnderstandingOwner,
        **kwargs,
    ) -> None:
        self._inner = SemanticPipeline(*args, **kwargs)
        self._owner = owner

    def extract_article(self, article, *, topic_id: str, extractor):
        result = self._inner.extract_article(
            article,
            topic_id=topic_id,
            extractor=extractor,
        )
        return self._owner.select(article, result)
