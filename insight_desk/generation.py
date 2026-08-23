from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping, Protocol

from insight_desk.core import CandidateEvent, EvidenceSpan, EventFact
from insight_desk.providers.groq import GROQ_20B


MAX_GENERATED_HEADLINE_CHARS = 120
MAX_GENERATED_SUMMARY_CHARS = 420
_HEADLINE_KOREAN_TOKEN_RE = re.compile(r"[가-힣]{2,}")


class GenerationContractError(ValueError):
    """Raised when Phase 7 generation inputs or outputs violate a structural contract."""


def _first_repeated_korean_headline_token(text: str) -> str | None:
    """Return the first repeated Korean lexical token in a compact feed headline.

    Headlines are intentionally short. Repeating the same two-or-more-syllable Korean token inside
    one headline is a measured visible-output failure mode, while Latin acronyms/numbers are left
    untouched so this gate does not pretend to be a general language model.
    """

    seen: set[str] = set()
    for match in _HEADLINE_KOREAN_TOKEN_RE.finditer(text):
        token = match.group(0)
        if token in seen:
            return token
        seen.add(token)
    return None


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
        return self.evidence_text_for(self.evidence_ids)

    def evidence_text_for(self, evidence_ids: tuple[str, ...]) -> str:
        allowed = set(self.evidence_ids)
        parts: list[str] = []
        for evidence_id in evidence_ids:
            if evidence_id not in allowed:
                raise GenerationContractError(
                    f"requested generation evidence is outside event facts: {evidence_id}"
                )
            parts.append(self.evidence[evidence_id].text)
        return "\n\n".join(parts)

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
        headline = self.headline.strip()
        summary = self.summary.strip()
        if not headline:
            raise GenerationContractError("headline must be non-empty")
        if not summary:
            raise GenerationContractError("summary must be non-empty")
        repeated_token = _first_repeated_korean_headline_token(headline)
        if repeated_token is not None:
            raise GenerationContractError(
                f"headline repeats Korean lexical token: {repeated_token}"
            )
        if len(headline) > MAX_GENERATED_HEADLINE_CHARS:
            raise GenerationContractError(
                f"headline exceeds hard feed ceiling: {len(headline)}>{MAX_GENERATED_HEADLINE_CHARS}"
            )
        if len(summary) > MAX_GENERATED_SUMMARY_CHARS:
            raise GenerationContractError(
                f"summary exceeds hard feed ceiling: {len(summary)}>{MAX_GENERATED_SUMMARY_CHARS}"
            )
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


# NEWS_REWRITE_POLICY_V1 3-1: every article uses the same machine-parseable output structure.
GENERATION_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "summary": {"type": "string"},
    },
    "required": ["headline", "summary"],
    "additionalProperties": False,
}


NEWS_REWRITE_POLICY_V1 = """# 뉴스 기사 자동 처리용 AI 느낌 제거 규칙

뉴스 기사를 자동으로 가져와 요약·재구성하는 파이프라인에 적용하는 버전이다. 사람이 매번 검수하지 않으므로 "사실 보존"을 스타일보다 우선한다.

## 0. 사실 보존 (최우선 원칙)
0-1) 숫자·날짜·고유명사·인용문은 원문 그대로 유지해라.
표현을 다듬더라도 수치, 이름, 직접 인용은 바꾸지 마라. 애매하면 재구성하지 말고 원문 표현을 그대로 써라.
0-2) 원문에 없는 정보는 추가하지 마라.
문장을 자연스럽게 만들려고 배경 설명이나 추측을 새로 넣지 마라.
0-3) 출처 표현은 지우지 마라.
"~에 따르면", "~라고 밝혔다", "~라고 전했다"는 완곡 표현이 아니라 출처 표시다. 기존 규칙 9(단정하기)는 글쓴이 자신의 불필요한 헤지에 적용하는 것이지, 취재원 발언 표시에는 적용하지 않는다.
0-4) 원문 문장을 그대로 옮기지 말고 재구성해라.
문장 구조를 유지한 채 단어만 바꾸지 마라. 핵심 내용만 뽑아 새 문장으로 써라.
0-5) 기간의 시간 방향과 기준점을 바꾸지 마라.
"~만에", "~도 안 돼" 같은 경과시간을 "~안에", "~이내" 같은 미래 기한으로 바꾸지 말고, "~후/뒤/전"의 방향도 원문과 다르게 쓰지 마라.

## 1. 제목(헤드라인)
1-1) 명사형으로 끝내라.
"~다/습니다"로 끝나는 완전한 문장 대신 "OOO 발표", "OOO 논란", "OOO 예정"처럼 명사형으로 마무리해라.
1-2) 낚시성 표현을 빼라.
"충격", "경악", "알고 보니", "이 정도일 줄은" 같은 과장된 클릭 유도 표현은 쓰지 마라. (기존 규칙 14의 연장)
1-3) 길이를 맞춰라.
피드 카드에서 잘리지 않도록 20~30자 내외로 써라. (앱 UI에 맞춰 조정)
1-4) 같은 한국어 내용어를 제목 안에서 반복하지 마라.
짧은 헤드라인에 같은 단어가 두 번 들어가면 문장을 다시 써라.

## 2. 리드문·요약
2-1) 첫 문장에 핵심을 담아라.
누가/무엇을/언제/어디서/왜를 첫 문장에서 요약해라. 배경 설명은 뒤로 미뤄라.
2-2) 기존 문장 규칙(1~8)을 그대로 적용해라.
수식어 제거, 주어 생략, 번역투 제거, 나열 구조 깨기, 구체적 사실 쓰기, 접속사 생략은 원본과 동일하게 적용한다.
2-3) 원문에 없는 주관적 수식어는 특히 금지해라.
뉴스는 객관 서술이 원칙이다. 원문에 없는 감정적·평가적 형용사("놀라운", "충격적인" 등)는 절대 넣지 마라.
2-4) 고정 요약 포맷은 규칙 11의 예외로 둔다.
"3줄 요약"처럼 UX상 필요한 정형 포맷이라면 개수를 억지로 바꾸지 않아도 된다. 규칙 11(3의 법칙 피하기)은 논증적 글쓰기용이지 구조화된 요약 포맷에는 적용하지 않는다.

## 3. 자동화 파이프라인
3-1) 기사마다 같은 출력 구조를 유지해라.
헤드라인 + 요약(N줄) 같은 템플릿을 모든 기사에 동일하게 적용해라. 형식이 흔들리면 파싱과 UI 렌더링이 깨진다.
3-2) 불확실하면 변형을 최소화해라.
표현을 다듬다가 의미가 달라질 위험이 있으면, 자연스러움보다 원문 보존을 우선해라.
3-3) 메타 발언 금지는 그대로 유지해라.
"이 기사에서는", "요약하자면" 같은 표현은 자동 요약에서도 넣지 마라. (기존 규칙 13)
"""


def build_generation_prompt(request: GenerationRequest) -> str:
    return (
        "아래 EVENT FACTS와 EVIDENCE만 사용해 한국어 브리핑 headline과 summary를 작성하라.\n"
        "EVIDENCE 밖의 사실, 배경지식, 원인, 평가, 수치, 날짜, 인물/기관명을 추가하지 마라.\n"
        "아래 NEWS_REWRITE_POLICY_V1 전체를 적용하라. 불확실하면 자연스러움보다 원문 보존을 우선하라.\n\n"
        + NEWS_REWRITE_POLICY_V1
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
    META_PHRASE = "meta_phrase"
    TEMPORAL_RELATION_MISMATCH = "temporal_relation_mismatch"


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
_DURATION = r"(?P<duration>\d[\d,]*(?:\.\d+)?\s*(?:년|개월|주|일|시간|분|초))"
_TEMPORAL_RELATION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "elapsed_under",
        re.compile(_DURATION + r"(?:도)?\s*(?:채\s*)?안\s*(?:돼|되어|되|지나|지났)"),
    ),
    (
        "future_within",
        re.compile(_DURATION + r"\s*(?:안에|이내(?:에)?|내에)"),
    ),
    (
        "elapsed_at",
        re.compile(_DURATION + r"\s*(?:만에|만인)"),
    ),
    (
        "after",
        re.compile(_DURATION + r"\s*(?:후(?:에)?|뒤(?:에)?)"),
    ),
    (
        "before",
        re.compile(_DURATION + r"\s*전(?:에)?"),
    ),
)
_QUOTE_PATTERNS = (
    re.compile(r'"([^"\n]+)"'),
    re.compile(r"“([^”\n]+)”"),
    re.compile(r"‘([^’\n]+)’"),
    re.compile(r"「([^」\n]+)」"),
    re.compile(r"『([^』\n]+)』"),
)
_META_PHRASES = ("이 기사에서는", "요약하자면")


def _date_atoms(text: str) -> tuple[str, ...]:
    values = {match.group(0) for match in _KOREAN_DATE_RE.finditer(text)}
    values.update(match.group(0) for match in _SEPARATED_DATE_RE.finditer(text))
    return tuple(sorted(values))


def _number_atoms(text: str) -> tuple[str, ...]:
    return tuple(sorted({match.group(0) for match in _NUMBER_RE.finditer(text)}))


def _quoted_atoms(text: str) -> tuple[str, ...]:
    values: set[str] = set()
    for pattern in _QUOTE_PATTERNS:
        values.update(
            match.group(1).strip()
            for match in pattern.finditer(text)
            if match.group(1).strip()
        )
    return tuple(sorted(values))


def _temporal_relation_atoms(text: str) -> tuple[str, ...]:
    values: set[str] = set()
    for relation, pattern in _TEMPORAL_RELATION_PATTERNS:
        for match in pattern.finditer(text):
            duration = re.sub(r"\s+", "", match.group("duration"))
            values.add(f"{duration}|{relation}")
    return tuple(sorted(values))


def validate_preservation(
    request: GenerationRequest,
    draft: GeneratedDraft,
) -> PreservationReport:
    """Deterministically reject source-literal and automation-policy violations before verification.

    This gate blocks novel event/evidence references, dates, numeric expressions, quoted text,
    measured temporal-direction changes, and the explicit NEWS_REWRITE_POLICY_V1 3-3 meta phrases.
    It intentionally does not pretend to prove general semantic support; that remains the frozen
    Cloudflare + local mDeBERTa verification role.
    """

    issues: list[PreservationIssue] = []
    if draft.event_id != request.event.event_id:
        issues.append(
            PreservationIssue(PreservationIssueCode.EVENT_ID_MISMATCH, draft.event_id)
        )

    allowed_evidence = set(request.evidence_ids)
    known_citations: list[str] = []
    for evidence_id in draft.evidence_ids:
        if evidence_id not in allowed_evidence:
            issues.append(
                PreservationIssue(PreservationIssueCode.UNKNOWN_EVIDENCE, evidence_id)
            )
        else:
            known_citations.append(evidence_id)

    source = request.evidence_text_for(tuple(known_citations)) if known_citations else ""
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

    source_temporal_relations = set(_temporal_relation_atoms(source))
    for value in _temporal_relation_atoms(generated):
        if value not in source_temporal_relations:
            issues.append(
                PreservationIssue(PreservationIssueCode.TEMPORAL_RELATION_MISMATCH, value)
            )

    for value in _quoted_atoms(generated):
        if value not in source:
            issues.append(
                PreservationIssue(PreservationIssueCode.NOVEL_QUOTED_TEXT, value)
            )

    for phrase in _META_PHRASES:
        if phrase in generated:
            issues.append(PreservationIssue(PreservationIssueCode.META_PHRASE, phrase))

    return PreservationReport(accepted=not issues, issues=tuple(issues))
