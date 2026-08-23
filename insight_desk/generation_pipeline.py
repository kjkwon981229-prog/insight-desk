from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Protocol

from insight_desk.core import EvidenceField, RenderMode
from insight_desk.generation import (
    GeneratedDraft,
    GenerationContractError,
    GenerationRequest,
    PreservationReport,
    validate_preservation,
)
from insight_desk.providers.transport import ProviderTransportError


FALLBACK_HEADLINE_MAX_CHARS = 96
FALLBACK_SUMMARY_MAX_CHARS = 360
_SENTENCE_END_RE = re.compile(r"[.!?。！？](?=\s|$)")
_CLAUSE_MARKS = ("…", "·", ":", ";", ",", "，")


class DraftGenerator(Protocol):
    def generate(self, request: GenerationRequest) -> GeneratedDraft: ...


class GenerationAttemptKind(StrEnum):
    PRIMARY = "primary"
    ALTERNATE = "alternate"
    EXTRACTIVE_FALLBACK = "extractive_fallback"


class GenerationAttemptStatus(StrEnum):
    ACCEPTED = "accepted"
    PROVIDER_ERROR = "provider_error"
    OUTPUT_CONTRACT_REJECTED = "output_contract_rejected"
    PRESERVATION_REJECTED = "preservation_rejected"


@dataclass(frozen=True, slots=True)
class GenerationAttempt:
    kind: GenerationAttemptKind
    sequence: int
    status: GenerationAttemptStatus
    error_code: str | None = None

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError("generation attempt sequence must be >= 1")
        error_statuses = {
            GenerationAttemptStatus.PROVIDER_ERROR,
            GenerationAttemptStatus.OUTPUT_CONTRACT_REJECTED,
        }
        if self.status in error_statuses and not self.error_code:
            raise ValueError("failed generation attempt must carry error_code")
        if self.status not in error_statuses and self.error_code is not None:
            raise ValueError("only failed generation attempt may carry error_code")


@dataclass(frozen=True, slots=True)
class GenerationRecoveryResult:
    event_id: str
    draft: GeneratedDraft
    render_mode: RenderMode
    preservation: PreservationReport
    attempts: tuple[GenerationAttempt, ...]

    def __post_init__(self) -> None:
        if self.draft.event_id != self.event_id:
            raise ValueError("generation recovery result cannot cross event identity")
        if not self.preservation.accepted:
            raise ValueError("final generation recovery draft must pass deterministic preservation")
        if not self.attempts:
            raise ValueError("generation recovery result must record at least one attempt")
        if self.attempts[-1].status is not GenerationAttemptStatus.ACCEPTED:
            raise ValueError("final generation attempt must be accepted")


def _bounded_source_excerpt(text: str, *, max_chars: int) -> str:
    """Return a bounded exact-source excerpt without inventing replacement text."""

    source = text.strip()
    if len(source) <= max_chars:
        return source

    window = source[:max_chars]
    sentence_ends = [match.end() for match in _SENTENCE_END_RE.finditer(window)]
    if sentence_ends:
        return window[: sentence_ends[-1]].rstrip()

    line_end = window.rfind("\n")
    if line_end >= max_chars // 3:
        return window[:line_end].rstrip()

    clause_end = max(window.rfind(mark) for mark in _CLAUSE_MARKS)
    if clause_end >= max_chars // 2:
        return window[: clause_end + 1].rstrip()

    return window.rstrip()


def _first_nonempty_line(text: str) -> tuple[str, int] | None:
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped:
            return stripped, offset + len(line)
        offset += len(line)
    stripped = text.strip()
    if stripped:
        return stripped, len(text)
    return None


class ExtractiveFallbackGenerator:
    """Zero-generation fallback using bounded exact-source excerpts."""

    def generate(self, request: GenerationRequest) -> GeneratedDraft:
        evidence_ids = request.evidence_ids
        spans = [request.evidence[evidence_id] for evidence_id in evidence_ids]
        title_spans = [span for span in spans if span.field is EvidenceField.TITLE]
        body_spans = [span for span in spans if span.field is EvidenceField.BODY]

        summary_source = body_spans[0] if body_spans else spans[0]
        summary_text = summary_source.text.strip()

        if title_spans:
            headline = _bounded_source_excerpt(
                title_spans[0].text,
                max_chars=FALLBACK_HEADLINE_MAX_CHARS,
            )
        else:
            first_line = _first_nonempty_line(summary_text)
            if first_line is None:
                headline = _bounded_source_excerpt(
                    spans[0].text,
                    max_chars=FALLBACK_HEADLINE_MAX_CHARS,
                )
            else:
                first_line_text, first_line_end = first_line
                headline = _bounded_source_excerpt(
                    first_line_text,
                    max_chars=FALLBACK_HEADLINE_MAX_CHARS,
                )
                if (
                    len(first_line_text) <= FALLBACK_HEADLINE_MAX_CHARS
                    and first_line_end < len(summary_text)
                ):
                    remainder = summary_text[first_line_end:].strip()
                    if remainder:
                        summary_text = remainder

        summary = _bounded_source_excerpt(
            summary_text,
            max_chars=FALLBACK_SUMMARY_MAX_CHARS,
        )
        if not summary:
            summary = headline

        return GeneratedDraft(
            event_id=request.event.event_id,
            headline=headline,
            summary=summary,
            evidence_ids=evidence_ids,
        )


def _provider_error_code(exc: ProviderTransportError) -> str:
    status = str(exc.status_code) if exc.status_code is not None else "none"
    return f"{exc.failure_kind.value}:{status}"


def _attempt_generated(
    generator: DraftGenerator,
    request: GenerationRequest,
    *,
    kind: GenerationAttemptKind,
    sequence: int,
) -> tuple[GeneratedDraft | None, PreservationReport | None, GenerationAttempt]:
    try:
        draft = generator.generate(request)
    except GenerationContractError as exc:
        return (
            None,
            None,
            GenerationAttempt(
                kind=kind,
                sequence=sequence,
                status=GenerationAttemptStatus.OUTPUT_CONTRACT_REJECTED,
                error_code=type(exc).__name__,
            ),
        )
    except ProviderTransportError as exc:
        return (
            None,
            None,
            GenerationAttempt(
                kind=kind,
                sequence=sequence,
                status=GenerationAttemptStatus.PROVIDER_ERROR,
                error_code=_provider_error_code(exc),
            ),
        )
    except Exception as exc:
        return (
            None,
            None,
            GenerationAttempt(
                kind=kind,
                sequence=sequence,
                status=GenerationAttemptStatus.PROVIDER_ERROR,
                error_code=f"{type(exc).__name__.lower()[:80] or 'unknown'}",
            ),
        )
    preservation = validate_preservation(request, draft)
    if not preservation.accepted:
        return (
            None,
            preservation,
            GenerationAttempt(
                kind=kind,
                sequence=sequence,
                status=GenerationAttemptStatus.PRESERVATION_REJECTED,
            ),
        )
    return (
        draft,
        preservation,
        GenerationAttempt(
            kind=kind,
            sequence=sequence,
            status=GenerationAttemptStatus.ACCEPTED,
        ),
    )


def _should_skip_immediate_primary_retry(attempt: GenerationAttempt) -> bool:
    if attempt.status is not GenerationAttemptStatus.PROVIDER_ERROR:
        return False
    code = (attempt.error_code or "").casefold()
    return code.startswith("rate_limited:") or code.startswith("free_quota_exhausted:")


def _configured_zero_cost_alternate() -> DraftGenerator | None:
    """Return the configured independent Gemini route without making a provider call."""

    from insight_desk.providers.gemini import GeminiBriefingGenerator, GeminiStructuredClient

    if not GeminiStructuredClient.configured():
        return None
    return GeminiBriefingGenerator(GeminiStructuredClient.from_env())


def generate_with_recovery(
    request: GenerationRequest,
    *,
    primary: DraftGenerator,
    alternate: DraftGenerator | None = None,
) -> GenerationRecoveryResult:
    """Apply zero-cost recovery: primary → bounded retry → alternate → exact source.

    Rate-limit or quota evidence suppresses an immediate primary retry. When the caller does not
    inject an alternate, an independently configured Gemini Free route is discovered lazily. No
    Gemini request is made when primary generation succeeds. Deterministic exact source remains the
    final non-provider fallback and no paid route exists.
    """

    attempts: list[GenerationAttempt] = []
    sequence = 0

    for _ in range(2):
        sequence += 1
        draft, preservation, attempt = _attempt_generated(
            primary,
            request,
            kind=GenerationAttemptKind.PRIMARY,
            sequence=sequence,
        )
        attempts.append(attempt)
        if draft is not None and preservation is not None:
            return GenerationRecoveryResult(
                event_id=request.event.event_id,
                draft=draft,
                render_mode=RenderMode.GENERATED,
                preservation=preservation,
                attempts=tuple(attempts),
            )
        if _should_skip_immediate_primary_retry(attempt):
            break

    resolved_alternate = alternate if alternate is not None else _configured_zero_cost_alternate()
    if resolved_alternate is not None:
        sequence += 1
        draft, preservation, attempt = _attempt_generated(
            resolved_alternate,
            request,
            kind=GenerationAttemptKind.ALTERNATE,
            sequence=sequence,
        )
        attempts.append(attempt)
        if draft is not None and preservation is not None:
            return GenerationRecoveryResult(
                event_id=request.event.event_id,
                draft=draft,
                render_mode=RenderMode.GENERATED,
                preservation=preservation,
                attempts=tuple(attempts),
            )

    sequence += 1
    draft = ExtractiveFallbackGenerator().generate(request)
    preservation = validate_preservation(request, draft)
    if not preservation.accepted:
        raise ValueError("extractive fallback violated deterministic preservation contract")
    attempts.append(
        GenerationAttempt(
            kind=GenerationAttemptKind.EXTRACTIVE_FALLBACK,
            sequence=sequence,
            status=GenerationAttemptStatus.ACCEPTED,
        )
    )
    return GenerationRecoveryResult(
        event_id=request.event.event_id,
        draft=draft,
        render_mode=RenderMode.EXTRACTIVE_FALLBACK,
        preservation=preservation,
        attempts=tuple(attempts),
    )
