from __future__ import annotations

"""Article-level event understanding for Canonical V2 production.

This owner resolves two event-understanding decisions before downstream publication:
- high-confidence temporal precedence across candidates from one article; and
- high-confidence topic ownership from the already-structured CanonicalEvent relation.

It does not perform article/source relevance, materiality, identity, generation quality, claim
verification, or publication. Topic ownership never re-reads EvidenceSpan or SourceDocument text.
When the structured relation is insufficient, the event is explicitly UNRESOLVED rather than
silently reclassified from free text.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
import re

from insight_desk.core import CanonicalEvent, RawArticle
from insight_desk.semantic.pipeline import SemanticArticleResult, SemanticPipeline


_CURRENT_EVENT_LAG = timedelta(days=1)


class EventTopicOwnershipVerdict(str, Enum):
    OWNED = "owned"
    NOT_OWNED = "not_owned"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class EventTopicOwnershipDecision:
    event_id: str
    topic_id: str
    verdict: EventTopicOwnershipVerdict
    reason: str


def _iso_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _configured_term_present(value: str, term: str) -> bool:
    """Mechanical explicit-term binding for one already-structured field.

    ASCII-only identifiers use alphanumeric boundaries so short configured names such as AI/SM/YG
    cannot match inside unrelated English words. Korean or mixed-script configured phrases keep
    literal substring semantics so aliases such as ``한화`` bind ``한화 이글스``.
    """

    needle = term.strip()
    if not needle:
        return False
    if needle.isascii() and any(ch.isalnum() for ch in needle):
        return bool(
            re.search(
                rf"(?<![A-Za-z0-9]){re.escape(needle)}(?![A-Za-z0-9])",
                value,
                flags=re.IGNORECASE,
            )
        )
    return needle.casefold() in value.casefold()


def _contains_any(value: str | None, terms: tuple[str, ...]) -> bool:
    if value is None:
        return False
    return any(_configured_term_present(value, term) for term in terms)


@dataclass(slots=True)
class PrimaryEventUnderstandingOwner:
    """Own article-primary precedence and structured event-to-topic ownership.

    Temporal selection remains intentionally conservative: only an explicit publication-day,
    previous-day, or future event can outrank older/undated context.

    Topic ownership is also high-confidence only. An event is OWNED when a configured topic term is
    explicitly bound to actor, object, or participants. A topic signal that survives only inside the
    broad action clause is UNRESOLVED because current deterministic extraction cannot prove whether
    it is the event relation or merely context. Missing signals are NOT_OWNED. Neither unresolved nor
    not-owned events are published by the compatibility runtime; unresolved decisions stay visible
    in the audit so a later semantic resolver can recover them without reintroducing detector logic.
    """

    articles_seen: int = 0
    resolved_primary: int = 0
    unresolved_preserved: int = 0
    ownership_decisions: dict[tuple[str, str], EventTopicOwnershipDecision] = field(
        default_factory=dict
    )

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

    def decide_topic_ownership(
        self,
        event: CanonicalEvent,
        *,
        topic_id: str,
        intent_anchors: tuple[str, ...],
        required_intent_terms: tuple[str, ...],
    ) -> EventTopicOwnershipDecision:
        key = (topic_id, event.event_id)
        prior = self.ownership_decisions.get(key)
        if prior is not None:
            return prior

        # Required terms remain the strongest configured vocabulary, but broad intent aliases are
        # also legitimate structured owners (e.g. a newly debuted "그룹" or a KBO participant).
        terms = tuple(dict.fromkeys(required_intent_terms + intent_anchors))
        if event.topic != topic_id:
            decision = EventTopicOwnershipDecision(
                event.event_id,
                topic_id,
                EventTopicOwnershipVerdict.NOT_OWNED,
                "canonical_topic_mismatch",
            )
        elif not terms:
            decision = EventTopicOwnershipDecision(
                event.event_id,
                topic_id,
                EventTopicOwnershipVerdict.UNRESOLVED,
                "no_configured_topic_ownership_terms",
            )
        else:
            core_values = (event.actor,) + (
                (event.object,) if event.object is not None else ()
            ) + event.participants
            if any(_contains_any(value, terms) for value in core_values):
                decision = EventTopicOwnershipDecision(
                    event.event_id,
                    topic_id,
                    EventTopicOwnershipVerdict.OWNED,
                    "configured_topic_term_bound_to_core_relation",
                )
            elif _contains_any(event.action, terms):
                decision = EventTopicOwnershipDecision(
                    event.event_id,
                    topic_id,
                    EventTopicOwnershipVerdict.UNRESOLVED,
                    "topic_signal_only_in_action_clause",
                )
            else:
                decision = EventTopicOwnershipDecision(
                    event.event_id,
                    topic_id,
                    EventTopicOwnershipVerdict.NOT_OWNED,
                    "no_topic_signal_in_structured_relation",
                )

        self.ownership_decisions[key] = decision
        return decision

    @property
    def audit_stats(self) -> dict[str, object]:
        counts = {verdict.value: 0 for verdict in EventTopicOwnershipVerdict}
        for decision in self.ownership_decisions.values():
            counts[decision.verdict.value] += 1
        return {
            "articles_seen": self.articles_seen,
            "resolved_primary": self.resolved_primary,
            "unresolved_primary_preserved": self.unresolved_preserved,
            "topic_ownership": {
                "decisions": len(self.ownership_decisions),
                **counts,
            },
            "source_or_evidence_re_read": False,
        }


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
