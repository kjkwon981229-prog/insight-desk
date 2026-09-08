from __future__ import annotations

"""Bounded Event Understanding compatibility owner for the legacy extraction bridge.

This module is deliberately provider-free. It does not create CanonicalEvent objects and it does
not replace the qualified Event Understanding provider contract. It classifies the already
extracted, evidence-bound CandidateEvents jointly at article scope so the production loop can
separate one source-central news event from contextual/analytical facts before Phase 6 selection.
"""

from dataclasses import dataclass, replace
from datetime import date, datetime
import re
from typing import Mapping, Protocol

from insight_desk.core import CandidateEvent, ContractError, EvidenceSpan, EventFact, RawArticle
from insight_desk.core.event_understanding_v2 import (
    ArticleEventRole,
    TopicRelation,
    UnderstandingStatus,
)
from insight_desk.event_predicate_v2 import PredicateCompleteness, assess_event_predicate
from insight_desk.semantic.tooling import MorphologySourceOffsetError


class MorphologyPort(Protocol):
    def analyze(self, text: str): ...


@dataclass(frozen=True, slots=True)
class CompatibilityEventUnderstandingDecision:
    status: UnderstandingStatus
    article_role: ArticleEventRole
    topic_relation: TopicRelation
    publishable_event: bool
    reasons: tuple[str, ...] = ()


_CONTEXT_SUBJECT_STEMS = (
    "그",
    "그녀",
    "그들",
    "이들",
    "그것",
    "이것",
    "해당",
    "이는",
    "이를",
    "이러한",
    "그러한",
)

_ANALYTICAL_PREDICATES = (
    "평가된다",
    "평가했다",
    "전망된다",
    "전망했다",
    "예상된다",
    "예상했다",
    "분석된다",
    "분석했다",
    "기대된다",
    "기대했다",
    "것으로 보인다",
    "것으로 관측된다",
    "가능성이 있다",
    "의미가 있다",
    "효과가 있을",
    "효과가 기대",
)


def _normalized(text: str) -> str:
    return " ".join(text.split())


def _is_context_dependent_subject(subject: str, morphology: MorphologyPort | None = None) -> bool:
    value = _normalized(subject)
    if not value:
        return True
    if any(value == stem or value.startswith(stem + " ") for stem in _CONTEXT_SUBJECT_STEMS):
        return True
    # Compatibility callers can retain a case/topic particle in the subject surface.
    first_word = value.split()[0]
    if any(first_word == stem + particle for stem in _CONTEXT_SUBJECT_STEMS
           for particle in ("은", "는", "이", "가", "의", "을", "를", "도", "만")):
        return True
    tokens = _morphology_tokens(value, morphology)
    if not tokens:
        return False
    first = tokens[0]
    return (
        str(getattr(first, "tag", "")) in {"NP", "MM"}
        and str(getattr(first, "normalized", getattr(first, "surface", ""))) in _CONTEXT_SUBJECT_STEMS
    )


def _is_analytical_predicate(action: str) -> bool:
    value = _normalized(action)
    return any(predicate in value for predicate in _ANALYTICAL_PREDICATES)


def _morphology_tokens(text: str, morphology: MorphologyPort | None) -> tuple[object, ...] | None:
    if morphology is None:
        return None
    try:
        return tuple(morphology.analyze(text))
    except (ContractError, MorphologySourceOffsetError):
        return None


def _has_explicit_predicate(action: str, morphology: MorphologyPort | None) -> bool:
    if not _normalized(action):
        return False
    if morphology is None:
        # Compatibility direct-call behavior. Production article understanding supplies morphology;
        # the shared owner is authoritative whenever structural analysis is available.
        return True
    assessment = assess_event_predicate(action, morphology=morphology)
    return assessment.completeness is PredicateCompleteness.COMPLETE


def _is_copular_definition(action: str, morphology: MorphologyPort | None) -> bool:
    """Identify a static classification/definition by its final morphological predicate only."""

    tokens = _morphology_tokens(action, morphology)
    if not tokens:
        return False
    predicate_tags = [
        str(getattr(token, "tag", ""))
        for token in tokens
        if str(getattr(token, "tag", "")).startswith(("V", "XSV", "XSA"))
    ]
    return bool(predicate_tags) and predicate_tags[-1] in {"VCP", "VCN"}


def _evidence_is_local(
    event: CandidateEvent,
    fact: EventFact,
    evidence: Mapping[str, EvidenceSpan],
) -> bool:
    """Check provenance locality only; Phase 6 owns fact-field evidence integrity."""

    if not fact.evidence_ids:
        return False
    for evidence_id in fact.evidence_ids:
        span = evidence.get(evidence_id)
        if span is None or span.article_id not in event.article_ids or not span.text.strip():
            return False
    return True


def assess_compatibility_event_understanding(
    event: CandidateEvent,
    *,
    facts: Mapping[str, EventFact],
    evidence: Mapping[str, EvidenceSpan],
    morphology: MorphologyPort | None,
    now: datetime,
) -> CompatibilityEventUnderstandingDecision:
    """Classify one legacy bridge event without inventing new event semantics."""

    del now
    if len(event.fact_ids) != 1:
        return CompatibilityEventUnderstandingDecision(
            status=UnderstandingStatus.UNRESOLVED,
            article_role=ArticleEventRole.CONTEXT,
            topic_relation=TopicRelation.UNRESOLVED,
            publishable_event=False,
            reasons=("compat_requires_single_fact",),
        )

    fact = facts.get(event.fact_ids[0])
    if fact is None:
        return CompatibilityEventUnderstandingDecision(
            status=UnderstandingStatus.UNRESOLVED,
            article_role=ArticleEventRole.CONTEXT,
            topic_relation=TopicRelation.UNRESOLVED,
            publishable_event=False,
            reasons=("fact_missing",),
        )

    if not _evidence_is_local(event, fact, evidence):
        return CompatibilityEventUnderstandingDecision(
            status=UnderstandingStatus.UNRESOLVED,
            article_role=ArticleEventRole.CONTEXT,
            topic_relation=TopicRelation.UNRESOLVED,
            publishable_event=False,
            reasons=("evidence_not_local",),
        )

    if _is_context_dependent_subject(fact.subject, morphology):
        return CompatibilityEventUnderstandingDecision(
            status=UnderstandingStatus.UNRESOLVED,
            article_role=ArticleEventRole.CONTEXT,
            topic_relation=TopicRelation.UNRESOLVED,
            publishable_event=False,
            reasons=("context_dependent_actor",),
        )

    if not _has_explicit_predicate(fact.action, morphology):
        return CompatibilityEventUnderstandingDecision(
            status=UnderstandingStatus.UNRESOLVED,
            article_role=ArticleEventRole.CONTEXT,
            topic_relation=TopicRelation.UNRESOLVED,
            publishable_event=False,
            reasons=("predicate_unresolved",),
        )

    if _is_copular_definition(fact.action, morphology):
        return CompatibilityEventUnderstandingDecision(
            status=UnderstandingStatus.RESOLVED,
            article_role=ArticleEventRole.CONTEXT,
            topic_relation=TopicRelation.BACKGROUND,
            publishable_event=False,
            reasons=("copular_definition_context",),
        )

    if _is_analytical_predicate(fact.action):
        return CompatibilityEventUnderstandingDecision(
            status=UnderstandingStatus.RESOLVED,
            article_role=ArticleEventRole.CONTEXT,
            topic_relation=TopicRelation.BACKGROUND,
            publishable_event=False,
            reasons=("analytical_context",),
        )

    return CompatibilityEventUnderstandingDecision(
        status=UnderstandingStatus.RESOLVED,
        article_role=ArticleEventRole.PRIMARY,
        topic_relation=TopicRelation.DIRECT,
        publishable_event=True,
    )


def _first_sentence_end(body: str, morphology: MorphologyPort | None = None) -> int:
    # Acquisition preserves source blocks. A detached noun-only caption is not the lead.
    # Never skip a clause-bearing prefix: its context may constrain the following event.
    offset = 0
    if morphology is not None:
        for line in body.splitlines(keepends=True):
            if not line.strip():
                offset += len(line)
                continue
            tokens = _morphology_tokens(line, morphology)
            if not tokens or any(
                str(getattr(token, "tag", "")).startswith("J")
                or str(getattr(token, "tag", "")) in {"VV", "VA", "XSV", "VCP", "VCN"}
                for token in tokens
            ):
                break
            offset += len(line)
        if offset >= len(body):
            offset = 0
    body = body[offset:]
    boundaries = [position + 1 for position, char in enumerate(body) if char in ".!?…\n"]
    return offset + (min(boundaries) if boundaries else len(body))


_TITLE_CONTENT_TAG_PREFIXES = (
    "NN",
    "NR",
    "NP",
    "VV",
    "VA",
    "SL",
    "SN",
    "XR",
    "XPN",
)


def _exact_proposition_span(
    article: RawArticle,
    event: CandidateEvent,
    *,
    facts: Mapping[str, EventFact],
    evidence: Mapping[str, EvidenceSpan],
) -> EvidenceSpan | None:
    """Resolve one immutable proposition without consulting flat semantic fields."""

    if len(event.fact_ids) != 1:
        return None
    fact = facts.get(event.fact_ids[0])
    if fact is None or len(fact.evidence_ids) != 1:
        return None
    span = evidence.get(fact.evidence_ids[0])
    if span is None or span.article_id not in event.article_ids:
        return None
    try:
        span.validate_against(article)
    except Exception:
        return None
    return span


def _source_key(text: str) -> str:
    return "".join(text.split()).casefold()


def _title_content_units(
    article: RawArticle,
    morphology: MorphologyPort | None,
) -> tuple[tuple[str, ...], ...]:
    """Return source-derived title units; no topic or event vocabulary participates."""

    tokens = _morphology_tokens(article.title, morphology)
    if not tokens:
        return ()
    units: list[tuple[str, ...]] = []
    for token in tokens:
        tag = str(getattr(token, "tag", ""))
        if not tag.startswith(_TITLE_CONTENT_TAG_PREFIXES):
            continue
        surface = str(getattr(token, "surface", "")).strip().casefold()
        normalized = str(getattr(token, "normalized", "")).strip().casefold()
        alternatives = tuple(dict.fromkeys(value for value in (surface, normalized) if value))
        if alternatives and alternatives not in units:
            units.append(alternatives)
    return tuple(units)


def _proposition_title_alignment(
    proposition: str,
    title_units: tuple[tuple[str, ...], ...],
) -> tuple[int, int]:
    """Measure literal title coverage in exact proposition bytes.

    The score is used only to prove which source proposition is central. It never rewrites the
    proposition and never becomes visible or canonical identity text.
    """

    source = _source_key(proposition)
    matched_lengths = tuple(
        max(
            (len(value) for value in alternatives if _source_key(value) in source),
            default=0,
        )
        for alternatives in title_units
    )
    return (
        sum(length > 0 for length in matched_lengths),
        sum(matched_lengths),
    )


def _is_body_lead(span: EvidenceSpan, *, lead_end: int) -> bool:
    return span.field.value == "body" and span.start < lead_end


def _title_event_frame_bound(article: RawArticle, span: EvidenceSpan, morphology) -> bool:
    """Prove a proposition's named actor, object and finite action in the source title.

    Later elaboration can repeat more title words without being a different central event.
    This source-only check uses grammatical roles, not a vocabulary of newsworthy actions.
    It does not change the exact proposition or infer equivalence between different verbs.
    """
    from insight_desk.semantic.kiwi_extractor import _predicate_fact_parts

    tokens = _morphology_tokens(span.text, morphology)
    title_tokens = _morphology_tokens(article.title, morphology)
    if not tokens or not title_tokens:
        return False
    parts = _predicate_fact_parts(span.text, tokens)
    if parts is None or parts.object is None:
        return False
    title_units = {str(getattr(token, "normalized", "")) for token in title_tokens}
    # Keep the grammatical subject identified in the complete source sentence.
    # Re-analyzing an isolated name changes both POS tags and segmentation.
    # Require the whole subject at lexical boundaries, never a shared name fragment.
    def title_has_surface(surface: str) -> bool:
        return bool(surface and re.search(r"(?<!\w)" + re.escape(surface) + r"(?!\w)", article.title))

    if not title_has_surface(parts.subject):
        return False
    # Parenthetical aliases qualify the same object, rather than a different event.
    # Omit them for title comparison only; immutable source evidence is unchanged.
    object_surface = []
    depth = 0
    for char in parts.object:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                return False
        elif depth == 0:
            object_surface.append(char)
    if depth:
        return False
    object_tokens = _morphology_tokens("".join(object_surface), morphology) or ()
    object_units = {str(getattr(token, "normalized", "")) for token in object_tokens
                    if str(getattr(token, "tag", "")).startswith("N")
                    or getattr(token, "tag", "") in {"SL", "SH"}}
    if not object_units or not all(unit in title_units or title_has_surface(unit)
                                   for unit in object_units):
        return False
    finite = [index for index, token in enumerate(tokens) if getattr(token, "tag", "") == "EF"]
    if not finite:
        return False
    before_end = tokens[:finite[-1]]
    verbal = [index for index, token in enumerate(before_end)
              if str(getattr(token, "tag", "")).startswith("V")
              or getattr(token, "tag", "") == "XSV"]
    if not verbal:
        return False
    for position, index in enumerate(verbal):
        end = verbal[position + 1] if position + 1 < len(verbal) else finite[-1]
        reported = any(getattr(t, "tag", "") == "EC" and
                       str(getattr(t, "normalized", "")).endswith(("다고", "라고"))
                       for t in tokens[index + 1:end])
        if index != verbal[-1] and not reported:
            continue
        token = tokens[index]
        if getattr(token, "tag", "") == "XSV" and index > 0:
            token = tokens[index - 1]
            if not (str(getattr(token, "tag", "")).startswith("N")
                    or getattr(token, "tag", "") == "XR"):
                continue
        elif getattr(token, "tag", "") != "VV":
            continue
        predicate = str(getattr(token, "normalized", ""))
        if len(predicate) >= 2 and predicate in title_units:
            return True
    return False


def _historical_event_context(article: RawArticle, fact: EventFact) -> bool:
    """Return true only when a date-only event is clearly outside the source freshness horizon."""

    if fact.event_date is None or article.provenance.published_at is None:
        return False
    try:
        event_date = date.fromisoformat(fact.event_date)
    except ValueError:
        return False
    age_days = (article.provenance.published_at.date() - event_date).days
    # Date-only precision cannot establish an exact 72-hour boundary. Four or more calendar days
    # is therefore the first interval that is unambiguously older than the 72-hour source window.
    return age_days > 3


def assess_compatibility_article_understanding(
    article: RawArticle,
    *,
    events: tuple[CandidateEvent, ...],
    facts: Mapping[str, EventFact],
    evidence: Mapping[str, EvidenceSpan],
    morphology: MorphologyPort | None,
    now: datetime,
) -> dict[str, CompatibilityEventUnderstandingDecision]:
    """Jointly classify all extracted events from one article.

    At most one resolved event may remain PRIMARY. Centrality uses immutable source structure and
    morphology-derived actor specificity only; no generated text, verifier output, source/domain
    exception, or topic-specific vocabulary participates.
    """

    decisions = {
        event.event_id: assess_compatibility_event_understanding(
            event,
            facts=facts,
            evidence=evidence,
            morphology=morphology,
            now=now,
        )
        for event in events
    }

    for event in events:
        decision = decisions[event.event_id]
        if (
            decision.status is UnderstandingStatus.RESOLVED
            and decision.article_role is ArticleEventRole.PRIMARY
            and decision.publishable_event
            and len(event.fact_ids) == 1
        ):
            fact = facts.get(event.fact_ids[0])
            if fact is not None and _historical_event_context(article, fact):
                decisions[event.event_id] = CompatibilityEventUnderstandingDecision(
                    status=UnderstandingStatus.RESOLVED,
                    article_role=ArticleEventRole.CONTEXT,
                    topic_relation=TopicRelation.BACKGROUND,
                    publishable_event=False,
                    reasons=decision.reasons + ("historical_event_context",),
                )

    eligible = [
        event
        for event in events
        if decisions[event.event_id].status is UnderstandingStatus.RESOLVED
        and decisions[event.event_id].article_role is ArticleEventRole.PRIMARY
        and decisions[event.event_id].publishable_event
        and len(event.fact_ids) == 1
        and event.fact_ids[0] in facts
    ]
    if not eligible:
        return decisions

    lead_end = _first_sentence_end(article.body, morphology)
    propositions = {
        event.event_id: _exact_proposition_span(
            article,
            event,
            facts=facts,
            evidence=evidence,
        )
        for event in eligible
    }
    if any(span is None for span in propositions.values()):
        for event in eligible:
            decisions[event.event_id] = CompatibilityEventUnderstandingDecision(
                status=UnderstandingStatus.UNRESOLVED,
                article_role=ArticleEventRole.CONTEXT,
                topic_relation=TopicRelation.UNRESOLVED,
                publishable_event=False,
                reasons=("canonical_primary_proposition_unresolved",),
            )
        return decisions

    frozen_propositions = {
        event_id: span
        for event_id, span in propositions.items()
        if span is not None
    }
    lead_events = [
        event
        for event in eligible
        if _is_body_lead(frozen_propositions[event.event_id], lead_end=lead_end)
    ]
    winner: CandidateEvent | None = None
    failure_reason = "article_centrality_unresolved"
    if len(eligible) == 1:
        if len(lead_events) == 1:
            winner = lead_events[0]
    elif len(lead_events) == 1:
        title_units = _title_content_units(article, morphology)
        if title_units:
            alignment = {
                event.event_id: _proposition_title_alignment(
                    frozen_propositions[event.event_id].text,
                    title_units,
                )
                for event in eligible
            }
            best = max(alignment.values())
            best_events = [event for event in eligible if alignment[event.event_id] == best]
            lead = lead_events[0]
            # Broadcast pages may repeat the same transcript. Identical exact
            # propositions are duplicate occurrences, not competing central events.
            if (lead in best_events and best[0] > 0
                    and all(frozen_propositions[event.event_id].text == frozen_propositions[lead.event_id].text
                            for event in best_events)):
                winner = lead_events[0]
            elif _title_event_frame_bound(
                article, frozen_propositions[lead_events[0].event_id], morphology
            ):
                winner = lead_events[0]
        failure_reason = "article_centrality_conflict"

    if winner is None:
        bound = [event for event in eligible if _title_event_frame_bound(
            article, frozen_propositions[event.event_id], morphology)]
        if bound and len({frozen_propositions[event.event_id].text for event in bound}) == 1:
            winner = min(bound, key=lambda event: frozen_propositions[event.event_id].start)

    if winner is None:
        for event in eligible:
            decisions[event.event_id] = CompatibilityEventUnderstandingDecision(
                status=UnderstandingStatus.UNRESOLVED,
                article_role=ArticleEventRole.CONTEXT,
                topic_relation=TopicRelation.UNRESOLVED,
                publishable_event=False,
                reasons=(failure_reason,),
            )
        return decisions

    for event in eligible:
        if event.event_id == winner.event_id:
            continue
        decisions[event.event_id] = replace(
            decisions[event.event_id],
            article_role=ArticleEventRole.CONTEXT,
            topic_relation=TopicRelation.BACKGROUND,
            publishable_event=False,
            reasons=decisions[event.event_id].reasons + ("secondary_article_event",),
        )
    return decisions
