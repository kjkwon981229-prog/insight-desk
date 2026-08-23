from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .facts import FactDraft, FactExtractionRequest
from .tooling import KiwiMorphologyHelper, MorphologySourceOffsetError, MorphologyToken


_NOUN_TAGS = {"SL", "SN"}
_TOPIC_SURFACES = {"은", "는"}
_TRAILING_PUNCTUATION = " \t\r\n.!?…"
_SENTENCE_TERMINALS = frozenset(".!?…")
# This is deliberately tiny: each nominal structure must come from a measured locked failure.
# It is not a general headline/event-type vocabulary.
_EXPLICIT_NOMINAL_ACTIONS = ("선발투수 예고",)


@dataclass(frozen=True, slots=True)
class _CasePhrase:
    text: str
    start: int
    marker_end: int


@dataclass(frozen=True, slots=True)
class _LiteralFactParts:
    subject: str
    action: str
    object: str | None


def _is_noun_like(token: MorphologyToken) -> bool:
    return token.tag.startswith("N") or token.tag in _NOUN_TAGS


def _phrase_before_case(text: str, tokens: tuple[MorphologyToken, ...], index: int) -> _CasePhrase | None:
    if index <= 0:
        return None
    marker = tokens[index]
    cursor = index - 1
    if not _is_noun_like(tokens[cursor]):
        return None
    start = tokens[cursor].start
    while cursor - 1 >= 0 and _is_noun_like(tokens[cursor - 1]):
        cursor -= 1
        start = tokens[cursor].start
    phrase = text[start:marker.start].strip()
    if not phrase:
        return None
    return _CasePhrase(phrase, start, marker.end)


def _subject_candidate(text: str, tokens: tuple[MorphologyToken, ...]) -> _CasePhrase | None:
    topics: list[_CasePhrase] = []
    nominatives: list[_CasePhrase] = []
    for index, token in enumerate(tokens):
        if token.tag == "JX" and token.surface in _TOPIC_SURFACES:
            phrase = _phrase_before_case(text, tokens, index)
            if phrase is not None:
                topics.append(phrase)
        elif token.tag == "JKS":
            phrase = _phrase_before_case(text, tokens, index)
            if phrase is not None:
                nominatives.append(phrase)

    if len(topics) == 1:
        return topics[0]
    if topics:
        return None
    if len(nominatives) == 1:
        return nominatives[0]
    return None


def _has_predicate_after(tokens: tuple[MorphologyToken, ...], offset: int) -> bool:
    return any(token.start >= offset and token.tag in {"VV", "XSV"} for token in tokens)


def _object_candidate(text: str, tokens: tuple[MorphologyToken, ...], *, after: int) -> str | None:
    objects: list[_CasePhrase] = []
    for index, token in enumerate(tokens):
        if token.tag != "JKO" or token.end <= after:
            continue
        phrase = _phrase_before_case(text, tokens, index)
        if phrase is not None and phrase.start >= after:
            objects.append(phrase)
    if not objects:
        return None
    return objects[-1].text


def _predicate_fact_parts(text: str, tokens: tuple[MorphologyToken, ...]) -> _LiteralFactParts | None:
    subject = _subject_candidate(text, tokens)
    if subject is None or not _has_predicate_after(tokens, subject.marker_end):
        return None
    action = text[subject.marker_end:].strip().rstrip(_TRAILING_PUNCTUATION).strip()
    if not action:
        return None
    return _LiteralFactParts(subject.text, action, _object_candidate(text, tokens, after=subject.marker_end))


def _nominal_fact_parts(text: str) -> _LiteralFactParts | None:
    clean = text.strip().rstrip(_TRAILING_PUNCTUATION).strip()
    for action in _EXPLICIT_NOMINAL_ACTIONS:
        if clean.endswith(action):
            subject = clean[: -len(action)].strip()
            if subject:
                return _LiteralFactParts(subject=subject, action=action, object=None)
    return None


def _left_source_boundary_is_safe(source: str, start: int) -> bool:
    if start <= 0:
        return True
    cursor = start - 1
    while cursor >= 0 and source[cursor].isspace():
        if source[cursor] in "\r\n":
            return True
        cursor -= 1
    return cursor < 0 or source[cursor] in _SENTENCE_TERMINALS


def _right_source_boundary_is_safe(source: str, end: int) -> bool:
    if end >= len(source):
        return True
    if end > 0 and source[end - 1] in _SENTENCE_TERMINALS:
        return True
    cursor = end
    while cursor < len(source) and source[cursor].isspace():
        if source[cursor] in "\r\n":
            return True
        cursor += 1
    return False


class KiwiDeterministicFactExtractor:
    """Precision-first local FactExtractorPort implementation with exact-source output only."""

    extractor_id = "kiwi-deterministic-v1"

    def __init__(self) -> None:
        self._kiwi = KiwiMorphologyHelper()

    def extract(self, request: FactExtractionRequest) -> tuple[FactDraft, ...]:
        drafts: list[FactDraft] = []
        for evidence in request.evidence:
            source = request.article.field_text(evidence.field)
            try:
                sentences = self._kiwi.split_sentences(evidence.text)
            except MorphologySourceOffsetError:
                # Exact source provenance cannot be established for this evidence window.
                # Fail closed locally instead of aborting the article or the full pipeline.
                continue
            for sentence in sentences:
                absolute_start = evidence.start + sentence.start
                absolute_end = evidence.start + sentence.end
                if not _left_source_boundary_is_safe(source, absolute_start):
                    continue
                if not _right_source_boundary_is_safe(source, absolute_end):
                    continue
                text = sentence.text
                try:
                    tokens = self._kiwi.analyze(text)
                except MorphologySourceOffsetError:
                    # Kiwi can occasionally return unusable coordinates for unusual live text.
                    # Never clip or repair them: skip only this sentence and preserve exactness.
                    continue
                parts = _predicate_fact_parts(text, tokens) or _nominal_fact_parts(text)
                if parts is None:
                    continue
                if parts.subject not in text or parts.action not in text:
                    raise ValueError("Kiwi deterministic extractor lost exact source surface")
                if parts.object is not None and parts.object not in text:
                    raise ValueError("Kiwi deterministic extractor object lost source surface")
                digest = hashlib.sha256(
                    f"{evidence.evidence_id}\x1f{sentence.start}\x1f{sentence.end}".encode("utf-8")
                ).hexdigest()[:20]
                drafts.append(
                    FactDraft(
                        draft_id=f"kiwi:{digest}",
                        subject=parts.subject,
                        action=parts.action,
                        object=parts.object,
                        evidence_ids=(evidence.evidence_id,),
                        source_start=absolute_start,
                        source_end=absolute_end,
                    )
                )
        return tuple(drafts)
