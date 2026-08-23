from __future__ import annotations

import hashlib
from dataclasses import dataclass

from insight_desk.core import CandidateEvent, EvidenceSpan, EventFact, RawArticle

from .evidence import EvidenceSegmenter
from .facts import FactDraft, FactExtractionRequest, FactExtractorPort


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

            fact = draft.to_event_fact(
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
