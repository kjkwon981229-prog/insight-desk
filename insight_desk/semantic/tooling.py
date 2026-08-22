from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class MorphologyToken:
    surface: str
    normalized: str
    tag: str
    start: int
    end: int

    def __post_init__(self) -> None:
        if not self.surface:
            raise ValueError("surface must be non-empty")
        if not self.normalized:
            raise ValueError("normalized must be non-empty")
        if not self.tag:
            raise ValueError("tag must be non-empty")
        if self.start < 0 or self.end <= self.start:
            raise ValueError("token offsets must describe a non-empty source span")


@dataclass(frozen=True, slots=True)
class SentenceSpan:
    text: str
    start: int
    end: int

    def __post_init__(self) -> None:
        if not self.text:
            raise ValueError("sentence text must be non-empty")
        if self.start < 0 or self.end <= self.start:
            raise ValueError("sentence offsets must describe a non-empty source span")
        if self.end - self.start != len(self.text):
            raise ValueError("sentence offsets must match sentence text length")


class KiwiMorphologyHelper:
    """Local Korean morphology/source-offset helper with deliberately narrow authority.

    This helper is not a named-entity recognizer, fact extractor, event-identity authority,
    material-event classifier, or publication verifier. The original EvidenceSpan remains the
    source of truth; morphology/sentence boundaries are only a deterministic scaffold around that
    source text.
    """

    def __init__(self) -> None:
        try:
            from kiwipiepy import Kiwi
        except ImportError as exc:  # optional dependency stays out of the base runtime
            raise RuntimeError(
                "kiwipiepy is optional; install insight-desk[semantic-local] to enable morphology"
            ) from exc
        self._kiwi = Kiwi()

    def analyze(self, text: str) -> tuple[MorphologyToken, ...]:
        if not text:
            return ()
        output: list[MorphologyToken] = []
        for token in self._kiwi.tokenize(text):
            start = int(token.start)
            end = start + int(token.len)
            if start < 0 or end > len(text) or end <= start:
                raise ValueError("Kiwi returned a token outside the supplied source text")
            surface = text[start:end]
            output.append(
                MorphologyToken(
                    surface=surface,
                    normalized=str(token.form),
                    tag=str(token.tag),
                    start=start,
                    end=end,
                )
            )
        return tuple(output)

    def split_sentences(self, text: str) -> tuple[SentenceSpan, ...]:
        if not text:
            return ()
        output: list[SentenceSpan] = []
        for sentence in self._kiwi.split_into_sents(text):
            start = int(sentence.start)
            end = int(sentence.end)
            if start < 0 or end > len(text) or end <= start:
                raise ValueError("Kiwi returned a sentence outside the supplied source text")
            surface = text[start:end]
            if surface != str(sentence.text):
                raise ValueError("Kiwi sentence text no longer matches exact source offsets")
            output.append(SentenceSpan(text=surface, start=start, end=end))
        return tuple(output)


@dataclass(frozen=True, slots=True)
class AliasCandidate:
    value: str
    score: float
    input_index: int

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("alias candidate value must be non-empty")
        if not 0.0 <= self.score <= 100.0:
            raise ValueError("alias candidate score must be in [0, 100]")
        if self.input_index < 0:
            raise ValueError("input_index must be non-negative")


class RapidFuzzAliasRetriever:
    """Local string candidate retrieval only; never a same-entity or same-event authority."""

    def __init__(self) -> None:
        try:
            from rapidfuzz import fuzz, process
        except ImportError as exc:  # optional dependency stays out of the base runtime
            raise RuntimeError(
                "RapidFuzz is optional; install insight-desk[semantic-local] to enable alias retrieval"
            ) from exc
        self._fuzz = fuzz
        self._process = process

    def retrieve(
        self,
        query: str,
        candidates: Iterable[str],
        *,
        limit: int = 5,
    ) -> tuple[AliasCandidate, ...]:
        if not query.strip():
            raise ValueError("query must be non-empty")
        if limit < 1:
            raise ValueError("limit must be >= 1")
        values = tuple(value for value in candidates if value.strip())
        if not values:
            return ()
        matches = self._process.extract(
            query,
            values,
            scorer=self._fuzz.WRatio,
            limit=min(limit, len(values)),
        )
        return tuple(
            AliasCandidate(value=str(value), score=float(score), input_index=int(index))
            for value, score, index in matches
        )
