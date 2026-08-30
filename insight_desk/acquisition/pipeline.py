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

    Route order is deliberately cheap-first and independent-extractor-aware:
    HTTP+primary → HTTP+deterministic article/main → rendered+primary → rendered+article/main.
    Every route must pass the same deterministic quality gate before it can become RawArticle.
    """

    def __init__(
        self,
        *,
        fetcher: HtmlFetcher,
        primary_extractor: ArticleExtractor,
        fallback_renderer: HtmlRenderer | None = None,
        fallback_extractor: ArticleExtractor | None = None,
        quality_policy: ExtractionQualityPolicy | None = None,
    ) -> None:
        self.fetcher = fetcher
        self.primary_extractor = primary_extractor
        self.fallback_renderer = fallback_renderer
        if fallback_extractor is None:
            from .runtime import ArticleMainTextExtractor

            fallback_extractor = ArticleMainTextExtractor()
        self.fallback_extractor = fallback_extractor
        self.quality_policy = quality_policy or ExtractionQualityPolicy()

    def acquire(self, candidate: ArticleCandidate) -> AcquisitionResult:
        fetched = self.fetcher.fetch(candidate.url)

        primary, primary_quality = self._extract_and_assess(
            fetched,
            extractor=self.primary_extractor,
        )
        if primary is not None and primary_quality.acceptable:
            return self._build_result(
                candidate=candidate,
                page=fetched,
                extracted=primary,
                quality=primary_quality,
                method=f"{self.fetcher.method_id}+{self.primary_extractor.method_id}",
                fallback_used=False,
            )

        static_fallback, static_quality = self._extract_and_assess(
            fetched,
            extractor=self.fallback_extractor,
        )
        if static_fallback is not None and static_quality.acceptable:
            return self._build_result(
                candidate=candidate,
                page=fetched,
                extracted=static_fallback,
                quality=static_quality,
                method=f"{self.fetcher.method_id}+{self.fallback_extractor.method_id}",
                fallback_used=True,
            )

        if self.fallback_renderer is None:
            reasons = self._combined_reasons(primary_quality, static_quality)
            raise AcquisitionError(
                FailureKind.EXTRACTION_EMPTY,
                "static extraction routes rejected: " + ",".join(reasons),
            )

        rendered = self.fallback_renderer.render(candidate.url)
        rendered_primary, rendered_primary_quality = self._extract_and_assess(
            rendered,
            extractor=self.primary_extractor,
        )
        if rendered_primary is not None and rendered_primary_quality.acceptable:
            return self._build_result(
                candidate=candidate,
                page=rendered,
                extracted=rendered_primary,
                quality=rendered_primary_quality,
                method=f"{self.fallback_renderer.method_id}+{self.primary_extractor.method_id}",
                fallback_used=True,
            )

        rendered_fallback, rendered_fallback_quality = self._extract_and_assess(
            rendered,
            extractor=self.fallback_extractor,
        )
        if rendered_fallback is not None and rendered_fallback_quality.acceptable:
            return self._build_result(
                candidate=candidate,
                page=rendered,
                extracted=rendered_fallback,
                quality=rendered_fallback_quality,
                method=f"{self.fallback_renderer.method_id}+{self.fallback_extractor.method_id}",
                fallback_used=True,
            )

        reasons = self._combined_reasons(
            primary_quality,
            static_quality,
            rendered_primary_quality,
            rendered_fallback_quality,
        )
        raise AcquisitionError(
            FailureKind.EXTRACTION_EMPTY,
            "all extraction routes rejected: " + ",".join(reasons),
        )

    def _extract_and_assess(
        self,
        page: FetchedPage,
        *,
        extractor: ArticleExtractor,
    ) -> tuple[ExtractedArticle | None, ExtractionQuality]:
        try:
            extracted = extractor.extract(page.html, url=page.url)
        except AcquisitionError:
            return None, ExtractionQuality(
                acceptable=False,
                character_count=0,
                reasons=(f"{extractor.method_id}_error",),
            )
        quality = self.quality_policy.assess(extracted.body)
        return extracted, quality

    @staticmethod
    def _combined_reasons(*qualities: ExtractionQuality) -> tuple[str, ...]:
        reasons: list[str] = []
        for quality in qualities:
            reasons.extend(quality.reasons or ("quality_rejected",))
        return tuple(dict.fromkeys(reasons)) or ("extraction_failed",)

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
