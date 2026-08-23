from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Callable, Protocol

from .facts import FactDraft, FactExtractionRequest, FactExtractorPort


_TRAILING_PUNCTUATION = " \t\r\n.!?…"
_SENTENCE_TERMINALS = frozenset(".!?…")
_SIMPLE_SUBJECT_RE = re.compile(
    r"^\s*(?P<subject>[0-9A-Za-z가-힣·&()（）.'\- ]{1,60}?)(?P<particle>은|는|이|가)\s*(?P<action>.+?)\s*$"
)
_NESTED_SUBJECT_RE = re.compile(r"[0-9A-Za-z가-힣)）](?:은|는|이|가)(?=\s)")


@dataclass(frozen=True, slots=True)
class SurfaceSentence:
    text: str
    start: int
    end: int


def _surface_sentences(text: str) -> tuple[SurfaceSentence, ...]:
    """Split conservatively while preserving exact offsets and source surfaces."""

    if not text:
        return ()
    output: list[SurfaceSentence] = []
    start = 0
    index = 0
    while index < len(text):
        char = text[index]
        terminal = char in _SENTENCE_TERMINALS
        newline = char in "\r\n"
        if not terminal and not newline:
            index += 1
            continue
        end = index + 1 if terminal else index
        raw = text[start:end]
        left_trim = len(raw) - len(raw.lstrip())
        right_trim = len(raw.rstrip())
        sentence_start = start + left_trim
        sentence_end = start + right_trim
        if sentence_end > sentence_start:
            output.append(SurfaceSentence(text=text[sentence_start:sentence_end], start=sentence_start, end=sentence_end))
        index += 1
        while index < len(text) and (text[index].isspace() or text[index] in _SENTENCE_TERMINALS):
            index += 1
        start = index
    if start < len(text):
        raw = text[start:]
        left_trim = len(raw) - len(raw.lstrip())
        sentence_start = start + left_trim
        sentence_end = len(text.rstrip())
        if sentence_end > sentence_start:
            output.append(SurfaceSentence(text=text[sentence_start:sentence_end], start=sentence_start, end=sentence_end))
    return tuple(output)


def _left_boundary_safe(source: str, start: int) -> bool:
    if start <= 0:
        return True
    cursor = start - 1
    while cursor >= 0 and source[cursor].isspace():
        if source[cursor] in "\r\n":
            return True
        cursor -= 1
    return cursor < 0 or source[cursor] in _SENTENCE_TERMINALS


def _right_boundary_safe(source: str, end: int) -> bool:
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


def _surface_parts(text: str) -> tuple[str, str] | None:
    clean = text.strip().rstrip(_TRAILING_PUNCTUATION).strip()
    if not clean or not clean.endswith("다"):
        return None
    match = _SIMPLE_SUBJECT_RE.match(clean)
    if match is None:
        return None
    subject = match.group("subject").strip()
    action = match.group("action").strip()
    if not subject or len(subject) > 48 or len(action) < 3:
        return None
    if _NESTED_SUBJECT_RE.search(action):
        return None
    return subject, action


class SurfaceDeterministicFactExtractor:
    """Last-resort exact-source parser for simple declarative Korean clauses only."""

    extractor_id = "surface-deterministic-v1"

    def extract(self, request: FactExtractionRequest) -> tuple[FactDraft, ...]:
        drafts: list[FactDraft] = []
        for evidence in request.evidence:
            source = request.article.field_text(evidence.field)
            for sentence in _surface_sentences(evidence.text):
                absolute_start = evidence.start + sentence.start
                absolute_end = evidence.start + sentence.end
                if not _left_boundary_safe(source, absolute_start) or not _right_boundary_safe(source, absolute_end):
                    continue
                parts = _surface_parts(sentence.text)
                if parts is None:
                    continue
                subject, action = parts
                digest = hashlib.sha256(
                    f"{evidence.evidence_id}\x1f{sentence.start}\x1f{sentence.end}".encode("utf-8")
                ).hexdigest()[:20]
                drafts.append(
                    FactDraft(
                        draft_id=f"surface:{digest}",
                        subject=subject,
                        action=action,
                        object=None,
                        evidence_ids=(evidence.evidence_id,),
                        source_start=absolute_start,
                        source_end=absolute_end,
                    )
                )
        return tuple(drafts)


class PosAnalyzer(Protocol):
    def pos(self, text: str): ...


class PecabDeterministicFactExtractor:
    """PeCab-backed validation of the conservative exact-surface parser."""

    extractor_id = "pecab-surface-v1"

    def __init__(self, analyzer: PosAnalyzer | None = None) -> None:
        if analyzer is None:
            from pecab import PeCab  # type: ignore[import-not-found]
            analyzer = PeCab()
        self._analyzer = analyzer
        self._surface = SurfaceDeterministicFactExtractor()

    def extract(self, request: FactExtractionRequest) -> tuple[FactDraft, ...]:
        output: list[FactDraft] = []
        for draft in self._surface.extract(request):
            if draft.source_start is None or draft.source_end is None:
                continue
            parent = next((item for item in request.evidence if item.evidence_id == draft.evidence_ids[0]), None)
            if parent is None:
                continue
            source = request.article.field_text(parent.field)
            sentence = source[draft.source_start : draft.source_end]
            try:
                tagged = self._analyzer.pos(sentence)
            except (RuntimeError, ValueError, OSError):
                continue
            tags = [str(tag) for _, tag in tagged]
            has_case = any(tag.startswith("J") for tag in tags)
            has_predicate = any(tag.startswith("V") or "XSV" in tag or "VCP" in tag for tag in tags)
            if has_case and has_predicate:
                output.append(
                    FactDraft(
                        draft_id=draft.draft_id.replace("surface:", "pecab:", 1),
                        subject=draft.subject,
                        action=draft.action,
                        object=draft.object,
                        evidence_ids=draft.evidence_ids,
                        source_start=draft.source_start,
                        source_end=draft.source_end,
                    )
                )
        return tuple(output)


@dataclass(slots=True)
class LazyFactExtractor:
    extractor_id: str
    factory: Callable[[], FactExtractorPort]
    _delegate: FactExtractorPort | None = field(default=None, init=False, repr=False)

    def extract(self, request: FactExtractionRequest) -> tuple[FactDraft, ...]:
        if self._delegate is None:
            try:
                self._delegate = self.factory()
            except (ImportError, RuntimeError, OSError):
                return ()
        return self._delegate.extract(request)


@dataclass(slots=True)
class SequentialFactExtractor:
    """Return the first non-empty exact-source fact set from independent routes."""

    routes: tuple[FactExtractorPort, ...]
    extractor_id: str = "kiwi-deterministic-v1"
    _route_stats: dict[str, dict[str, int]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if len(self.routes) < 1:
            raise ValueError("fact extraction requires at least one route")
        ids = [route.extractor_id for route in self.routes]
        if len(ids) != len(set(ids)):
            raise ValueError("fact extraction route ids must be unique")
        self._route_stats = {
            route_id: {"calls": 0, "empty": 0, "selected": 0, "drafts": 0}
            for route_id in ids
        }

    @property
    def route_stats(self) -> dict[str, dict[str, int]]:
        return {route_id: dict(stats) for route_id, stats in self._route_stats.items()}

    def extract(self, request: FactExtractionRequest) -> tuple[FactDraft, ...]:
        for route in self.routes:
            stats = self._route_stats[route.extractor_id]
            stats["calls"] += 1
            drafts = route.extract(request)
            if drafts:
                stats["selected"] += 1
                stats["drafts"] += len(drafts)
                return drafts
            stats["empty"] += 1
        return ()


def build_resilient_fact_extractor() -> SequentialFactExtractor:
    from .kiwi_extractor import KiwiDeterministicFactExtractor

    return SequentialFactExtractor(
        routes=(
            LazyFactExtractor(extractor_id="kiwi-deterministic-route", factory=KiwiDeterministicFactExtractor),
            LazyFactExtractor(extractor_id="pecab-surface-route", factory=PecabDeterministicFactExtractor),
            SurfaceDeterministicFactExtractor(),
        )
    )
