from __future__ import annotations

import hashlib
from typing import Protocol
from urllib.parse import urlparse

from insight_desk.core import FailureKind, RawArticle, SourceProvenance

from .models import (
    AcquisitionError,
    AcquisitionResult,
    ArticleCandidate,
    ExtractedArticle,
    ExtractionQuality,
    ExtractionQualityPolicy,
    FetchedPage,
)


class HtmlFetcher(Protocol):
    method_id: str

    def fetch(self, url: str) -> FetchedPage: ...


class ArticleExtractor(Protocol):
    method_id: str

    def extract(self, html: str, *, url: str) -> ExtractedArticle: ...


class HtmlRenderer(Protocol):
    method_id: str

    def render(self, url: str) -> FetchedPage: ...


class AcquisitionPipeline:
    """Acquire one article without paraphrasing or semantic rewriting.

    The primary HTML body is extracted first. Playwright may be used only when the primary
    extraction fails the deterministic quality gate. The selected extracted body becomes the
    immutable RawArticle source for later EvidenceSpan offsets.
    """

    def __init__(
        self,
        *,
        fetcher: HtmlFetcher,
        primary_extractor: ArticleExtractor,
        fallback_renderer: HtmlRenderer | None = None,
        quality_policy: ExtractionQualityPolicy | None = None,
    ) -> None:
        self.fetcher = fetcher
        self.primary_extractor = primary_extractor
        self.fallback_renderer = fallback_renderer
        self.quality_policy = quality_policy or ExtractionQualityPolicy()

    def acquire(self, candidate: ArticleCandidate) -> AcquisitionResult:
        fetched = self.fetcher.fetch(candidate.url)
        primary, primary_quality = self._extract_and_assess(fetched)
        if primary is not None and primary_quality.acceptable:
            return self._build_result(
                candidate=candidate,
                page=fetched,
                extracted=primary,
                quality=primary_quality,
                method=f"{self.fetcher.method_id}+{self.primary_extractor.method_id}",
                fallback_used=False,
            )

        if self.fallback_renderer is None:
            reasons = primary_quality.reasons if primary_quality is not None else ("primary_extraction_failed",)
            raise AcquisitionError(
                FailureKind.EXTRACTION_EMPTY,
                "primary extraction rejected: " + ",".join(reasons),
            )

        rendered = self.fallback_renderer.render(candidate.url)
        fallback, fallback_quality = self._extract_and_assess(rendered)
        if fallback is None or not fallback_quality.acceptable:
            reasons = fallback_quality.reasons if fallback_quality is not None else ("fallback_extraction_failed",)
            raise AcquisitionError(
                FailureKind.EXTRACTION_EMPTY,
                "fallback extraction rejected: " + ",".join(reasons),
            )
        return self._build_result(
            candidate=candidate,
            page=rendered,
            extracted=fallback,
            quality=fallback_quality,
            method=f"{self.fallback_renderer.method_id}+{self.primary_extractor.method_id}",
            fallback_used=True,
        )

    def _extract_and_assess(
        self, page: FetchedPage
    ) -> tuple[ExtractedArticle | None, ExtractionQuality]:
        try:
            extracted = self.primary_extractor.extract(page.html, url=page.url)
        except AcquisitionError:
            return None, ExtractionQuality(
                acceptable=False,
                character_count=0,
                reasons=("extractor_error",),
            )
        quality = self.quality_policy.assess(extracted.body)
        return extracted, quality

    @staticmethod
    def _source_id(candidate: ArticleCandidate) -> str:
        host = (urlparse(candidate.url).hostname or candidate.source_name).lower()
        return "web:" + host

    def _build_result(
        self,
        *,
        candidate: ArticleCandidate,
        page: FetchedPage,
        extracted: ExtractedArticle,
        quality: ExtractionQuality,
        method: str,
        fallback_used: bool,
    ) -> AcquisitionResult:
        body = extracted.body.strip()
        if not body:
            raise AcquisitionError(FailureKind.EXTRACTION_EMPTY, "selected extraction is empty")
        title = (extracted.page_title or candidate.search_title).strip()
        provenance = SourceProvenance(
            source_id=self._source_id(candidate),
            source_name=candidate.source_name,
            url=candidate.url,
            retrieved_via=f"{candidate.retrieved_via}+{method}",
            fetched_at=page.fetched_at,
            published_at=candidate.published_at,
        )
        article = RawArticle(
            article_id=candidate.candidate_id,
            provenance=provenance,
            title=title,
            body=body,
            topic_ids=candidate.topic_ids,
            query=candidate.query,
        )
        return AcquisitionResult(
            article=article,
            extraction_method=method,
            fallback_used=fallback_used,
            quality=quality,
            source_html_sha256=hashlib.sha256(page.html.encode("utf-8")).hexdigest(),
        )
