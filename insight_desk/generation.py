from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping, Protocol

from insight_desk.core import CandidateEvent, EvidenceSpan, EventFact
from insight_desk.providers.groq import GROQ_20B


class GenerationContractError(ValueError):
    """Raised when Phase 7 generation inputs or outputs violate a structural contract."""


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    event: CandidateEvent
    facts: Mapping[str, EventFact]
    evidence: Mapping[str, EvidenceSpan]

    def __post_init__(self) -> None:
        if not self.event.fact_ids:
            raise GenerationContractError("generation requires at least one event fact")
        for fact_id in self.event.fact_ids:
            fact = self.facts.get(fact_id)
            if fact is None:
                raise GenerationContractError(f"event references missing fact: {fact_id}")
            if fact.fact_id != fact_id:
                raise GenerationContractError(f"fact index key mismatch: {fact_id}")
            for evidence_id in fact.evidence_ids:
                span = self.evidence.get(evidence_id)
                if span is None:
                    raise GenerationContractError(
                        f"fact references missing evidence: {evidence_id}"
                    )
                if span.evidence_id != evidence_id:
                    raise GenerationContractError(
                        f"evidence index key mismatch: {evidence_id}"
                    )
                if span.article_id not in self.event.article_ids:
                    raise GenerationContractError(
                        f"evidence outside event provenance: {evidence_id}"
                    )

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        ordered: list[str] = []
        seen: set[str] = set()
        for fact_id in self.event.fact_ids:
            for evidence_id in self.facts[fact_id].evidence_ids:
                if evidence_id not in seen:
                    seen.add(evidence_id)
                    ordered.append(evidence_id)
        return tuple(ordered)

    @property
    def evidence_text(self) -> str:
        return "\n\n".join(self.evidence[evidence_id].text for evidence_id in self.evidence_ids)

    @property
    def fact_text(self) -> str:
        lines: list[str] = []
        for fact_id in self.event.fact_ids:
            fact = self.facts[fact_id]
            parts = [f"subject={fact.subject}", f"action={fact.action}"]
            if fact.object is not None:
                parts.append(f"object={fact.object}")
            if fact.event_date is not None:
                parts.append(f"event_date={fact.event_date}")
            if fact.location is not None:
                parts.append(f"location={fact.location}")
            if fact.cause is not None:
                parts.append(f"cause={fact.cause}")
            if fact.participants:
                parts.append("participants=" + ", ".join(fact.participants))
            lines.append(f"{fact.fact_id}: " + " | ".join(parts))
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class GeneratedDraft:
    event_id: str
    headline: str
    summary: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.event_id.strip():
            raise GenerationContractError("event_id must be non-empty")
        if not self.headline.strip():
            raise GenerationContractError("headline must be non-empty")
        if not self.summary.strip():
            raise GenerationContractError("summary must be non-empty")
        if not self.evidence_ids:
            raise GenerationContractError("generated draft must cite evidence")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise GenerationContractError("generated draft evidence ids must be unique")

    @property
    def combined_text(self) -> str:
        return f"{self.headline}\n{self.summary}"


class StructuredGenerationClient(Protocol):
    model_id: str

    def structured_json(
        self,
        *,
        prompt: str,
        schema: dict[str, object],
        schema_name: str,
        system_prompt: str = "Follow the JSON schema exactly. Do not output commentary.",
    ) -> dict[str, object]: ...


GENERATION_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "summary": {"type": "string"},
    },
    "required": ["headline", "summary"],
    "additionalProperties": False,
}


NEWS_REWRITE_POLICY_V1_RECOVERED = """NEWS_REWRITE_POLICY_V1 — recovered rules only
0. fact preservation
0-1 숫자·날짜·고유명사·인용문은 원문 표현을 유지한다.
0-2 원문 외 정보를 추가하지 않는다.
0-3 출처 표현을 유지한다.
0-4 원문을 그대로 복사하지 않고 재구성한다.
1. title
1-1 명사형으로 작성한다.
1-2 낚시성 표현을 제거한다.
1-3 20~30자 내외로 작성한다.
2. lead/summary
2-1 첫 문장에 핵심을 요약한다.
2-2 수식어·번역투·나열 구조를 줄이는 기존 원칙을 적용한다.
2-3 주관적 수식어를 사용하지 않는다.
2-4 고정 요약 포맷을 사용할 수 있다.
"""


def build_generation_prompt(request: GenerationRequest) -> str:
    return (
        "아래 EVENT FACTS와 EVIDENCE만 사용해 한국어 브리핑 headline과 summary를 작성하라.\n"
        "EVIDENCE 밖의 사실, 배경지식, 원인, 평가, 수치, 날짜, 인물/기관명을 추가하지 마라.\n"
        "아래 recovered policy만 적용하며, 복구되지 않은 규칙을 추정해 추가하지 마라.\n\n"
        + NEWS_REWRITE_POLICY_V1_RECOVERED
        + "\nEVENT ID:\n"
        + request.event.event_id
        + "\n\nEVENT FACTS:\n"
        + request.fact_text
        + "\n\nEVIDENCE:\n"
        + request.evidence_text
    )


@dataclass(slots=True)
class Groq20BBriefingGenerator:
    client: StructuredGenerationClient

    def __post_init__(self) -> None:
        if self.client.model_id != GROQ_20B:
            raise GenerationContractError("briefing generation is frozen to Groq GPT-OSS 20B")

    def generate(self, request: GenerationRequest) -> GeneratedDraft:
        result = self.client.structured_json(
            prompt=build_generation_prompt(request),
            schema=GENERATION_SCHEMA,
            schema_name="insight_desk_briefing_generation",
            system_prompt=(
                "Write only evidence-grounded Korean briefing text. "
                "Return JSON matching the schema exactly."
            ),
        )
        headline = result.get("headline")
        summary = result.get("summary")
        if not isinstance(headline, str) or not isinstance(summary, str):
            raise GenerationContractError("Groq generation output is outside headline/summary contract")
        return GeneratedDraft(
            event_id=request.event.event_id,
            headline=headline,
            summary=summary,
            evidence_ids=request.evidence_ids,
        )


class PreservationIssueCode(StrEnum):
    EVENT_ID_MISMATCH = "event_id_mismatch"
    UNKNOWN_EVIDENCE = "unknown_evidence"
    NOVEL_DATE = "novel_date"
    NOVEL_NUMBER = "novel_number"
    NOVEL_QUOTED_TEXT = "novel_quoted_text"


@dataclass(frozen=True, slots=True)
class PreservationIssue:
    code: PreservationIssueCode
    value: str


@dataclass(frozen=True, slots=True)
class PreservationReport:
    accepted: bool
    issues: tuple[PreservationIssue, ...]

    def __post_init__(self) -> None:
        if self.accepted == bool(self.issues):
            raise GenerationContractError(
                "accepted preservation report must have no issues and rejected report must have issues"
            )


_KOREAN_DATE_RE = re.compile(r"\d{4}년\s*\d{1,2}월(?:\s*\d{1,2}일)?")
_SEPARATED_DATE_RE = re.compile(r"\d{4}[./-]\d{1,2}(?:[./-]\d{1,2})?")
_NUMBER_RE = re.compile(
    r"\d[\d,]*(?:\.\d+)?(?:%|％|조원|억원|원|억달러|달러|만명|명|개|건|회|위|점|경기|이닝|시즌|년|월|일|시|분|초)?"
)
_QUOTE_PATTERNS = (
    re.compile(r'"([^"\n]+)"'),
    re.compile(r"“([^”\n]+)”"),
    re.compile(r"‘([^’\n]+)’"),
    re.compile(r"「([^」\n]+)」"),
    re.compile(r"『([^』\n]+)』"),
)


def _date_atoms(text: str) -> tuple[str, ...]:
    values = {match.group(0) for match in _KOREAN_DATE_RE.finditer(text)}
    values.update(match.group(0) for match in _SEPARATED_DATE_RE.finditer(text))
    return tuple(sorted(values))


def _number_atoms(text: str) -> tuple[str, ...]:
    return tuple(sorted({match.group(0) for match in _NUMBER_RE.finditer(text)}))


def _quoted_atoms(text: str) -> tuple[str, ...]:
    values: set[str] = set()
    for pattern in _QUOTE_PATTERNS:
        values.update(match.group(1).strip() for match in pattern.finditer(text) if match.group(1).strip())
    return tuple(sorted(values))


def validate_preservation(
    request: GenerationRequest,
    draft: GeneratedDraft,
) -> PreservationReport:
    """Deterministically reject source-literal mutations before semantic verification.

    This gate intentionally does not pretend to prove general semantic support. It blocks novel
    event/evidence references plus novel dates, numeric expressions, and quoted text. General factual
    additions and paraphrase entailment remain the responsibility of the frozen Cloudflare + local
    mDeBERTa verification policy.
    """

    issues: list[PreservationIssue] = []
    if draft.event_id != request.event.event_id:
        issues.append(
            PreservationIssue(PreservationIssueCode.EVENT_ID_MISMATCH, draft.event_id)
        )

    allowed_evidence = set(request.evidence_ids)
    for evidence_id in draft.evidence_ids:
        if evidence_id not in allowed_evidence:
            issues.append(
                PreservationIssue(PreservationIssueCode.UNKNOWN_EVIDENCE, evidence_id)
            )

    source = request.evidence_text
    generated = draft.combined_text

    source_dates = set(_date_atoms(source))
    for value in _date_atoms(generated):
        if value not in source_dates:
            issues.append(PreservationIssue(PreservationIssueCode.NOVEL_DATE, value))

    source_numbers = set(_number_atoms(source))
    generated_dates = set(_date_atoms(generated))
    for value in _number_atoms(generated):
        if any(value in date for date in generated_dates):
            continue
        if value not in source_numbers:
            issues.append(PreservationIssue(PreservationIssueCode.NOVEL_NUMBER, value))

    for value in _quoted_atoms(generated):
        if value not in source:
            issues.append(
                PreservationIssue(PreservationIssueCode.NOVEL_QUOTED_TEXT, value)
            )

    return PreservationReport(accepted=not issues, issues=tuple(issues))
