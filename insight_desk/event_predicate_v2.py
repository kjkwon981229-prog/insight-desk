from __future__ import annotations

"""Shared structural owner for EventFact predicate completeness.

This module answers one narrow question: does an extracted action expose a clause-complete
predicate, rather than merely containing a verb inside an attributive nominal description?
It intentionally owns no topic, source, materiality, centrality, or publication policy.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class MorphologyPort(Protocol):
    def analyze(self, text: str): ...


class PredicateCompleteness(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class EventPredicateAssessment:
    completeness: PredicateCompleteness
    reason: str


_VERBAL_STEMS = ("V", "XSV", "XSA")
_FINITE_ENDINGS = {"EF"}
_CONNECTIVE_ENDINGS = {"EC"}
_AUXILIARY_VERBS = {"VX"}
_ATTRIBUTIVE_ENDING = "ETM"
_NOMINAL_TAG_PREFIXES = ("NN", "NP", "NR", "SN", "SL", "SH")


def _tag(token: object) -> str:
    return str(getattr(token, "tag", ""))


def _is_verbal(tag: str) -> bool:
    return tag.startswith(_VERBAL_STEMS)


def _is_nominal(tag: str) -> bool:
    return tag.startswith(_NOMINAL_TAG_PREFIXES)


def assess_event_predicate(
    action: str,
    *,
    morphology: MorphologyPort | None,
) -> EventPredicateAssessment:
    """Return structural clause completeness without lexical event exceptions.

    A verb used only inside an attributive clause followed by a nominal head (VV ... ETM NNG) is
    structurally incomplete. A finite ending is direct evidence of completeness. Test doubles and
    compatibility morphology ports historically expose only a verbal tag; that reduced observation
    remains COMPLETE unless it contains positive evidence of an incomplete attributive structure.
    """

    if not action.strip() or morphology is None:
        return EventPredicateAssessment(
            PredicateCompleteness.UNRESOLVED,
            "morphology_unavailable",
        )
    try:
        tokens = tuple(morphology.analyze(action))
    except Exception:
        return EventPredicateAssessment(
            PredicateCompleteness.UNRESOLVED,
            "morphology_unavailable",
        )
    if not tokens:
        return EventPredicateAssessment(
            PredicateCompleteness.UNRESOLVED,
            "morphology_empty",
        )

    tags = tuple(_tag(token) for token in tokens)
    if not any(_is_verbal(tag) for tag in tags):
        return EventPredicateAssessment(
            PredicateCompleteness.INCOMPLETE,
            "verbal_predicate_missing",
        )

    if any(tag in _FINITE_ENDINGS for tag in tags):
        return EventPredicateAssessment(
            PredicateCompleteness.COMPLETE,
            "finite_clause",
        )

    last_verbal_index = max(index for index, tag in enumerate(tags) if _is_verbal(tag))
    later_tags = tags[last_verbal_index + 1 :]
    if _ATTRIBUTIVE_ENDING in later_tags:
        etm_index = last_verbal_index + 1 + later_tags.index(_ATTRIBUTIVE_ENDING)
        if any(_is_nominal(tag) for tag in tags[etm_index + 1 :]):
            return EventPredicateAssessment(
                PredicateCompleteness.INCOMPLETE,
                "attributive_nominal_description",
            )

    if (
        any(tag in _CONNECTIVE_ENDINGS for tag in later_tags)
        and any(tag in _AUXILIARY_VERBS for tag in later_tags)
    ):
        return EventPredicateAssessment(
            PredicateCompleteness.UNRESOLVED,
            "auxiliary_clause_without_finite_ending",
        )

    return EventPredicateAssessment(
        PredicateCompleteness.COMPLETE,
        "verbal_predicate_compact_observation",
    )
