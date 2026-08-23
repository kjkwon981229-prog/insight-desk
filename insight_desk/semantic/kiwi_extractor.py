from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .facts import FactDraft, FactExtractionRequest
from .tooling import KiwiMorphologyHelper, MorphologyToken


_NOUN_TAGS = {"SL", "SN"}
_TOPIC_SURFACES = {"은", "는"}
_TRAILING_PUNCTUATION = " \t\r\n.!?…"
_SENTENCE_TERMINALS = frozenset(".!?…")


@dataclass(frozen=True, slots=True)
class _CasePhrase:
    text: str
    start: int
    marker_end: int


def _is_noun_like(token: MorphologyToken) -> bool:
    return token.tag.startswith("N") or token.tag in _NOUN_TAGS


def _phrase_before_case(
    text: str,
    tokens: tuple[MorphologyToken, ...],
    index: int,
) -> _CasePhrase | None:
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


def _subject_candidate(
    text: str,
    tokens: tuple[MorphologyToken, ...],
) -> _CasePhrase | None:
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

    # A single explicit topic marker wins over embedded nominatives, e.g.
    # "한국은행 부총재는 ... 충격이 없다면 ... 밝혔다".
    if len(topics) == 1:
        return topics[0]
    if topics:
        return None
    if len(nominatives) == 1:
        return nominatives[0]
    return None


def _has_predicate_after(tokens: tuple[MorphologyToken, ...], offset: int) -> bool:
    return any(token.start >= offset and token.tag in {"VV", "XSV"} for token in tokens)


def _object_candidate(
    text: str,
    tokens: tuple[MorphologyToken, ...],
    *,
    after: int,
) -> str | None:
    objects: list[_CasePhrase] = []
    for index, token in enumerate(tokens):
        if token.tag != "JKO" or token.end <= after:
            continue
        phrase = _phrase_before_case(text, tokens, index)
        if phrase is not None and phrase.start >= after:
            objects.append(phrase)
    if not objects:
        return None
    # Korean clauses can contain more than one object-like phrase. The nearest explicit
    # accusative phrase to the clause predicate is the safest bounded structural object.
    return objects[-1].text


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
    """High-precision, local FactExtractorPort implementation.

    It emits a draft only when one complete source sentence exposes exactly one safe subject/topic
    candidate and an explicit Korean verbal predicate after that subject. ``action`` is deliberately
    the exact source clause after the subject marker, not a generated paraphrase or lemma. This
    preserves modifiers, amounts, quoted/prospective language and secondary predicates for later
    evidence validation.

    Evidence windows may be cut at a whitespace boundary by ``EvidenceSegmenter``. Leading or
    trailing sentence fragments that touch such an unsafe cut are skipped rather than interpreted as
    standalone facts. Unsupported/ambiguous sentences likewise emit no draft. This is a
    precision-first extractor, not an NER system, material-event authority, identity authority, or
    publication verifier.
    """

    extractor_id = "kiwi-deterministic-v1"

    def __init__(self) -> None:
        self._kiwi = KiwiMorphologyHelper()

    def extract(self, request: FactExtractionRequest) -> tuple[FactDraft, ...]:
        drafts: list[FactDraft] = []
        for evidence in request.evidence:
            source = request.article.field_text(evidence.field)
            for sentence in self._kiwi.split_sentences(evidence.text):
                absolute_start = evidence.start + sentence.start
                absolute_end = evidence.start + sentence.end
                if not _left_source_boundary_is_safe(source, absolute_start):
                    continue
                if not _right_source_boundary_is_safe(source, absolute_end):
                    continue

                text = sentence.text
                tokens = self._kiwi.analyze(text)
                subject = _subject_candidate(text, tokens)
                if subject is None:
                    continue
                if not _has_predicate_after(tokens, subject.marker_end):
                    continue

                action = text[subject.marker_end:].strip().rstrip(_TRAILING_PUNCTUATION).strip()
                if not action:
                    continue
                # Exact-source containment is a hard contract for this extractor.
                if subject.text not in text or action not in text:
                    raise ValueError("Kiwi deterministic extractor lost exact source surface")

                object_text = _object_candidate(
                    text,
                    tokens,
                    after=subject.marker_end,
                )
                if object_text is not None and object_text not in text:
                    raise ValueError("Kiwi deterministic extractor object lost source surface")

                digest = hashlib.sha256(
                    f"{evidence.evidence_id}\x1f{sentence.start}\x1f{sentence.end}".encode("utf-8")
                ).hexdigest()[:20]
                drafts.append(
                    FactDraft(
                        draft_id=f"kiwi:{digest}",
                        subject=subject.text,
                        action=action,
                        object=object_text,
                        evidence_ids=(evidence.evidence_id,),
                    )
                )
        return tuple(drafts)
