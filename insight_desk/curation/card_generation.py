from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Protocol, Sequence

from .sentences import split_sentences
from .reasons import build_reason, reason_is_grounded
from .grounding import CardLine, GroundingResult, NounExtractor, check_format, check_grounding
from .scoring import ScoreResult


class CardClient(Protocol):
    def structured_json(
        self,
        *,
        prompt: str,
        schema: dict[str, Any],
        schema_name: str,
        system_prompt: str = "",
    ) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class Card:
    reason: str
    lines: tuple[str, str, str]
    evidence: tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]


@dataclass(frozen=True, slots=True)
class CardResult:
    status: str  # "ok" | "unavailable" | "rejected"
    card: Card | None
    code: str
    weak: bool = False
    # 결정적으로 만든 "고른 이유". 외부 모델이 없어도(unavailable) 쓸 수 있도록 따로 담는다.
    reason: str = ""


CARD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "evidence": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                },
                "required": ["text", "evidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["lines"],
    "additionalProperties": False,
}


def build_prompt(*, title: str, sentences: Sequence[str], topic_label: str) -> str:
    lines = [f"제목: {title}", f"주제: {topic_label}", "", "문장 목록:"]
    for i, s in enumerate(sentences):
        lines.append(f"[{i}] {s}")
    lines.append("")
    lines.append("위 문장 목록에서 핵심 사실 3개를 뽑아 JSON으로 작성하세요.")
    lines.append("규칙:")
    lines.append("- 각 줄은 text와 evidence로 구성합니다. text는 개조식으로, 한 줄에 한 가지 사실만 50자 이내로 쓰고 "
                 "명사형(~함, ~임, ~됨, ~전망, ~예정 등)으로 맺습니다. '~다/~요'로 끝내거나 ';'로 사실을 이어 붙이지 않습니다.")
    lines.append("- evidence는 그 사실이 들어 있는 문장 번호 1~3개입니다. 위 목록의 번호만 사용합니다.")
    lines.append("- 숫자·고유명사·영어 이름·따옴표 인용은 인용한 문장에 적힌 그대로 씁니다. "
                 "연도·날짜·수치는 인용한 문장에 적혀 있을 때만 쓰고, '올해/내년/지난달' 같은 표현을 연도로 바꾸지 않습니다.")
    lines.append("- 원문에 없는 수치·날짜·원인·평가·추측은 금지합니다.")
    lines.append("- 영어 원문이어도 줄은 한국어로 작성합니다(숫자·고유명사는 영어 유지).")
    return "\n".join(lines)


_REPAIR_HINTS = {
    "format:length": "각 줄을 50자 이내, 한 줄에 한 가지 사실로 줄이세요.",
    "format:evidence_count": "근거 문장 번호는 줄마다 1~3개로 하세요.",
    "format:finite_verb": "줄 끝을 '~함', '~임', '~됨' 같은 명사형으로 맺으세요.",
    "format:period_end": "줄 끝에 마침표를 붙이지 마세요.",
    "grounding:number": "숫자·연도·단위가 인용한 문장에 그대로 있어야 합니다. 원문에 없는 연도(올해를 연도로 바꾼 것 포함)와 숫자는 빼세요.",
    "grounding:latin": "영어 단어는 인용한 문장이나 제목에 있는 것만 쓰세요.",
    "grounding:proper": "이름·고유명사는 인용한 문장이나 제목에 있는 것만 쓰세요.",
    "grounding:quote": "따옴표 안 말은 인용한 문장에 있는 그대로만 쓰세요.",
    "grounding:nouns": "인용한 문장에 없는 내용이 섞였습니다. 인용한 문장의 낱말로 다시 쓰세요.",
    "grounding:negation": "원문에 없는 부정 표현을 넣지 마세요.",
    "grounding:negation_dropped": "원문의 취소·중단·불가 같은 표현을 빠뜨리지 마세요.",
    "grounding:direction": "증가·감소, 상승·하락 같은 방향이 원문과 반대입니다. 원문 그대로의 방향으로 쓰세요.",
    "invalid_output": "지정한 JSON 형식(lines 배열에 text와 evidence)을 정확히 지키세요.",
}


def _repair_prompt(prompt: str, code: str, line_index: int | None) -> str:
    hint = _REPAIR_HINTS.get(code, "원문 문장에 있는 내용만 쓰세요.")
    where = f" (문제가 된 줄: {line_index + 1}번째)" if line_index is not None else ""
    return f"{prompt}\n\n[이전 답변이 검사에서 탈락했습니다{where}] {hint}"


def build_card(
    *,
    title: str,
    body: str,
    topic_label: str,
    score: ScoreResult,
    now: datetime,
    clients: Sequence[CardClient],
    noun_extractor: NounExtractor | None = None,
    clock: Callable[[], float] = time.monotonic,
    budget_seconds: float = 120.0,
) -> CardResult:
    start_time = clock()

    sentences = split_sentences(body)
    reason = build_reason(score=score, topic_label=topic_label, title=title, body=body, now=now)
    if not reason_is_grounded(reason, body, title):
        return CardResult(status="rejected", card=None, code="reason_ungrounded")
    if len(sentences) < 3:
        # 핵심 3줄을 뽑을 문장이 모자란다: 글을 버리지 않고, 검증된 요약을 그대로 보여 주는 카드로 둔다.
        return CardResult(status="unavailable", card=None, code="too_few_sentences", reason=reason)

    if not clients:
        return CardResult(status="unavailable", card=None, code="no_client", reason=reason)

    base_prompt = build_prompt(title=title, sentences=sentences, topic_label=topic_label)

    rejected_code: str | None = None  # 모델이 답했지만 형식·대조를 통과하지 못한 첫 사유
    last_code: str = "provider_error"

    for client in clients:
        prompt = base_prompt
        for _attempt in range(2):  # 처음 한 번 + 탈락 사유를 알려 준 고쳐 쓰기 한 번
            if clock() - start_time >= budget_seconds:
                return CardResult(status="unavailable", card=None, code="budget_exhausted", reason=reason)
            try:
                response = client.structured_json(
                    prompt=prompt,
                    schema=CARD_SCHEMA,
                    schema_name="insight_desk_card_lines",
                )
            except Exception:
                last_code = "provider_error"
                break  # 이 클라이언트는 포기하고 다음으로

            if not _validate_response(response):
                last_code = "invalid_output"
                prompt = _repair_prompt(base_prompt, last_code, None)
                continue

            card_lines = [
                CardLine(text=item["text"], evidence=tuple(sorted(set(item["evidence"]))))
                for item in response["lines"]
            ]
            result = check_format(card_lines, len(sentences))
            if result.ok:
                result = check_grounding(card_lines, sentences, noun_extractor=noun_extractor, context=title)
            if not result.ok:
                last_code = result.code
                rejected_code = rejected_code or result.code
                prompt = _repair_prompt(base_prompt, result.code, result.line_index)
                continue

            card = Card(
                reason=reason,
                lines=(card_lines[0].text, card_lines[1].text, card_lines[2].text),
                evidence=(card_lines[0].evidence, card_lines[1].evidence, card_lines[2].evidence),
            )
            return CardResult(status="ok", card=card, code="ok", weak=result.weak, reason=reason)

    if rejected_code is not None:
        return CardResult(status="rejected", card=None, code=rejected_code, reason=reason)

    return CardResult(status="unavailable", card=None, code=last_code, reason=reason)


def _validate_response(response: Any) -> bool:
    if not isinstance(response, dict):
        return False
    if "lines" not in response:
        return False
    lines = response["lines"]
    if not isinstance(lines, list):
        return False
    if len(lines) != 3:
        return False
    for item in lines:
        if not isinstance(item, dict):
            return False
        if "text" not in item or "evidence" not in item:
            return False
        if not isinstance(item["text"], str):
            return False
        if not isinstance(item["evidence"], list):
            return False
        for e in item["evidence"]:
            if not isinstance(e, int):
                return False
    return True
