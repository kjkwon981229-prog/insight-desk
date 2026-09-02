from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .facts import FactDraft, FactExtractionRequest
from .tooling import KiwiMorphologyHelper, MorphologySourceOffsetError, MorphologyToken


_NOUN_TAGS = {"SL", "SN"}
_TOPIC_SURFACES = {"은", "는"}
_TRAILING_PUNCTUATION = " \t\r\n.!?…"
_SENTENCE_TERMINALS = frozenset(".!?…")
_PREDICATE_TAGS = frozenset({"VV", "VA", "XSV", "VCP", "VCN"})
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
    proposition_start: int = 0


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


def _structural_proposition_start(
    text: str,
    tokens: tuple[MorphologyToken, ...],
    subject: _CasePhrase,
) -> int:
    """Exclude only a structurally detached, non-predicative prefix before the fact subject.

    Some publisher bodies encode a byline/location/source prefix in the same extracted line as the
    lead and separate it with ``|``. That prefix is not part of the event proposition. We narrow the
    exact-source range only when the final delimiter before the subject is followed solely by
    whitespace and the prefix itself contains no case particle or predicate. This keeps contextual
    clauses such as ``업계에 따르면 | ...`` attached and avoids publisher/name-specific rules.
    """

    if subject.start <= 0:
        return 0
    separator = text.rfind("|", 0, subject.start)
    if separator < 0:
        return 0
    if text[separator + 1 : subject.start].strip():
        return 0
    prefix = text[:separator]
    if not prefix.strip() or any(char in _SENTENCE_TERMINALS for char in prefix):
        return 0
    prefix_tokens = tuple(token for token in tokens if token.end <= separator)
    if not prefix_tokens:
        return 0
    if any(token.tag.startswith("J") or token.tag in _PREDICATE_TAGS for token in prefix_tokens):
        return 0
    return subject.start


def _predicate_fact_parts(text: str, tokens: tuple[MorphologyToken, ...]) -> _LiteralFactParts | None:
    subject = _subject_candidate(text, tokens)
    if subject is None or not _has_predicate_after(tokens, subject.marker_end):
        return None
    action = text[subject.marker_end:].strip().rstrip(_TRAILING_PUNCTUATION).strip()
    if not action:
        return None
    return _LiteralFactParts(
        subject.text,
        action,
        _object_candidate(text, tokens, after=subject.marker_end),
        proposition_start=_structural_proposition_start(text, tokens, subject),
    )


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


def _structural_line_ranges(text: str) -> tuple[tuple[int, int], ...]:
    """Return exact non-empty ranges that never cross an acquired source block boundary."""

    ranges: list[tuple[int, int]] = []
    cursor = 0
    while cursor < len(text):
        newline = text.find("\n", cursor)
        end = len(text) if newline < 0 else newline
        if end > cursor and text[end - 1] == "\r":
            end -= 1
        if end > cursor and text[cursor:end].strip():
            ranges.append((cursor, end))
        if newline < 0:
            break
        cursor = newline + 1
    return tuple(ranges)


class KiwiDeterministicFactExtractor:
    """Precision-first local FactExtractorPort implementation with exact-source output only."""

    extractor_id = "kiwi-deterministic-v1"

    def __init__(self) -> None:
        self._kiwi = KiwiMorphologyHelper()

    def extract(self, request: FactExtractionRequest) -> tuple[FactDraft, ...]:
        drafts: list[FactDraft] = []
        for evidence in request.evidence:
            source = request.article.field_text(evidence.field)
            for line_start, line_end in _structural_line_ranges(evidence.text):
                structural_line = evidence.text[line_start:line_end]
                try:
                    sentences = self._kiwi.split_sentences(structural_line)
                except MorphologySourceOffsetError:
                    # Exact source provenance cannot be established for this source block.
                    continue
                for sentence in sentences:
                    absolute_start = evidence.start + line_start + sentence.start
                    absolute_end = evidence.start + line_start + sentence.end
                    if not _left_source_boundary_is_safe(source, absolute_start):
                        continue
                    if not _right_source_boundary_is_safe(source, absolute_end):
                        continue
                    text = sentence.text
                    try:
                        tokens = self._kiwi.analyze(text)
                    except MorphologySourceOffsetError:
                        # Never clip or repair unusable coordinates: skip only this sentence.
                        continue
                    parts = _predicate_fact_parts(text, tokens) or _nominal_fact_parts(text)
                    if parts is None:
                        continue
                    if parts.subject not in text or parts.action not in text:
                        raise ValueError("Kiwi deterministic extractor lost exact source surface")
                    if parts.object is not None and parts.object not in text:
                        raise ValueError("Kiwi deterministic extractor object lost source surface")
                    proposition_start = absolute_start + parts.proposition_start
                    if proposition_start >= absolute_end:
                        raise ValueError("Kiwi deterministic extractor produced an invalid proposition range")
                    digest = hashlib.sha256(
                        f"{evidence.evidence_id}\x1f{proposition_start}\x1f{absolute_end}".encode("utf-8")
                    ).hexdigest()[:20]
                    drafts.append(
                        FactDraft(
                            draft_id=f"kiwi:{digest}",
                            subject=parts.subject,
                            action=parts.action,
                            object=parts.object,
                            evidence_ids=(evidence.evidence_id,),
                            source_start=proposition_start,
                            source_end=absolute_end,
                        )
                    )
        return tuple(drafts)
