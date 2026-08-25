from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from insight_desk.core import CandidateEvent, EvidenceSpan, EventFact, RawArticle

from .evidence import EvidenceSegmenter
from .facts import FactDraft, FactExtractionRequest, FactExtractorPort


_EVENT_DAY_RE = re.compile(
    r"(?<!\d)(?:(20\d{2})년\s*)?(?:(1[0-2]|0?[1-9])월\s*)?([0-3]?\d)일"
    r"(?!\s*(?:동안|간|뒤|후|째))"
)
_CONTEXT_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9.+-]*|[가-힣]{2,}")
_CONTEXT_COMMON_TOKENS = frozenset(
    {
        "이번",
        "해당",
        "지난",
        "통해",
        "대한",
        "관련",
        "따르면",
        "진행된",
        "진행했다",
        "밝혔다",
        "기업",
        "업무",
        "데이터",
        "인공지능",
        "ai",
    }
)
_REFERENTIAL_FACT_LEADS = (
    "이번 ",
    "해당 ",
    "이 거래",
    "이 경매",
    "이번 거래",
    "이번 경매",
    "이를 ",
    "인수 대상",
    "매각 대상",
)
_SENTENCE_TERMINALS = frozenset(".!?…。！？")


def _previous_sentence(source: str, start: int) -> str:
    if start <= 0:
        return ""
    cursor = min(start, len(source)) - 1
    while cursor >= 0 and (source[cursor].isspace() or source[cursor] in _SENTENCE_TERMINALS):
        cursor -= 1
    if cursor < 0:
        return ""
    end = cursor + 1
    while cursor >= 0 and source[cursor] not in _SENTENCE_TERMINALS and source[cursor] not in "\r\n":
        cursor -= 1
    return source[cursor + 1 : end].strip()


def _context_tokens(value: str) -> frozenset[str]:
    return frozenset(
        token.casefold()
        for token in _CONTEXT_TOKEN_RE.findall(value)
        if token.casefold() not in _CONTEXT_COMMON_TOKENS
    )


def _resolve_day_match(match: re.Match[str], reference: datetime) -> str | None:
    year_text, month_text, day_text = match.groups()
    day = int(day_text)
    if day < 1 or day > 31:
        return None

    year = int(year_text) if year_text else reference.year
    month = int(month_text) if month_text else reference.month
    if year_text is None and month_text is not None and month > reference.month:
        year -= 1
    if month_text is None and day > reference.day + 1:
        previous_month = reference.replace(day=1) - timedelta(days=1)
        year = previous_month.year
        month = previous_month.month
    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError:
        return None


def _bound_prior_event_date(
    *,
    source: str,
    start: int,
    current_text: str,
    published_at: datetime | None,
) -> str | None:
    """Recover only a date that is visibly bound to the exact fact sentence.

    Exact sentence evidence deliberately stays byte-preserved. When the sentence drops a date that
    appears in the immediately preceding source sentence, retain that date only if the two sentences
    share distinctive event anchors. Referential continuations such as ``이번 경매`` need one shared
    anchor; ordinary sentences require two. Unrelated historical background therefore stays detached.
    """

    if published_at is None or _EVENT_DAY_RE.search(current_text) is not None:
        return None
    previous = _previous_sentence(source, start)
    matches = tuple(_EVENT_DAY_RE.finditer(previous))
    if not previous or not matches:
        return None

    shared = _context_tokens(previous) & _context_tokens(current_text)
    referential = current_text.lstrip().startswith(_REFERENTIAL_FACT_LEADS)
    if len(shared) < (1 if referential else 2):
        return None
    return _resolve_day_match(matches[-1], published_at)


@dataclass(frozen=True, slots=True)
class SemanticArticleResult:
    article_id: str
    extractor_id: str
    evidence: tuple[EvidenceSpan, ...]
    facts: tuple[EventFact, ...]
    events: tuple[CandidateEvent, ...]

    def __post_init__(self) -> None:
        if not self.article_id.strip():
            raise ValueError("article_id must be non-empty")
        if not self.extractor_id.strip():
            raise ValueError("extractor_id must be non-empty")
        if len({span.evidence_id for span in self.evidence}) != len(self.evidence):
            raise ValueError("semantic result evidence ids must be unique")
        if len({fact.fact_id for fact in self.facts}) != len(self.facts):
            raise ValueError("semantic result fact ids must be unique")
        if len({event.event_id for event in self.events}) != len(self.events):
            raise ValueError("semantic result event ids must be unique")


class SemanticPipeline:
    """Turn one immutable RawArticle into evidence-bound facts and conservative event candidates.

    Extraction windows remain broad enough for deterministic parsing, while FactDrafts that carry
    exact source coordinates are rebound to sentence-sized EvidenceSpans before they become EventFacts.
    One FactDraft still becomes one CandidateEvent; identity merging remains a later explicit stage.
    """

    def __init__(self, *, segmenter: EvidenceSegmenter | None = None) -> None:
        self.segmenter = segmenter or EvidenceSegmenter()

    def extract_article(
        self,
        article: RawArticle,
        *,
        topic_id: str,
        extractor: FactExtractorPort,
    ) -> SemanticArticleResult:
        extractor_id = str(getattr(extractor, "extractor_id", "")).strip()
        if not extractor_id:
            raise ValueError("fact extractor must expose non-empty extractor_id")

        extraction_evidence = self.segmenter.segment(article)
        if not extraction_evidence:
            return SemanticArticleResult(
                article_id=article.article_id,
                extractor_id=extractor_id,
                evidence=(),
                facts=(),
                events=(),
            )

        request = FactExtractionRequest(
            article=article,
            topic_id=topic_id,
            evidence=extraction_evidence,
        )
        drafts = extractor.extract(request)
        if not isinstance(drafts, tuple):
            raise TypeError("FactExtractorPort must return tuple[FactDraft, ...]")
        if len({draft.draft_id for draft in drafts}) != len(drafts):
            raise ValueError("fact extractor returned duplicate draft ids")

        evidence_by_id = {span.evidence_id: span for span in extraction_evidence}
        result_evidence = list(extraction_evidence)
        facts: list[EventFact] = []
        events: list[CandidateEvent] = []
        for draft in drafts:
            if not isinstance(draft, FactDraft):
                raise TypeError("fact extractor returned a non-FactDraft value")
            draft.validate_against(request)
            fact_id = self._stable_id("fact", article.article_id, extractor_id, draft.draft_id)
            event_id = self._stable_id("event", article.article_id, extractor_id, draft.draft_id)

            fact_evidence_ids = draft.evidence_ids
            fact_draft = draft
            if draft.has_exact_source_range:
                parent = evidence_by_id[draft.evidence_ids[0]]
                assert draft.source_start is not None and draft.source_end is not None
                sentence_evidence_id = self._stable_id(
                    "evfact",
                    article.article_id,
                    parent.evidence_id,
                    str(draft.source_start),
                    str(draft.source_end),
                )
                sentence_span = EvidenceSpan.from_article(
                    evidence_id=sentence_evidence_id,
                    article=article,
                    field=parent.field,
                    start=draft.source_start,
                    end=draft.source_end,
                )
                result_evidence.append(sentence_span)
                fact_evidence_ids = (sentence_evidence_id,)

                if draft.event_date is None:
                    inherited_date = _bound_prior_event_date(
                        source=article.field_text(parent.field),
                        start=draft.source_start,
                        current_text=sentence_span.text,
                        published_at=article.provenance.published_at,
                    )
                    if inherited_date is not None:
                        fact_draft = replace(draft, event_date=inherited_date)

            fact = fact_draft.to_event_fact(
                fact_id=fact_id,
                evidence_ids=fact_evidence_ids,
            )
            facts.append(fact)
            events.append(
                CandidateEvent(
                    event_id=event_id,
                    topic_id=topic_id,
                    fact_ids=(fact_id,),
                    article_ids=(article.article_id,),
                )
            )

        return SemanticArticleResult(
            article_id=article.article_id,
            extractor_id=extractor_id,
            evidence=tuple(result_evidence),
            facts=tuple(facts),
            events=tuple(events),
        )

    @staticmethod
    def _stable_id(prefix: str, *parts: str) -> str:
        digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]
        return f"{prefix}-{digest}"
