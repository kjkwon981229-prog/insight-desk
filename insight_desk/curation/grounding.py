from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Sequence

from .text import content_words, normalize

NounExtractor = Callable[[str], frozenset[str]]

MAX_LINE_CHARS = 70
MAX_EVIDENCE = 4
NOUN_COVERAGE = 0.5
# 같은 뜻의 영어 약어와 한국어 낱말: 한쪽이 원문에 있으면 다른 쪽을 쓴 줄도 통과한다.
_LATIN_ALIASES: dict[str, tuple[str, ...]] = {
    "ai": ("인공지능",),
    "gpu": ("그래픽처리장치",),
    "kbo": ("한국야구위원회", "프로야구"),
    "kospi": ("코스피",),
    "psat": ("공직적격성평가",),
}

_DEFAULT_EXTRACTORS: tuple[NounExtractor, NounExtractor] | None = None

# 요약 문체에서 모델이 동사를 명사로 바꿀 때 자주 새로 생기는 낱말. 원문에 없어도 사실 추가가 아니므로
# 내용어 일치율 계산에서 뺀다. (수치·고유명사·영문·인용은 아래 별도 검사가 엄격하게 본다.)
_GENERIC_NOMINALS = frozenset(
    "확대 증가 감소 예정 전망 발표 계획 추진 상승 하락 강화 개선 확정 출시 공개 시행 진행 기록 달성 돌파 제공 도입 "
    "개최 참여 실시 결정 합의 변경 지속 유지 급증 급감 둔화 확산 해소 마련 부각 주목 논의 요구 지적 평가 분석 영향 기대 우려".split()
)


@dataclass(frozen=True, slots=True)
class CardLine:
    text: str
    evidence: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class GroundingResult:
    ok: bool
    code: str
    line_index: int | None = None
    weak: bool = False


def default_extractors() -> tuple[NounExtractor, NounExtractor]:
    """(명사 추출기, 고유명사 추출기). kiwipiepy 가 없으면 고유명사 검사는 빈 집합을 돌려준다."""
    global _DEFAULT_EXTRACTORS
    if _DEFAULT_EXTRACTORS is not None:
        return _DEFAULT_EXTRACTORS
    try:
        from kiwipiepy import Kiwi

        kiwi = Kiwi()

        def _tokens(text: str):
            return kiwi.analyze(text)[0][0]

        def nouns(text: str) -> frozenset[str]:
            return frozenset(t.form for t in _tokens(text) if t.tag in ("NNG", "NNP", "SL", "SN"))

        def proper(text: str) -> frozenset[str]:
            return frozenset(t.form for t in _tokens(text) if t.tag == "NNP")

        _DEFAULT_EXTRACTORS = (nouns, proper)
    except Exception:  # kiwipiepy 미설치 또는 모델 오류: 형태소 없이 낱말 단위로 폴백
        _DEFAULT_EXTRACTORS = (content_words, lambda _text: frozenset())
    return _DEFAULT_EXTRACTORS


def default_noun_extractor() -> NounExtractor:
    return default_extractors()[0]


_FINITE_SUFFIXES = ("습니다", "입니다", "했다", "한다", "이다")
_FINITE_CHARS = ("다", "요", "까", "죠", "?")

_UNIT_LIST = [
    "퍼센트", "달러", "원화", "억원", "만원", "조원", "천원",
    "%", "$", "원", "억", "만", "천", "조",
    "명", "건", "개", "위", "승", "패", "점",
    "회", "배", "홈런", "타점", "이닝",
    "세", "년", "월", "일", "시", "분", "초",
    "km", "kg",
]
_UNIT_PATTERN = re.compile(
    # 3분기·3개월·15일정 처럼 단위가 더 큰 낱말의 일부인 경우만 뒤 글자로 걸러낸다(조사는 허용).
    r"(\d+(?:\.\d+)?)\s{0,1}(" + "|".join(re.escape(u) for u in _UNIT_LIST) + r")(?![A-Za-z]|기|월|간|반|정)"
)
_NUMBER_ONLY = re.compile(r"\d+(?:\.\d+)?")
_LATIN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9.+&-]*")
_QUOTE_PATTERNS = [
    re.compile(r"'([^']+)'"),
    re.compile(r'"([^"]+)"'),
    re.compile("‘([^’]+)’"),
    re.compile("“([^”]+)”"),
    re.compile("「([^」]+)」"),
]
_NEG_MARKERS = ["않", "아니", "불가", "없", "무산", "취소", "부결", "중단", "철회"]
_STRONG_NEG = ("무산", "취소", "부결", "중단", "철회", "불가")
_WEAK_NEG = ("없다", "없었", "않았", "않는", "않을", "않다", "아니다", "아니라")
_UP_WORDS = ("증가", "상승", "확대", "늘", "급증", "인상", "성장", "개선", "호조", "흑자")
_DOWN_WORDS = ("감소", "하락", "축소", "줄", "급감", "인하", "둔화", "악화", "부진", "적자")


def _direction(text: str) -> tuple[bool, bool]:
    return any(w in text for w in _UP_WORDS), any(w in text for w in _DOWN_WORDS)


def _normalize_numbers(text: str) -> str:
    t = text.replace(",", "")
    t = t.replace("퍼센트", "%")
    t = t.replace("달러", "$")
    t = t.replace("원화", "원")
    t = re.sub(r"\$\s*(\d+(?:\.\d+)?)", r"\1$", t)  # $100 -> 100$ (달러와 같은 꼴로)
    t = re.sub(r"(?<=[억만조])\s+(?=원)", "", t)  # 500억 원 -> 500억원
    return t


def _num_unit_pairs(text: str) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2)) for m in _UNIT_PATTERN.finditer(_normalize_numbers(text))]


def _noun_supported(noun: str, support: str) -> bool:
    """명사가 그대로 있거나, 3글자 이상 복합명사의 앞·뒤 두 글자(계약금액↔계약했다)가 있으면 인정한다."""
    if noun in support:
        return True
    return len(noun) >= 3 and (noun[:2] in support or noun[-2:] in support)


def _has_hangul(text: str) -> bool:
    return any("가" <= c <= "힣" for c in text)


def check_format(lines: Sequence[CardLine], sentence_count: int) -> GroundingResult:
    if len(lines) != 3:
        return GroundingResult(ok=False, code="format:line_count")
    for idx, line in enumerate(lines):
        text = line.text.strip()
        if len(text) < 4 or len(text) > MAX_LINE_CHARS:
            return GroundingResult(ok=False, code="format:length", line_index=idx)
        if text.endswith("."):
            return GroundingResult(ok=False, code="format:period_end", line_index=idx)
        if text.endswith(_FINITE_SUFFIXES) or text.endswith(_FINITE_CHARS):
            return GroundingResult(ok=False, code="format:finite_verb", line_index=idx)
        evidence = line.evidence
        if not 1 <= len(evidence) <= MAX_EVIDENCE:
            return GroundingResult(ok=False, code="format:evidence_count", line_index=idx)
        if len(set(evidence)) != len(evidence):
            return GroundingResult(ok=False, code="format:evidence_dup", line_index=idx)
        if any(not isinstance(e, int) or isinstance(e, bool) or e < 0 or e >= sentence_count for e in evidence):
            return GroundingResult(ok=False, code="format:evidence_range", line_index=idx)
    return GroundingResult(ok=True, code="ok")


def check_grounding(
    lines: Sequence[CardLine],
    sentences: Sequence[str],
    *,
    noun_extractor: NounExtractor | None = None,
    proper_extractor: NounExtractor | None = None,
    context: str = "",
) -> GroundingResult:
    """줄마다 인용한 원문 문장과 대조한다. 첫 실패에서 멈춘다.

    `context`(기사 제목)는 이름·영문·명사 검사에서만 인용 문장과 함께 근거로 인정한다. 제목에 적힌
    주어는 본문 문장에서 대명사로 바뀌는 일이 흔하기 때문이다. 수치와 따옴표 인용은 인용 문장만 본다.
    """
    if noun_extractor is None:
        noun_extractor, default_proper = default_extractors()
        if proper_extractor is None:
            proper_extractor = default_proper

    weak = False
    for idx, line in enumerate(lines):
        cited_raw = " ".join(sentences[i] for i in line.evidence)
        cited_norm = normalize(_normalize_numbers(cited_raw))

        cited_pairs = set(_num_unit_pairs(cited_raw))
        cited_numbers = set(_NUMBER_ONLY.findall(_normalize_numbers(cited_raw)))
        for number, unit in _num_unit_pairs(line.text):
            if (number, unit) not in cited_pairs:
                return GroundingResult(False, "grounding:number", idx, weak)
        # 단위 없이 쓴 숫자도 원문에 있어야 한다.
        line_numbers = set(_NUMBER_ONLY.findall(_normalize_numbers(line.text)))
        if not line_numbers <= cited_numbers:
            return GroundingResult(False, "grounding:number", idx, weak)

        support_raw = f"{cited_raw} {context}"
        support_norm = normalize(_normalize_numbers(support_raw))
        support_lower = support_raw.lower()
        for match in _LATIN_PATTERN.finditer(line.text):
            token = match.group(0)
            if len(token) < 2:
                continue
            lowered = token.lower()
            if lowered in support_lower:
                continue
            if any(alias in support_raw for alias in _LATIN_ALIASES.get(lowered.strip(".+&-"), ())):
                continue
            return GroundingResult(False, "grounding:latin", idx, weak)

        for pattern in _QUOTE_PATTERNS:
            for match in pattern.finditer(line.text):
                if match.group(1) not in cited_raw:
                    return GroundingResult(False, "grounding:quote", idx, weak)

        hangul = sum(1 for c in cited_norm if "가" <= c <= "힣")
        if hangul / max(len(cited_norm), 1) >= 0.2:
            if proper_extractor is not None:
                for name in proper_extractor(line.text):
                    if len(name) >= 2 and normalize(name) not in support_norm:
                        return GroundingResult(False, "grounding:proper", idx, weak)
            nouns = [
                n
                for n in noun_extractor(line.text)
                if len(n) >= 2 and _has_hangul(n) and n not in _GENERIC_NOMINALS
            ]
            if nouns:
                matched = sum(1 for n in nouns if _noun_supported(normalize(n), support_norm))
                if matched / len(nouns) < NOUN_COVERAGE:
                    return GroundingResult(False, "grounding:nouns", idx, weak)
        else:
            weak = True

        line_negates = any(marker in line.text for marker in _NEG_MARKERS)
        if line_negates and not any(marker in cited_raw for marker in _NEG_MARKERS):
            return GroundingResult(False, "grounding:negation", idx, weak)
        if any(m in cited_raw for m in _STRONG_NEG + _WEAK_NEG) and not line_negates:
            return GroundingResult(False, "grounding:negation_dropped", idx, weak)
        line_up, line_down = _direction(line.text)
        cited_up, cited_down = _direction(cited_raw)
        if (line_up and not line_down and cited_down and not cited_up) or (
            line_down and not line_up and cited_up and not cited_down
        ):
            return GroundingResult(False, "grounding:direction", idx, weak)

    return GroundingResult(True, "ok", None, weak)
