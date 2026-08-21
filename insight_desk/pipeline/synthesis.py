from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from difflib import SequenceMatcher

from ..domain.models import Certainty, EvidenceType, NewsItem, StoryFacts, TrendMetric
from .clustering import StoryCluster
from .editorial import (
    best_headline_item,
    effective_lead,
    effective_title,
    event_owned_items,
    event_owned_lead,
    evidence_corroborated,
    safe_evidence_text,
)
from .normalization import normalize_text
from .semantics import (
    ACTION_TERMS,
    CanonicalEvent,
    EventFact,
    MetricObservation,
    canonical_event_date,
    canonical_event_signature,
    canonical_publisher,
    contains_action,
    contains_boundary_term,
    earnings_fact_parts,
    earnings_observations,
    event_action_signal,
    event_dates,
    first_action,
    industry_change_facts,
    is_trusted_official_domain,
    market_direction,
    metric_observations,
    primary_event_focus_terms,
    recruitment_event_type,
    sports_result_facts,
    summary_information_gain,
    summary_preserves_primary_focus,
)
from .trend_metrics import effective_trend_state

_NUMBER_RE = re.compile(
    r"(?<![A-Za-z가-힣])\d[\d,.]*(?:\s?(?:조원|억원|만원|천만|만\s?달러|억\s?달러|달러|개월|주년|분기|원|%|퍼센트|명|건|배|개|종|곳|일|월|년|분|시|위|점|대|선|km))?"
)
_DATE_RE = re.compile(r"(?:20\d{2}\s?년\s?)?\d{1,2}\s?(?:월\s?\d{1,2}\s?일|일)")
_TIME_RE = re.compile(r"(?:오전|오후)\s?\d{1,2}(?::\d{2})?|\d{1,2}\s?시(?:\s?\d{1,2}\s?분)?")
_CHANGE_MARKERS = (
    "최고",
    "최대",
    "최저",
    "최소",
    "증가",
    "감소",
    "상승",
    "하락",
    "확대",
    "축소",
    "돌파",
    "기록",
    "사상",
    "역대",
    "급등",
    "급락",
    "강세",
    "약세",
    "강보합세",
)
_ACTION_MARKERS = (
    "요구",
    "촉구",
    "줄여라",
    "시구",
    "개최",
    "공연",
    "콘서트",
    "출시",
    "발매",
    "발표",
    "공개",
    "시행",
    "선발",
    "중단",
    "멈춘",
    "재개",
    "취소",
    "경기",
    "매각",
    "인수",
    "인상",
    "인하",
    "규제",
    "유치",
    "투자",
    "인수",
    "트레이드",
    "부상",
    "승리",
    "패배",
    "컴백",
    "전략",
    "할당",
    "계약",
)
_LOCATION_TERMS = (
    "잠실",
    "서울",
    "부산",
    "광주",
    "대전",
    "인천",
    "제주",
    "판교",
    "여의도",
    "뉴욕",
    "도쿄",
    "싱가포르",
    "충칭",
    "DDP",
)
_KBO_TEAM_RE = re.compile(
    r"(?<![A-Za-z가-힣])(?:한화(?:\s*이글스)?|두산(?:\s*베어스)?|LG(?:\s*트윈스)?|"
    r"KT(?:\s*위즈)?|SSG(?:\s*랜더스)?|KIA(?:\s*타이거즈)?|NC(?:\s*다이노스)?|"
    r"롯데(?:\s*자이언츠)?|삼성(?:\s*라이온즈)?|키움(?:\s*히어로즈)?)"
    r"(?=(?:와|과|의|은|는|이|가|을|를)?(?:\s|$|[,，.:：;；]))",
    re.IGNORECASE,
)
_LINEUP_LABEL_RE = re.compile(r"^(?:선발(?:투수)?|투수|예고|라인업)\s*", re.IGNORECASE)
_PLAYER_TOKEN_RE = re.compile(r"[A-Za-z가-힣][A-Za-z가-힣·.'’-]{1,11}")
_LINEUP_PREFIX_PARTICLE_RE = re.compile(r"^(?:와|과|의|은|는|이|가|을|를)(?:\s+|$)")
_GRAMMATICAL_PARTICLE_TOKENS = frozenset({"와", "과", "의", "은", "는", "이", "가", "을", "를"})
_STOPWORDS = {
    "관련",
    "보도",
    "추가",
    "내용",
    "결과",
    "발표",
    "공개",
    "확인",
    "전해져",
    "전해졌다",
    "밝혀져",
    "올해",
    "지난해",
    "이번",
    "내년",
    "따르면",
    "대해",
    "위해",
    "에서",
    "으로",
    "있는",
    "있다",
    "같은",
    "및",
    "또",
}
_GENERIC_CHANGE_WORDS = {"기록", "발표", "공개", "확인"}
_EVENT_ACTIONS = {"시구", "개최", "공연", "콘서트", "선발", "경기", "컴백"}
_SUBJECT_END_MARKERS = ("회동", "시구", "경기", "공연", "콘서트", "출시", "공지")
_DIRECTIONAL_CHANGE_WORDS = {"증가", "감소", "상승", "하락", "확대", "축소", "돌파", "급등", "급락", "강세", "약세", "강보합세"}
_TRUNCATION_RE = re.compile(r"\.{2,}|…|·{2,}")
_AWARD_TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣]+(?:[·&'’-][A-Za-z0-9가-힣]+)*")
_AWARD_GENERIC_TOKENS = frozenset(
    {
        "국내외",
        "음악",
        "음원",
        "가요",
        "아이돌",
        "가수",
        "차트",
        "평점",
        "랭킹",
        "연속",
        "no",
        "위",
        "주",
        "월",
        "일",
    }
)
_AWARD_SUPPORT_MARKERS = ("컴백", "신곡", "앨범", "데뷔곡", "데뷔")
_TIME_PREFIX_RE = re.compile(r"^(?:한|두|세|몇|\d+)\s?(?:달|주|일|시간)\s?만에\b")
_DATE_COUNTER_RE = re.compile(r"^(?:20\d{2}\s?년|\d{1,2}\s?(?:월|일|주년))$")
_DATE_STAMP_RE = re.compile(r"^20\d{2}[./-]\d{1,2}[./-]\d{1,2}$")
_TIME_COUNTER_RE = re.compile(r"^\d{1,2}\s?(?:시|분)$")
_MARKET_RUN_RE = re.compile(r"\d+\s?거래일(?:\s?연속)?\s?(?:순매수|순매도)")
_GENERIC_HEADLINE_MARKERS = ("관련 보도", "관련 소식", "관련 기사", "관련 뉴스")
_GENERIC_SUMMARY_MARKERS = (
    "단일 검색 결과만 확인되어",
    "공통으로 확인되는 세부 사실은 제한적이다",
    "소식이 보도됐다",
    "변화가 보도됐다",
    "발표가 확인됐다",
    "공개 내용이 확인됐다",
    "관련 내용이 확인됐다",
    "여러 매체에서 같은 핵심 내용이 확인됐다",
    "여러 보도에서 같은 핵심 내용이 확인됐다",
    "공식 자료를 인용한 보도가 확인됐다",
)
_EVENT_DATE_MARKERS = (
    "발매", "출시", "컴백", "공개", "발표", "개최", "공연", "콘서트", "진행", "시작", "재개",
    "예정", "상장", "시구", "경기", "열렸다", "성료",
)
_COMPLETION_MARKERS = ("대성황", "성황", "성료", "진행했다", "진행됐다", "개최했다", "열렸다", "마쳤다")
_DISPLAY_BRACKETS = (("(", ")"), ("[", "]"), ("{", "}"))
_BARE_NUMERIC_END_RE = re.compile(r"(?:^|\s)\d[\d,]*$")
_DANGLING_END_RE = re.compile(
    r"(?:^|\s)(?:및|또는|그리고|하지만|때문에|위해|대상|대상은)$"
)
_MALFORMED_SUBJECT_BOUNDARY_RE = re.compile(
    r"대상\s*(?:은|는|이|가)?\s+(?:시행|도입|적용|발표|공개|시작)"
)
_MALFORMED_PARTICLE_STACK_RE = re.compile(
    r"(?:와과|과와|의가|을를|를을|은는|는은)(?=$|[\s,.!?。！？])|"
    r"[A-Za-z가-힣·]{2,}가가(?=$|[\s,.!?。！？])"
)


_SUMMARY_TRANSLATIONESE_RE = re.compile(
    r"(?:결정을\s*내렸|영향을\s*미쳤|(?:발표|진행|검토)를\s*했)"
)
_SUMMARY_ABSTRACT_SENTENCE_RE = re.compile(
    r"(?:^|(?<=[.!?。！？])\s+)(?:논란이\s*커졌다|우려가\s*제기됐다|성과를\s*냈다)(?=$|[.!?。！？])"
)
_SUMMARY_REDUNDANT_CONCLUSION_RE = re.compile(
    r"(?:^|(?<=[.!?。！？])\s+)(?:종합하면|요약하면|결론적으로)\b"
)
_SUMMARY_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。！？])\s+")
_SUMMARY_LEADING_SUBJECT_RE = re.compile(
    r"^\s*([A-Za-z0-9가-힣·&.'’-]{2,30})(?:은|는|이|가)(?=\s)"
)


def summary_style_issues(value: str) -> tuple[str, ...]:
    """Return deterministic violations of the Korean news-summary SSOT.

    This deliberately enforces only the subset that can be judged without
    guessing: obvious translationese nominalization, unattributed abstract
    evaluation as a whole sentence, forced concluding prose, and immediate
    repetition of the same explicit subject across adjacent sentences.
    """

    text = normalize_text(value)
    if not text:
        return ("EMPTY",)
    issues: list[str] = []
    if _SUMMARY_TRANSLATIONESE_RE.search(text):
        issues.append("TRANSLATIONESE")
    if _SUMMARY_ABSTRACT_SENTENCE_RE.search(text):
        issues.append("ABSTRACT_EVALUATION")
    if _SUMMARY_REDUNDANT_CONCLUSION_RE.search(text):
        issues.append("REDUNDANT_CONCLUSION")

    previous_subject = ""
    for sentence in _SUMMARY_SENTENCE_SPLIT_RE.split(text):
        match = _SUMMARY_LEADING_SUBJECT_RE.match(sentence)
        subject = normalize_text(match.group(1)) if match else ""
        if subject and previous_subject and subject == previous_subject:
            issues.append("REPEATED_SUBJECT")
            break
        previous_subject = subject
    return tuple(dict.fromkeys(issues))


def editorial_text_issues(value: str) -> tuple[str, ...]:
    """Return deterministic user-facing copy defects.

    This is intentionally a small output contract, not a Korean NLP parser.
    It is shared by synthesis eligibility and live acceptance so a fragment
    that cannot be displayed cannot pass only because the validator uses a
    different interpretation of the text.
    """

    text = normalize_text(value)
    if not text:
        return ("EMPTY",)
    issues: list[str] = []
    if _TRUNCATION_RE.search(text):
        issues.append("TRUNCATED")
    if text.count('"') % 2:
        issues.append("UNMATCHED_QUOTE")
    if text.count("'") % 2 and not re.search(r"[A-Za-z0-9]'[A-Za-z0-9]", text):
        issues.append("UNMATCHED_QUOTE")
    if text.count("“") != text.count("”") or text.count("‘") != text.count("’"):
        issues.append("UNMATCHED_QUOTE")
    for opening, closing in _DISPLAY_BRACKETS:
        if text.count(opening) != text.count(closing):
            issues.append("UNMATCHED_BRACKET")
    sentence_end = text.rstrip(" .!?。！？")
    if _BARE_NUMERIC_END_RE.search(sentence_end):
        issues.append("BARE_NUMERIC_END")
    if _DANGLING_END_RE.search(sentence_end):
        issues.append("DANGLING_CLAUSE")
    if _MALFORMED_SUBJECT_BOUNDARY_RE.search(text):
        issues.append("MALFORMED_SUBJECT_BOUNDARY")
    if _MALFORMED_PARTICLE_STACK_RE.search(text):
        issues.append("MALFORMED_PARTICLE_STACK")
    return tuple(dict.fromkeys(issues))


def _normalise_display_sentence(value: str) -> str:
    """Remove only unmatched decorative punctuation from display copy."""

    text = normalize_text(value)
    issues = editorial_text_issues(text)
    if "UNMATCHED_QUOTE" in issues:
        text = re.sub(r"[\"'“”‘’]", "", text)
    return text


def _earnings_fact_parts(text: str) -> tuple[str, str, str]:
    """Keep synthesis on the same fact-bound earnings parser as the event model."""

    return earnings_fact_parts(_clean_headline(text))


def earnings_summary_preserves_fact_binding(headline: str, summary: str) -> bool:
    """Require an earnings display to retain period/metric/value together."""

    period, metric, value = _earnings_fact_parts(headline)
    if not metric or not value:
        return False
    compact_summary = normalize_text(summary).replace(" ", "")
    if metric not in compact_summary or value not in compact_summary:
        return False
    if period and period not in compact_summary:
        return False
    return True


def is_usable_synthesis(
    headline: str,
    summary: str,
    *,
    source_count: int,
    official_source: bool = False,
    relation_fact: EventFact | None = None,
    relation_fact_preserved: bool = False,
) -> bool:
    """Reject display copy that cannot carry a concrete editorial fact."""

    clean_headline = normalize_text(headline)
    clean_summary = normalize_text(summary)
    if not clean_headline or any(marker in clean_headline for marker in _GENERIC_HEADLINE_MARKERS):
        return False
    if not clean_summary or any(
        clean_summary == marker or clean_summary.startswith(marker)
        for marker in _GENERIC_SUMMARY_MARKERS
    ):
        return False
    if relation_fact is not None:
        relation_fact_preserved = relation_summary_preserves_fact(
            clean_summary,
            clean_headline,
            relation_fact,
        )
        if not relation_fact_preserved:
            return False
    if not summary_information_gain(clean_headline, clean_summary) and not relation_fact_preserved:
        return False
    if _TRUNCATION_RE.search(clean_headline):
        return False
    if editorial_text_issues(clean_summary):
        return False
    if summary_style_issues(clean_summary):
        return False
    if clean_summary.endswith("일정이 공개됐다.") and not _DATE_RE.search(clean_summary):
        return False
    if source_count <= 1 and not official_source and "추가 확인이 필요하다" in clean_summary:
        return False
    return True


def _clean_headline(value: str) -> str:
    text = normalize_text(value)
    text = re.sub(r"^\s*(?:\[[^]]+\]|속보|단독|전문)\s*[:：]?\s*", "", text)
    text = text.replace("원달러", "원·달러")
    # A search title containing an ellipsis may be truncated. Keep the
    # complete clause before the marker; never expose the marker or its
    # possibly incomplete tail as briefing copy.
    marker = _TRUNCATION_RE.search(text)
    if marker:
        text = text[: marker.start()]
    text = re.sub(r"[\"'“”‘’]", "", text)
    text = re.sub(r"\s*[?!]+\s*", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .·-—")
    text = re.sub(r"^[^0-9A-Za-z가-힣]+", "", text)
    return text


def _editorial_headline(value: str, *, subject: str = "") -> str:
    """Reduce a source headline to a complete, non-truncated display phrase."""

    raw = normalize_text(value)
    cleaned = _clean_headline(raw)
    if _TRUNCATION_RE.search(raw):
        clauses = [part.strip(" ,·-—") for part in re.split(r"[,，|｜:：]", cleaned) if part.strip()]
        first = clauses[0] if clauses else ""
        if len(first) >= 5:
            return first
        if subject.strip():
            return f"{subject.strip()} 관련 보도"
    if len(cleaned) <= 56:
        return cleaned
    clauses = [part.strip(" ,·-—") for part in re.split(r"[,，|｜:：]", cleaned) if part.strip()]
    for clause in clauses:
        if 8 <= len(clause) <= 56:
            return clause
    return cleaned


def _safe_evidence_text(value: str) -> str:
    """Return a snippet only when it is a complete, non-truncated fragment."""

    text = normalize_text(value)
    return "" if _TRUNCATION_RE.search(text) else text


def _fact_evidence_text(value: str) -> str:
    """Keep a concrete lead prefix when only its trailing clause is cut off.

    Search snippets frequently end with an ellipsis after a complete first
    sentence.  That prefix can support a date or action, while the truncated
    tail must remain unusable.  A snippet that starts with an ellipsis has no
    safe prefix and is rejected.
    """

    text = normalize_text(value)
    marker = _TRUNCATION_RE.search(text)
    if not marker:
        return text
    prefix = text[: marker.start()].strip(" ,·-—")
    if len(prefix) < 12:
        return ""
    # A prefix is safe only when it ends at a sentence boundary. Otherwise
    # the apparent lead can end halfway through a word (for example
    # ``방..``) and become a fabricated fact in the final summary.
    boundaries = list(re.finditer(r"[.!?。！？]", prefix))
    if boundaries:
        return prefix[: boundaries[-1].end()].strip(" ,·-—")
    # Korean leads often omit a final period. Accept only common predicate
    # endings, not an arbitrary partial noun or word.
    if re.search(r"(?:다|요|음|함|됨|임|연다|열린다|된다|했다|한다|있다|없다)$", prefix):
        return prefix
    # Structured lineup fragments are a narrow positive control: explicit
    # team/player pairs are independently parseable even when the source
    # truncates after the last pair. Do not generalize this to free-form prose.
    if len(_lineup_detail(prefix)) >= 2:
        return prefix
    return ""


def _fact_lead(item: object) -> str:
    for authority in getattr(item, "authoritative_evidence", ()):
        for value in (getattr(authority, "description", ""), getattr(authority, "title", "")):
            lead = _fact_evidence_text(value)
            if lead:
                return lead
    for value in (getattr(item, "metadata_description", ""), getattr(item, "summary", "")):
        lead = _fact_evidence_text(value)
        if lead:
            return lead
    return ""


def _best_event_completion_evidence(
    items: tuple[NewsItem, ...],
    canonical_event: CanonicalEvent | None,
    title: str,
    focus_terms: tuple[str, ...],
) -> str:
    """Choose a same-event, same-focus fact lead from all owned sources.

    A canonical event may have several legitimate owners. Restricting
    synthesis to the representative lead can discard a fact supplied by a
    corroborating owner; accepting every paragraph from one owner can switch
    to a secondary event. This bounded chooser closes both failure modes.
    """

    candidates: list[str] = []
    if canonical_event is not None and canonical_event.evidence_detail:
        candidates.append(canonical_event.evidence_detail)
    for item in items:
        raw = (
            event_owned_lead(item, canonical_event.event_type)
            if canonical_event is not None
            else _fact_lead(item)
        )
        if raw:
            candidates.append(raw)
    scored: list[tuple[tuple[int, int, int], str]] = []
    for order, raw in enumerate(dict.fromkeys(candidates)):
        detail = _fact_evidence_text(raw)
        if not detail or editorial_text_issues(detail):
            continue
        if not summary_information_gain(title, detail):
            continue
        if not summary_preserves_primary_focus(detail, focus_terms):
            continue
        material = int(bool(_NUMBER_RE.search(detail))) + int(
            bool(event_action_signal(canonical_event.event_type, title, detail))
            if canonical_event is not None
            else bool(_action(detail))
        )
        scored.append(((material, min(len(detail), 240), -order), detail))
    return max(scored, default=((0, 0, 0), ""))[1]


def _lineup_detail(evidence: str) -> tuple[str, ...]:
    """Extract only explicit team/player pairs from a complete lineup lead."""

    matches = list(_KBO_TEAM_RE.finditer(evidence))
    pairs: list[str] = []
    for index, team_match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(evidence)
        fragment = evidence[team_match.end() : end]
        fragment = fragment.lstrip(" \t:：·,/()[]{}-")
        fragment = _LINEUP_PREFIX_PARTICLE_RE.sub("", fragment)
        fragment = _LINEUP_LABEL_RE.sub("", fragment)
        player_match = _PLAYER_TOKEN_RE.match(fragment)
        if not player_match:
            continue
        player = player_match.group(0).strip("·-—")
        if not player or player in {
            "경기",
            "예고",
            "선발",
            "투수",
            "라인업",
            *_GRAMMATICAL_PARTICLE_TOKENS,
        }:
            continue
        team = re.sub(r"\s+", " ", team_match.group(0)).strip()
        pair = f"{team} {player}"
        if pair not in pairs:
            pairs.append(pair)
    return tuple(pairs[:4])


def _unique(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _numbers(text: str) -> tuple[str, ...]:
    values = []
    for match in _NUMBER_RE.findall(text):
        value = re.sub(r"\s+", "", match)
        if value not in values:
            values.append(value)
    return tuple(values)


def _meaningful_numbers(values: tuple[str, ...], context: str = "") -> tuple[str, ...]:
    """Discard bare counters accidentally captured from Korean headlines."""

    if any(marker in context.casefold() for marker in ("ndf", "선물환")) and "/" in context:
        return values
    meaningful = tuple(
        value
        for value in values
        if not _DATE_COUNTER_RE.fullmatch(value)
        and not _DATE_STAMP_RE.fullmatch(value)
        and re.search(r"[^\d,.\s]", value)
    )
    if meaningful:
        return meaningful
    if values and all(_DATE_COUNTER_RE.fullmatch(value) or _DATE_STAMP_RE.fullmatch(value) for value in values):
        return ()
    return values


def _market_run_phrase(title: str) -> str:
    match = _MARKET_RUN_RE.search(_clean_headline(title))
    return match.group(0) if match else ""


def _market_quote_detail(title: str, numbers: tuple[str, ...], change: str) -> str:
    """Preserve an NDF quote pair and its movement without adding context."""

    cleaned = _clean_headline(title)
    if not any(marker in cleaned.casefold() for marker in ("ndf", "선물환")) or len(numbers) < 2:
        return ""
    direction = next((marker for marker in _DIRECTIONAL_CHANGE_WORDS if marker in cleaned), "")
    if not direction:
        return ""
    values = [re.sub(r"\s+", "", value).removesuffix("원") for value in numbers[:3]]
    if len(values) >= 3:
        return f"{values[0]}/{values[1]}원, {values[2]}원 {direction}"
    return f"{values[0]}/{values[1]}원 {direction}"


def _market_metric_number(title: str, numbers: tuple[str, ...]) -> str:
    """Return a number only when the headline ties it to the metric.

    A level such as ``1300원대 환율`` must not be rendered as the size of a
    later-mentioned ``변동폭``.  If a variability marker is present, only a
    number immediately following that marker is safe to reuse.
    """

    if not numbers:
        return ""
    cleaned = _clean_headline(title)
    marker = re.search(r"변동폭|변동성", cleaned)
    if marker:
        nearby = _NUMBER_RE.search(cleaned[marker.end() : marker.end() + 32])
        return nearby.group(0).replace(" ", "") if nearby else ""
    return numbers[0]


def _dates(text: str) -> tuple[str, ...]:
    return _unique([re.sub(r"\s+", "", value) for value in _DATE_RE.findall(text)])


def _event_dates(text: str) -> tuple[str, ...]:
    """Extract dates tied to the event, not a publication-date preface."""

    return event_dates(text)


def _times(text: str) -> tuple[str, ...]:
    return _unique([re.sub(r"\s+", "", value) for value in _TIME_RE.findall(text)])


def _locations(text: str) -> tuple[str, ...]:
    return _unique([value for value in _LOCATION_TERMS if value.casefold() in text.casefold()])


def _repeated_values(
    items: tuple[object, ...], extractor: Callable[[str], tuple[str, ...]]
) -> tuple[str, ...]:
    counts: Counter[str] = Counter()
    for item in items:
        # Search descriptions may contain an unrelated trailing clause.  Only
        # repeat facts that appear in the effective headline evidence.
        values = extractor(effective_title(item))
        counts.update(set(values))
    return tuple(value for value, count in counts.most_common() if count >= 2)


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[A-Za-z0-9가-힣·]{2,}", text)
        if token not in _STOPWORDS and not token.isdigit()
    }


def _repeated_terms(items: tuple[object, ...]) -> tuple[str, ...]:
    counts: Counter[str] = Counter()
    for item in items:
        counts.update(_tokens(_clean_headline(getattr(item, "title", ""))))
    return tuple(token for token, count in counts.most_common() if count >= 2)[:3]


def _event_type(text: str, numbers: tuple[str, ...]) -> str:
    recruitment = recruitment_event_type(text)
    if recruitment:
        return recruitment
    if any(word in text for word in ("실적", "매출", "영업이익", "순이익", "가이던스")):
        return "EARNINGS"
    if any(word in text for word in ("1위", "차트", "관왕", "수상")):
        return "AWARD_CHART"
    if any(word in text for word in ("규제", "법안", "고시", "금지", "허용")):
        return "REGULATION"
    if any(
        word in text
        for word in (
            "정책 발표",
            "정책 결정",
            "정책 시행",
            "정책 개편",
            "대책 발표",
            "대책 시행",
            "규정",
            "기준금리",
            "요구",
            "촉구",
            "줄여라",
        )
    ):
        return "POLICY"
    if any(word in text for word in ("출시", "발매", "선공개", "음원", "신곡", "싱글", "데뷔곡", "신규상장", "상장", "예약판매", "판매 개시", "사양 확정")):
        return "PRODUCT_RELEASE"
    sports_context = any(word in text for word in ("야구", "KBO", "프로야구", "구단", "선수", "홈런", "경기", "시구"))
    if (
        sports_context
        and any(word in text for word in ("폭염", "열파"))
        and any(word in text for word in ("중단", "멈춘", "휴식", "재개", "취소"))
    ):
        return "SPORTS_INTERRUPTION"
    if any(contains_action(text, word) for word in ("부상", "트레이드", "엔트리", "선발")):
        return "ROSTER_PERSONNEL"
    if sports_context and _DATE_RE.search(text) and any(word in text for word in ("시구", "개최", "예정")):
        return "SPORTS_EVENT"
    if any(word in text for word in ("야구", "KBO", "프로야구", "구단", "선수", "홈런", "경기 결과")) and any(word in text for word in ("중단", "멈춘", "폭염")):
        return "SPORTS_INTERRUPTION"
    if any(word in text for word in ("야구", "KBO", "프로야구", "구단", "선수", "홈런", "경기 결과")) and any(word in text for word in ("경기 결과", "승리했다", "패배했다", "우승", "승률", "연승", "연패", "홈런", "순위")):
        return "SPORTS_RESULT"
    if any(word in text for word in ("콘서트", "공연", "앨범", "컴백", "배우", "가수", "시구")):
        return "ENTERTAINMENT_EVENT"
    if any(word in text for word in ("환율", "원달러", "원·달러", "코스피", "주가", "증시", "금리")):
        return "MARKET"
    if numbers and any(word in text for word in (*_CHANGE_MARKERS, "평균", "통계", "지표", "비율", "변동폭")):
        return "STATISTIC"
    if any(
        contains_action(text, word)
        for word in ("유치", "투자", "인수", "전략", "데이터센터", "할당", "계약", "생산")
    ):
        return "INDUSTRY_CHANGE"
    if _DATE_RE.search(text) and any(word in text for word in (*_ACTION_MARKERS, "예정", "진행", "프로젝트", "선보인다")):
        return "SCHEDULED_EVENT"
    if any(word in text for word in ("공식 발표", "발표", "공지")):
        return "ANNOUNCEMENT"
    if any(word in text for word in ("공식 발표", "발표", "공지", "공개")):
        return "ANNOUNCEMENT"
    if any(word in text for word in ("굿즈", "유니폼", "패션", "상품", "기념품")):
        return "MERCHANDISE"
    return "OTHER"


def _subject(title: str, action: str, numbers: tuple[str, ...]) -> str:
    cleaned = _clean_headline(title)
    compact_cleaned = re.sub(r"\s+", "", cleaned)
    compact_positions = [index for index, value in enumerate(cleaned) if not value.isspace()]
    first_number = -1
    for value in numbers:
        compact_value = re.sub(r"\s+", "", value)
        compact_index = compact_cleaned.find(compact_value)
        if compact_index < 0 or compact_index >= len(compact_positions):
            continue
        original_index = compact_positions[compact_index]
        if first_number < 0 or original_index < first_number:
            first_number = original_index
    if first_number > 0:
        candidate = cleaned[:first_number]
    elif action and action in cleaned:
        candidate = cleaned[: cleaned.find(action)]
    else:
        marker_match = next(
            (
                match
                for value in _SUBJECT_END_MARKERS
                for match in (
                    re.search(rf"(?<![A-Za-z가-힣]){re.escape(value)}(?![A-Za-z가-힣])", cleaned),
                )
                if match
            ),
            None,
        )
        if marker_match:
            candidate = cleaned[: marker_match.end()]
        else:
            candidate = cleaned.split(" · ", 1)[0]
    if "," in candidate or "，" in candidate:
        candidate = re.split(r"[,，]", candidate, maxsplit=1)[0]
    candidate = re.sub(r"^(?:올해|지난해|이번|내년)\s+", "", candidate).strip(" ,·-")
    candidate = re.sub(r"\s+(?:어디|왜|무슨)\s*(?:갔나|일까|인가)?$", "", candidate).strip(" ,·-")
    candidate = re.sub(r"^\d[\d,.]*\s?원대\s+", "", candidate).strip(" ,·-")
    if len(candidate) < 2:
        candidate = cleaned.split(" · ", 1)[0].strip(" ,·-")
    return candidate[:48]


def _recruitment_subject(title: str, subject: str) -> str:
    """Keep the recruitment subject separate from its trailing metric label."""

    cleaned = re.sub(r"\s+(?:경쟁률|경쟁률은|경쟁률이)$", "", subject).strip(" ,·-")
    return cleaned or _clean_headline(title)


def _action(text: str) -> str:
    return next((word for word in _ACTION_MARKERS if contains_action(text, word)), "")


def _change_phrases(text: str) -> tuple[str, ...]:
    phrases: list[str] = []
    for marker in _CHANGE_MARKERS:
        index = text.find(marker)
        if index < 0:
            continue
        start = max(0, index - 14)
        end = min(len(text), index + len(marker) + 8)
        fragment = re.sub(r"\s+", " ", text[start:end]).strip(" ,·")
        # Description snippets can begin or end in the middle of a sentence.
        # Such fragments are evidence only, never a display fact.
        if _TRUNCATION_RE.search(fragment):
            continue
        if fragment and fragment not in phrases:
            phrases.append(fragment)
    return tuple(phrases[:2])


def _tail_after_first_number(title: str, numbers: tuple[str, ...]) -> str:
    cleaned = _clean_headline(title)
    for number in numbers:
        index = cleaned.find(number)
        if index >= 0:
            tail = cleaned[index + len(number) :].strip(" ,·-")
            for marker in _CHANGE_MARKERS:
                marker_index = tail.find(marker)
                if marker_index < 0:
                    continue
                prefix = tail[:marker_index].strip(" ,·-—")[-16:]
                prefix = re.sub(r"^.*?변동폭\s*", "", prefix)
                value = f"{prefix} {marker}".strip()
                if value and value not in _GENERIC_CHANGE_WORDS:
                    return value
            break
    return ""


def _fact_subject(value: str) -> str:
    """Keep the subject compact when a headline embeds comparison context."""

    text = re.sub(r"\s+", " ", value).strip(" ,·-")
    text = re.split(r"\s+(?:금융위기|코로나|전년|지난해|이후|대비|역대)", text, maxsplit=1)[0]
    text = re.sub(r"\s+(?:최고|최대|최저|최소|급등|급락|상승|하락)$", "", text)
    text = re.sub(r"\s+(?:어디|왜|무슨)\s*(?:갔나|일까|인가)?$", "", text)
    text = re.sub(r"^\d[\d,.]*\s?원대\s+", "", text)
    return text.strip(" ,·-")


def _domain_subject(title: str, subject: str, event_type: str) -> str:
    """Replace a clickbait lead with the stable noun users need."""

    if event_type in {"MARKET", "MARKET_MOVE", "STATISTIC"}:
        clean_title = _clean_headline(title)
        has_fx = any(term in clean_title for term in ("환율", "원달러", "원·달러"))
        has_kospi = "코스피" in clean_title or "KOSPI" in clean_title
        if has_fx and has_kospi:
            first_number = _NUMBER_RE.search(clean_title)
            prefix = clean_title[: first_number.start()] if first_number else clean_title
            if "코스피" in prefix or "KOSPI" in prefix:
                return "코스피"
            if "환율" in prefix or "원달러" in prefix or "원·달러" in prefix:
                return "원·달러 환율"
            return "코스피" if clean_title.find("코스피") < clean_title.find("환율") else "원·달러 환율"
        if has_fx:
            return "원·달러 환율"
        if has_kospi:
            return "코스피"
        if "코스닥" in clean_title or "KOSDAQ" in clean_title:
            return "코스닥"
        if any(term in clean_title for term in ("닛케이", "니케이", "도쿄증시")):
            return "닛케이"
        if "다우" in clean_title:
            return "다우"
        if "나스닥" in clean_title or "NASDAQ" in clean_title:
            return "나스닥"
        if any(term in title for term in ("증시", "주가", "주식")) and subject in {"이젠", "올해", "이번"}:
            return "증시"
    return subject


def _award_subject(title: str, subject: str, *, titles: tuple[str, ...] = ()) -> str:
    """Prefer a repeated named artist/entity over headline decoration.

    Entertainment headlines sometimes prepend a descriptive phrase to the
    artist, while corroborating headlines name the artist directly. A phrase
    repeated across the cluster is safer than treating the whole first
    headline prefix as the subject.
    """

    clean = _clean_headline(title)
    marker = re.search(r"\s+(?:국내외\s+)?(?:음악\s+)?차트\b", clean)
    if not marker:
        return subject
    # A canonical artist+work subject extracted from the article lead is
    # stronger than extending the title prefix through a chart/platform token.
    if subject and any(support in subject for support in _AWARD_SUPPORT_MARKERS):
        prefix = clean[: marker.start()].strip(" ,·-—")
        subject_key = re.sub(r"[^0-9A-Za-z가-힣]", "", subject).casefold()
        prefix_key = re.sub(r"[^0-9A-Za-z가-힣]", "", prefix).casefold()
        if subject_key and prefix_key.startswith(subject_key):
            return subject

    def prefix_tokens(value: str) -> list[str]:
        candidate = _clean_headline(value)
        candidate_marker = re.search(r"\s+(?:국내외\s+)?(?:음악\s+)?차트\b", candidate)
        if not candidate_marker:
            return []
        candidate = candidate[: candidate_marker.start()]
        tokens: list[str] = []
        for token in _AWARD_TOKEN_RE.findall(candidate):
            folded = token.casefold()
            if token.isdigit() or any(character.isdigit() for character in token):
                continue
            if folded in _AWARD_GENERIC_TOKENS:
                continue
            tokens.append(token)
        return tokens

    prefixes = [prefix_tokens(value) for value in (title, *titles)]
    prefixes = [tokens for index, tokens in enumerate(prefixes) if tokens and (index == 0 or tokens != prefixes[0])]
    if prefixes:
        first = prefixes[0]
        best: tuple[str, ...] = ()
        for length in range(min(4, len(first)), 0, -1):
            for start in range(0, len(first) - length + 1):
                phrase = tuple(first[start : start + length])
                if all(
                    any(
                        tokens[index : index + len(phrase)] == list(phrase)
                        for index in range(len(tokens) - len(phrase) + 1)
                    )
                    for tokens in prefixes[1:]
                ):
                    best = phrase
                    break
            if best:
                break
        if best:
            return " ".join(best)
        # With one source, or with differently formatted corroboration, the
        # final named tokens are safer than retaining date/rank decoration.
        if first:
            return " ".join(first[-2:])
    return subject

def _award_supporting_fact(title: str, titles: tuple[str, ...]) -> str:
    """Find a concrete event detail from another corroborating headline.

    A chart cluster can choose a result-heavy headline as its display title,
    leaving the default summary with no information gain.  Reuse only a
    bounded event marker that appears in a different source headline; never
    infer a release or comeback from the retrieval query.
    """

    headline = _clean_headline(title)
    for candidate in titles:
        clean = _clean_headline(candidate)
        if not clean or clean == headline:
            continue
        for marker in _AWARD_SUPPORT_MARKERS:
            match = re.search(rf"{re.escape(marker)}(?:부터|후|당일)?", clean)
            if match and marker not in headline:
                return match.group(0)
    return ""


def _naturalize_release_onset(value: str) -> str:
    """Use a natural post-release connector without adding timing certainty."""

    return re.sub(r"(컴백|출시|발표|공개)\s*부터", r"\1 후", value)


def summary_why_redundant(summary: str, why_it_matters: str) -> bool:
    """Detect exact or near-exact information-structure duplication only."""

    left = re.sub(r"[^0-9a-z가-힣]", "", normalize_text(summary).casefold())
    right = re.sub(r"[^0-9a-z가-힣]", "", normalize_text(why_it_matters).casefold())
    if not left or not right:
        return False
    if left == right:
        return True
    return len(left) >= 20 and len(right) >= 20 and SequenceMatcher(None, left, right).ratio() >= 0.94


def _trend_state(topic_id: str, metrics: tuple[TrendMetric, ...]) -> str:
    relevant = [metric for metric in metrics if metric.topic_id == topic_id]
    if not relevant:
        return "비교 부족"
    states = tuple(effective_trend_state(metric) for metric in relevant)
    rising = "RISE" in states
    falling = "FALL" in states
    if rising and falling:
        return "혼조"
    if rising:
        return "상승"
    if falling:
        return "둔화"
    if "INSUFFICIENT_COMPARISON" in states:
        return "비교 부족"
    return "큰 변화 없음"


def _official_source(items: tuple[object, ...]) -> str:
    for item in items:
        authorities = getattr(item, "authoritative_evidence", ())
        for authority in authorities:
            publisher = str(getattr(authority, "publisher", "") or "").strip()
            if publisher:
                return "공식 자료"
        if EvidenceType.OFFICIAL_SOURCE in getattr(item, "provenance", ()):
            return "공식 자료"
        domain = str(getattr(item, "source_domain", ""))
        if is_trusted_official_domain(domain):
            return "공식 자료"
    return ""


def _particle(value: str) -> str:
    if not value:
        return "는"
    last = value[-1]
    if "가" <= last <= "힣":
        code = ord(last) - 0xAC00
        return "은" if code % 28 else "는"
    return "는"


def _subject_particle(value: str) -> str:
    if not value:
        return "가"
    last = value[-1]
    if "가" <= last <= "힣":
        code = ord(last) - 0xAC00
        return "이" if code % 28 else "가"
    # Use the Korean reading of the final Latin letter, not English spelling.
    # ``N`` (엔) takes 이, while ``T`` (티) takes 가.  This stays bounded to
    # acronyms and avoids a publisher/entity-specific exception list.
    last = value.rstrip()[-1:].casefold()
    if last and last in "fhlmnrsx":
        return "이"
    if last and last in "012345678":
        return "이" if last in "013678" else "가"
    return "가"


def _object_particle(value: str) -> str:
    """Return the Korean object marker for a fact value."""

    if not value:
        return "을"
    last = value.rstrip()[-1]
    if last in "%":
        return "를"
    if "가" <= last <= "힣":
        code = ord(last) - 0xAC00
        return "을" if code % 28 else "를"
    if last.isdigit():
        return "를"
    # Acronym endings such as JYP are pronounced as Korean vowel sounds
    # (피), while F/L/M/N/R/S/X retain a final consonant sound.  Keep this
    # bounded to the same letter heuristic used by _subject_particle.
    return "을" if last.casefold() in "fhlmnrsx" else "를"


def _instrumental_particle(value: str) -> str:
    """Return the Korean ``로/으로`` particle for a noun phrase."""

    if not value:
        return "으로"
    last = value[-1]
    if "가" <= last <= "힣":
        code = ord(last) - 0xAC00
        if code % 28 == 8:  # ㄹ 받침 takes ``로``.
            return "로"
        return "으로" if code % 28 else "로"
    return "으로"


def _conjunction_particle(value: str) -> str:
    """Return ``과/와`` for a clean noun phrase used by our templates."""

    if not value:
        return "과"
    last = value.rstrip()[-1]
    if "가" <= last <= "힣":
        return "과" if (ord(last) - 0xAC00) % 28 else "와"
    return "과" if last.casefold() in "bcdfghjklmnpqrstvwxyz" else "와"


def _strip_news_byline(value: str) -> str:
    """Remove a wire-service dateline/byline from a reader-facing fact."""

    cleaned = re.sub(r"^(?:\[[^]]+\]\s*)?[^=\n]{1,80}?\s+기자\s*=\s*", "", value).strip()
    return re.sub(r"([.!?])(?=[A-Za-z가-힣])", r"\1 ", cleaned)


_POLICY_AUDIENCE_TITLE_RE = re.compile(
    r"^(?P<owner>[^,，]+)[,，]\s*(?P<object>.+?)\s+"
    r"(?P<audience>(?:(?:전|전체|모든)\s*)?"
    r"(?:직원|시민|주민|학생|고객|사용자|회원|관객|교사|장병|국민|기업|가구|환자)\s*대상)\s+"
    r"(?P<verb>시행|도입|적용|배포|운영)$"
)


def _structured_policy_sentence(title: str, evidence: str) -> str:
    """Render an actor/object/audience title without crossing subject bounds."""

    clean_title = _clean_headline(title)
    match = _POLICY_AUDIENCE_TITLE_RE.match(clean_title)
    if not match:
        return ""
    owner = match.group("owner").strip()
    object_text = match.group("object").strip()
    audience = match.group("audience").strip()
    verb = match.group("verb")
    audience_noun = re.sub(r"\s*대상$", "", audience).strip()
    if not owner or not object_text or not audience_noun:
        return ""
    target_clause = f"{audience_noun}{_object_particle(audience_noun)} 대상으로"
    evidence_text = normalize_text(evidence)
    if "절차" in evidence_text and any(marker in evidence_text for marker in ("시작", "착수", "들어")):
        status = f"{verb} 절차에 들어갔다."
    else:
        status = f"{verb}한다."
    return (
        f"{owner}{_subject_particle(owner)} {object_text}{_object_particle(object_text)} "
        f"{target_clause} {status}"
    )


def _policy_role_sentence(
    actor: str,
    condition: str,
    policy_object: str,
    action: str,
) -> str:
    """Render policy roles only when the structured predicate is explicit."""

    if not actor or not policy_object or not action:
        return ""
    condition_clause = normalize_text(condition)
    condition_match = re.match(
        r"(?P<subject>.+?)(?P<particle>[이가])?\s*"
        r"(?P<ending>없다면|없으면|없을\s+경우|없는\s+경우|있다면|있으면|있을\s+경우)$",
        condition_clause,
    )
    if condition_match is not None:
        condition_subject = condition_match.group("subject").strip()
        condition_subject = re.sub(
            r"(?<=[가-힣])(?=(?:충격|위험|변동|악화|개선|문제)$)",
            " ",
            condition_subject,
        )
        condition_particle = condition_match.group("particle") or _subject_particle(
            condition_subject
        )
        condition_clause = (
            f"{condition_subject}{condition_particle} {condition_match.group('ending')}"
        )
    if condition_clause:
        condition_clause += " "

    if action == "추가 인상 가능성 언급":
        predicate = "추가로 인상할 가능성을 언급했다."
    elif action == "인상 가능성 언급":
        predicate = "인상할 가능성을 언급했다."
    elif action == "인하 가능성 언급":
        predicate = "인하할 가능성을 언급했다."
    elif action in {"인상", "인하", "동결", "유지"}:
        predicate = f"{action} 방침을 밝혔다."
    else:
        return ""
    return (
        f"{actor}{_particle(actor)} {condition_clause}"
        f"{policy_object}{_object_particle(policy_object)} {predicate}"
    )


def _sports_result_subject(subject: str, facts: tuple[EventFact, ...], title: str = "") -> str:
    """Remove leading performance facts from a sports subject without guessing."""

    clean = _normalise_display_sentence(subject)
    for fact in facts:
        value = _event_fact_value(fact)
        if value:
            clean = re.sub(rf"^{re.escape(value)}\s*", "", clean)
    if clean in {"구단", "팀", "선수", "구단 관계자"} and title:
        title_subject = _clean_headline(title).split(",", 1)[0].strip()
        for fact in facts:
            value = _event_fact_value(fact)
            if value:
                title_subject = re.sub(rf"^{re.escape(value)}\s*", "", title_subject)
        if title_subject and title_subject not in {"구단", "팀", "선수"}:
            clean = title_subject
    return clean.strip(" ,·-—") or _normalise_display_sentence(subject)


def _number_with_ro(value: str) -> str:
    """Attach the Korean instrumental marker without producing ``원로``."""

    return f"{value}로" if value.endswith(("%", "달러")) else f"{value}으로"


def _market_direction_sentence(subject: str, marker: str) -> str:
    """Render a direction with the correct Korean predicate form."""

    if marker in {"상승", "하락", "급등", "급락", "증가", "감소", "확대", "축소", "돌파"}:
        return f"{subject}{_particle(subject)} {marker}했다."
    if marker == "보합":
        return f"{subject}{_particle(subject)} 보합세를 보였다."
    return f"{subject}{_particle(subject)} {marker}를 보였다."


def _next_signal(event_type: str, text: str, date: str, action: str) -> str:
    if event_type in {"STATISTIC", "MARKET", "MARKET_MOVE"}:
        if "월" in text:
            return "다음 월간 통계와 변동폭"
        if "분기" in text:
            return "다음 분기 통계와 변화폭"
        if "연간" in text or "연도" in text:
            return "다음 연간 통계와 변화폭"
        return ""
    if event_type in {"SCHEDULED_EVENT", "SPORTS_EVENT", "ENTERTAINMENT_EVENT"} and date:
        noun = "경기·행사" if event_type == "SPORTS_EVENT" else "행사"
        return f"{date} {noun} 결과와 공식 후속 발표"
    if event_type == "POLICY" and (date or "시행" in text):
        return "시행일과 세부 고시"
    if event_type == "ANNOUNCEMENT" and (
        date or any(word in text for word in ("시행", "실행", "적용", "예정", "출시"))
    ):
        return "실행 시점과 공식 전문"
    return ""


def _event_fact_value(fact: EventFact) -> str:
    value = normalize_text(fact.value)
    if not value:
        return ""
    if fact.unit in {"명", "위", "주", "표", "홈런", "타점"} and not value.endswith(fact.unit):
        return f"{value}{fact.unit}"
    return value


def _event_fact_map(facts: tuple[EventFact, ...]) -> dict[str, str]:
    return {fact.role: _event_fact_value(fact) for fact in facts if _event_fact_value(fact)}


def _compact_fact_value(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣%]", "", normalize_text(value).casefold())


def industry_summary_preserves_fact_binding(
    headline: str,
    summary: str,
    facts: tuple[EventFact, ...],
) -> bool:
    """Require every material industry relationship to survive synthesis."""

    if not facts:
        return True
    compact_summary = _compact_fact_value(summary)
    if not compact_summary:
        return False
    for fact in facts:
        if fact.role == "EVENT_RELATION":
            if not _relation_detail_supports_fact(summary, fact):
                return False
            continue
        for value in (fact.value, fact.related_value):
            if value and _compact_fact_value(value) not in compact_summary:
                return False
    return True


def _event_relation_fact(facts: tuple[EventFact, ...]) -> EventFact | None:
    return next((fact for fact in facts if fact.role == "EVENT_RELATION"), None)


_RELATION_ANNOUNCED_MARKERS = (
    "다고 밝혔다",
    "라고 밝혔다",
    "다고 전했다",
    "라고 전했다",
    "다고 말했다",
    "라고 말했다",
    "다고 발표했다",
    "라고 발표했다",
)
_RELATION_NEGATION_MARKERS = (
    "않",
    "안 ",
    "못 ",
    "부인",
    "무산",
    "없다",
    "없다고",
    "아니다",
    "확정되지",
)
_RELATION_UNCERTAIN_MARKERS = (
    "가능성",
    "가능하다",
    "가능성이",
    "수 있다",
    "수도 있다",
    "검토",
    "논의",
    "전망",
    "거론",
    "여부",
    "싶다",
)
_RELATION_NEGATION_EXEMPT_ACTIONS = frozenset({"영입 무산"})
_RELATION_FUTURE_MARKERS: dict[str, tuple[str, ...]] = {
    "완화": ("완화하기로", "완화할", "완화 예정이다"),
    "착공": ("착공식을 연다", "착공식을 열 예정이다", "착공할", "착공 예정", "착공하기로"),
    "공급": ("공급할", "공급 예정이다", "공급하기로"),
    "수주": ("수주할", "수주 예정이다", "수주하기로"),
    "신설": ("신설할", "신설 예정이다", "신설하기로"),
    "출범": ("출범할", "출범 예정이다", "출범하기로"),
    "투자": ("투자할", "투자 예정이다", "투자하기로"),
    "지원": ("지원할", "지원 예정이다", "지원하기로"),
    "선정": ("선정될", "선정 예정이다", "선정하기로"),
    "지정": ("지정될", "지정 예정이다", "지정하기로"),
    "떠남": ("떠난다", "떠날", "떠나기로", "떠날 예정이다"),
    "결별": ("결별할", "결별 예정이다", "결별하기로"),
    "이적": ("이적할", "이적 예정이다", "이적하기로"),
}
_RELATION_PRESENT_MARKERS: dict[str, tuple[str, ...]] = {
    "완화": ("완화한다",),
    "공급": ("공급한다",),
    "신설": ("신설한다",),
    "출범": ("출범한다",),
    "투자": ("투자한다",),
    "지원": ("지원한다",),
}
_RELATION_ACTION_MARKERS: dict[str, tuple[str, ...]] = {
    "선정": ("선정", "결정됐다", "결정되었다"),
    "지정": ("지정", "결정됐다", "결정되었다"),
    "떠남": ("떠나", "떠난", "떠났", "떠날", "결별"),
    "영입 무산": ("영입", "무산"),
    "계약 체결": ("체결",),
    "이적 확정": ("이적", "확정"),
    "트레이드 성사": ("트레이드", "성사"),
}
_RELATION_CLAUSE_BOUNDARIES = ",.?!;:。！？，、"
_RELATION_COMPLETED_MARKERS: dict[str, tuple[str, ...]] = {
    "완화": ("완화했다", "완화됐다", "완화되었다"),
    "착공": ("착공식을 열었다", "착공했다", "착공에 들어갔다"),
    "공급": ("공급했다", "공급됐다"),
    "수주": ("수주했다", "수주됐다"),
    "신설": ("신설했다", "신설됐다"),
    "출범": ("출범했다",),
    "투자": ("투자했다",),
    "지원": ("지원했다", "지원됐다"),
    "선정": ("선정됐다", "선정되었다", "선정했다", "결정됐다", "결정되었다"),
    "지정": ("지정됐다", "지정되었다", "지정했다", "결정됐다", "결정되었다"),
    "떠남": ("떠났다",),
    "결별": ("결별했다",),
    "이적": ("이적했다",),
}


def _relation_action_markers(action: str) -> tuple[str, ...]:
    return _RELATION_ACTION_MARKERS.get(action, (action,))


def _relation_window_contains(text: str, action: str, markers: tuple[str, ...]) -> bool:
    """Check polarity markers only near the bound relation predicate."""

    normalized = normalize_text(text)
    if not normalized:
        return False
    for action_marker in _relation_action_markers(action):
        for match in re.finditer(re.escape(action_marker), normalized):
            left_boundary = max(
                (normalized.rfind(boundary, 0, match.start()) for boundary in _RELATION_CLAUSE_BOUNDARIES),
                default=-1,
            ) + 1
            right_boundaries = [
                position
                for boundary in _RELATION_CLAUSE_BOUNDARIES
                for position in (normalized.find(boundary, match.end()),)
                if position >= 0
            ]
            right_boundary = min(right_boundaries, default=len(normalized))
            window = normalized[
                max(left_boundary, match.start() - 24) : min(right_boundary, match.end() + 40)
            ]
            if any(marker in window for marker in markers):
                return True
    return False


def _relation_text_temporal_mode(text: str, action: str) -> str:
    """Classify one bounded relation clause without inventing completion."""

    normalized = normalize_text(text)
    if not normalized:
        return "UNKNOWN"
    if (
        action not in _RELATION_NEGATION_EXEMPT_ACTIONS
        and _relation_window_contains(normalized, action, _RELATION_NEGATION_MARKERS)
    ):
        return "NEGATED"
    if _relation_window_contains(normalized, action, _RELATION_UNCERTAIN_MARKERS):
        return "POSSIBILITY"
    if _relation_window_contains(normalized, action, _RELATION_ANNOUNCED_MARKERS):
        return "ANNOUNCED"
    if any(marker in normalized for marker in _RELATION_FUTURE_MARKERS.get(action, ())):
        return "FUTURE"
    if any(marker in normalized for marker in _RELATION_PRESENT_MARKERS.get(action, ())):
        return "ONGOING"
    if any(marker in normalized for marker in _RELATION_COMPLETED_MARKERS.get(action, ())):
        return "COMPLETED"
    return "UNKNOWN"


def _relation_temporal_mode(title: str, evidence: str, action: str) -> str:
    """Read only source-backed tense cues for a relation fallback.

    The typed relation answers what the event is; this bounded adapter only
    prevents the fallback sentence from upgrading a planned or announced
    action into a completed one.  Evidence is checked before the title so a
    fuller lead can resolve a nominal headline safely.
    """

    for value in (evidence, title):
        mode = _relation_text_temporal_mode(value, action)
        if mode != "UNKNOWN":
            return mode
    return "UNKNOWN"


def _relation_detail_supports_fact(detail: str, fact: EventFact) -> bool:
    """Allow source modifiers without losing subject/object ownership."""

    detail_key = _compact_fact_value(detail)
    subject_key = _compact_fact_value(fact.subject)
    subject_terms = [
        _compact_fact_value(term)
        for term in re.findall(r"[A-Za-z0-9가-힣·&'’\-]+", fact.subject)
        if _compact_fact_value(term)
    ]
    if subject_key not in detail_key and not any(
        len(term) >= 2 and term in detail_key for term in subject_terms[-1:]
    ):
        return False
    object_terms = re.findall(r"[A-Za-z0-9가-힣·&'’\-]+", fact.object)
    if not all(_compact_fact_value(term) in detail_key for term in object_terms if term):
        return False
    action_markers = _relation_action_markers(fact.relation)
    return any(_compact_fact_value(marker) in detail_key for marker in action_markers)


def relation_summary_preserves_fact(summary: str, headline: str, fact: EventFact) -> bool:
    """Require relation, polarity, and temporal commitment to agree."""

    if _compact_fact_value(headline) == _compact_fact_value(summary):
        return False
    if not _relation_detail_supports_fact(summary, fact):
        return False
    headline_mode = _relation_text_temporal_mode(headline, fact.relation)
    summary_mode = _relation_text_temporal_mode(summary, fact.relation)
    if summary_mode in {"NEGATED", "POSSIBILITY"}:
        return False
    if headline_mode in {"NEGATED", "POSSIBILITY"}:
        return False
    if headline_mode == "FUTURE" and summary_mode == "COMPLETED":
        return False
    if headline_mode == "ANNOUNCED" and summary_mode == "COMPLETED":
        return False
    if headline_mode == "COMPLETED" and summary_mode in {"FUTURE", "ANNOUNCED"}:
        return False
    if headline_mode == "ONGOING" and summary_mode == "COMPLETED":
        return False
    return True


_relation_summary_preserves_fact = relation_summary_preserves_fact


def _relation_headline(fact: EventFact) -> str:
    """Keep the subject and minimum identifying object in a relation headline."""

    object_tokens = [
        token
        for token in re.findall(r"[A-Za-z0-9가-힣·&'’\-]+", fact.object)
        if not re.fullmatch(r"\d+(?:[.,]\d+)?(?:년|월|일|주)?", token)
        and token not in {"만에", "조기", "공식"}
    ]
    # Keep the identifying tail of a long object phrase.  This preserves a
    # place/product/program context without making the headline a copy of the
    # source lead, leaving the summary room for a material supporting detail.
    object_label = " ".join(object_tokens[-4:]) if object_tokens else fact.object
    subject = normalize_text(fact.subject)
    action_label = {
        "떠남": "결별",
        "영입 무산": "영입 무산",
    }.get(fact.relation, fact.relation)
    return " ".join(part for part in (f"{subject}," if subject else "", object_label, action_label) if part)


def _event_relation_summary(
    title: str,
    completion_evidence: str,
    fact: EventFact,
) -> str:
    """Render only the subject/object/predicate already owned by the event."""

    detail = normalize_text(completion_evidence)
    normalized_title = normalize_text(title)
    if normalized_title and detail.startswith(normalized_title):
        detail = detail[len(normalized_title) :].strip(" ,:·-—")
    detail = _strip_news_byline(detail).rstrip(" .!?。！")
    action = fact.relation
    detail_supports_fact = _relation_detail_supports_fact(detail, fact)
    temporal_mode = _relation_temporal_mode(title, completion_evidence, action)
    if temporal_mode in {"NEGATED", "POSSIBILITY"}:
        if (
            detail
            and not _TRUNCATION_RE.search(detail)
            and not editorial_text_issues(detail)
            and detail_supports_fact
            and summary_information_gain(title, detail)
        ):
            return f"{detail}."
        return ""
    if (
        detail
        and not _TRUNCATION_RE.search(detail)
        and not editorial_text_issues(detail)
        and summary_information_gain(title, detail)
        and detail_supports_fact
    ):
        return f"{detail}."
    if (
        detail
        and not _TRUNCATION_RE.search(detail)
        and not editorial_text_issues(detail)
        and detail_supports_fact
        and action in {"선정", "지정"}
    ):
        role_marker = next(
            (marker for marker in ("참여사", "파트너", "협력사", "Partner") if marker in detail),
            "",
        )
        if role_marker and temporal_mode == "COMPLETED":
            subject_particle = _subject_particle(fact.subject)
            if role_marker == "Partner" and fact.object.rstrip().casefold().endswith("partner"):
                return f"{fact.subject}{subject_particle} {fact.object}로 선정됐다."
            return f"{fact.subject}{subject_particle} {fact.object} {role_marker}로 결정됐다."

    subject = fact.subject
    object_text = fact.object
    if not subject or not object_text:
        return ""
    if temporal_mode == "ANNOUNCED":
        subject_prefix = f"{subject}{_particle(subject)}"
        if action == "떠남":
            return f"{subject_prefix} {object_text}{_object_particle(object_text)} 떠난다고 밝혔다."
        if action == "착공":
            return f"{subject_prefix} {object_text} 착공 계획을 밝혔다."
        if action == "투자":
            return f"{subject_prefix} {object_text}에 투자하겠다고 밝혔다."
    if temporal_mode == "FUTURE":
        subject_prefix = f"{subject}{_particle(subject)}"
        date_match = _DATE_RE.search(f"{completion_evidence} {title}")
        date = f"{date_match.group(0).replace(' ', '')} " if date_match else ""
        if action == "착공":
            return f"{subject_prefix} {date}{object_text} 착공 예정이다."
        if action == "떠남":
            return f"{subject_prefix} {object_text}{_object_particle(object_text)} 떠날 예정이다."
        if action == "투자":
            return f"{subject_prefix} {object_text}에 투자할 예정이다."
        if action == "완화":
            return f"{subject_prefix} {object_text}{_object_particle(object_text)} 완화할 예정이다."
        if action in {"선정", "지정"}:
            return f"{subject_prefix} {object_text}{_instrumental_particle(object_text)} {action}될 예정이다."
        if action in {"공급", "지원", "수주", "신설", "출범"}:
            return f"{subject_prefix} {object_text}{_object_particle(object_text)} {action}할 예정이다."
    if temporal_mode == "ONGOING":
        subject_prefix = f"{subject}{_particle(subject)}"
        if action == "완화":
            return f"{subject_prefix} {object_text}{_object_particle(object_text)} 완화한다."
        if action in {"공급", "지원", "수주", "신설", "출범"}:
            return f"{subject_prefix} {object_text}{_object_particle(object_text)} {action}한다."
        if action == "투자":
            return f"{subject_prefix} {object_text}에 투자한다."
    if temporal_mode == "UNKNOWN":
        subject_prefix = f"{subject}{_particle(subject)}"
        if action in {"선정", "지정"}:
            return f"{subject_prefix} {object_text} {action} 사실이 확인됐다."
        if action == "떠남":
            return f"{subject_prefix} {object_text}{_object_particle(object_text)} 떠나는 내용이 확인됐다."
        return f"{subject_prefix} {object_text} {action} 소식이 확인됐다."
    if action == "완화":
        return f"{subject}{_particle(subject)} {object_text}{_object_particle(object_text)} 완화했다."
    if action == "착공":
        return f"{subject}{_particle(subject)} {object_text} 착공에 들어갔다."
    if action == "공급":
        return f"{subject}{_particle(subject)} {object_text}{_object_particle(object_text)} 공급한다."
    if action == "수주":
        return f"{subject}{_particle(subject)} {object_text}{_object_particle(object_text)} 수주했다."
    if action == "신설":
        return f"{subject}{_particle(subject)} {object_text}{_object_particle(object_text)} 신설했다."
    if action == "출범":
        return f"{subject}{_particle(subject)} {object_text}{_instrumental_particle(object_text)} 출범했다."
    if action == "투자":
        return f"{subject}{_particle(subject)} {object_text}에 투자했다."
    if action == "지원":
        return f"{subject}{_particle(subject)} {object_text}{_object_particle(object_text)} 지원한다."
    if action in {"선정", "지정"}:
        marker = "에" if re.search(r"(?:프로그램|Program)$", object_text, re.IGNORECASE) else "로"
        return f"{subject}{_particle(subject)} {object_text}{marker} {action}됐다."
    if action in {"해지", "종료", "만료", "해제"}:
        return f"{subject}{_particle(subject)} {object_text}{_object_particle(object_text)} {action}했다."
    if action == "떠남":
        return f"{subject}{_particle(subject)} {object_text}{_object_particle(object_text)} 떠났다."
    if action == "결별":
        return f"{subject}{_particle(subject)} {object_text}{_conjunction_particle(object_text)} 결별했다."
    if action == "이적":
        return f"{subject}{_particle(subject)} {object_text}{_instrumental_particle(object_text)} 이적했다."
    if action == "영입 무산":
        return f"{subject}의 {object_text} 영입이 무산됐다."
    if action in {"영입 확정", "계약 체결", "방출", "이적 확정", "트레이드 성사"}:
        return f"{subject}의 {object_text} {action}이 확인됐다."
    return ""


def _industry_fact_summary(
    title: str,
    subject: str,
    action: str,
    completion_evidence: str,
    facts: tuple[EventFact, ...],
) -> str:
    """Render a fact-rich industry event without rebuilding loose numbers."""

    detail = normalize_text(completion_evidence)
    clean_title = normalize_text(title)
    if clean_title and detail.startswith(clean_title):
        detail = detail[len(clean_title) :].strip(" ,:·-—")
    detail = _strip_news_byline(detail).rstrip(" .!?。！")
    if (
        detail
        and not _TRUNCATION_RE.search(detail)
        and not editorial_text_issues(detail)
        and not any(marker in detail for marker in _GENERIC_SUMMARY_MARKERS)
        and summary_information_gain(title, detail)
        and industry_summary_preserves_fact_binding(title, detail, facts)
    ):
        return f"{detail}."

    fact = next(iter(facts), None)
    if fact is None:
        if action == "유치" and clean_title:
            return f"{_clean_headline(title)}."
        return ""
    if fact is None or not subject:
        return ""
    if fact.role == "TREND_CHANGE":
        # A trend headline needs an additional same-focus source detail to
        # provide information gain. Without it, returning a polished copy of
        # the headline would recreate the old mixed-focus false pass.
        return ""
    if fact.role == "EVENT_RELATION":
        return _event_relation_summary(title, completion_evidence, fact)
    subject_particle = _subject_particle(subject)
    if fact.role == "RATIO_CHANGE" and fact.related_value:
        label = fact.subject or next(
            (marker for marker in ("점유율", "비중", "비율", "경쟁률") if marker in title),
            "비율",
        )
        change_word = action if action in {"확대", "축소", "증가", "감소"} else "변했다"
        return f"{subject}의 {label}이 {fact.value}에서 {fact.related_value}로 {change_word}됐다."
    if fact.role == "PRODUCTION_CHANGE" and fact.related_value:
        change_word = f"{action}됐다" if action in {"확대", "축소", "증가", "감소"} else "바뀌었다"
        return (
            f"{subject}의 생산 관련 수치가 {fact.value}에서 "
            f"{fact.related_value}{_instrumental_particle(fact.related_value)} {change_word}."
        )
    if fact.role == "COMPARISON" and fact.related_value:
        return f"{subject} 관련 비교 수치는 {fact.value}와 {fact.related_value}로 제시됐다."
    if fact.role == "CONTRACT_QUANTITY":
        return f"{subject}{subject_particle} {fact.value} 규모의 공급 계약을 체결했다."
    if fact.role == "ACQUISITION_AMOUNT":
        return f"{subject}{subject_particle} {fact.value} 규모 인수에 나섰다."
    if fact.role == "STRATEGY_AMOUNT":
        return f"{subject}{subject_particle} 전략 관련 {fact.value} 규모 투자를 추진한다."
    if fact.role == "PRODUCTION_QUANTITY":
        return f"{subject}{subject_particle} {fact.value} 규모의 생산 계획을 제시했다."
    if fact.role == "INVESTMENT_AMOUNT":
        evidence_text = f"{title} {completion_evidence}"
        if "유치" in evidence_text:
            return f"{subject}{subject_particle} {fact.value} 규모의 투자를 유치했다."
        return f"{subject}{subject_particle} {fact.value} 규모의 투자 계획을 제시했다."
    return ""


def _headline(
    title: str,
    event_type: str,
    subject: str,
    numbers: tuple[str, ...],
    change: str,
    *,
    date: str = "",
    action: str = "",
    temporal_state: str = "",
    observations: tuple[MetricObservation, ...] = (),
    event_facts: tuple[EventFact, ...] = (),
) -> str:
    cleaned = _clean_headline(title)
    relation_fact = _event_relation_fact(event_facts)
    if relation_fact is not None:
        return _relation_headline(relation_fact)
    if event_type == "EARNINGS" and subject:
        period, metric, value = _earnings_fact_parts(cleaned)
        if metric and value:
            fact = " ".join(part for part in (period, metric, value) if part)
            direction = next((item.direction for item in observations if item.direction), "")
            if value.endswith(("%", "퍼센트")) and direction:
                fact = f"{fact} {direction}"
            return f"{subject} {fact} 실적"
    if event_type == "AWARD_CHART" and subject and re.search(r"\bbillboard\b", cleaned, re.IGNORECASE):
        fact_map = _event_fact_map(event_facts)
        rank = fact_map.get("CHART_RANK", "")
        chart = "빌보드 200" if re.search(r"\bbillboard\s*200\b", cleaned, re.IGNORECASE) else "빌보드 차트"
        if rank:
            return f"{subject}, {chart} {rank}"
    if event_type in {"STATISTIC", "MARKET", "MARKET_MOVE", "EARNINGS"} and subject and numbers:
        run_phrase = _market_run_phrase(cleaned)
        if run_phrase:
            return f"{subject} {run_phrase}"
        metric_number = _market_metric_number(cleaned, numbers)
        if not metric_number:
            return f"{subject} {change}" if change and change not in _GENERIC_CHANGE_WORDS else subject
        result = f"{subject} {metric_number}"
        # A change fragment from a title without a number is often a clipped
        # article lead (for example ``미 증시 상승 마감에 코스피``).  The
        # metric itself is safe; appending that fragment creates a malformed
        # headline and can imply an unsupported comparison.
        if change and not _NUMBER_RE.search(cleaned) and change not in cleaned:
            change = ""
        for marker in ("강보합세", "강세", "약세", "상승", "하락", "급등", "급락"):
            if marker in change:
                change = marker
                break
        if change and change not in _GENERIC_CHANGE_WORDS and change not in result:
            result += f" · {change}"
        return result
    if event_type == "SPORTS_INTERRUPTION":
        league = "프로야구" if "프로야구" in cleaned or "프로야구" in subject else ("KBO" if "KBO" in cleaned else subject)
        if temporal_state == "RESUMING":
            return " ".join(part for part in (league, date, "경기 재개 예정") if part).strip() or "경기 재개 예정"
        if temporal_state == "RESUMED":
            return " ".join(part for part in (league, date, "경기 재개") if part).strip() or "경기 재개"
        if temporal_state == "CANCELLED":
            return f"{league} 경기 취소" if league else "경기 취소"
        return f"{league} 폭염으로 경기 중단" if league else "폭염으로 경기 중단"
    if event_type in {"AWARD_CHART", "PRODUCT_RELEASE", "INDUSTRY_CHANGE", "REGULATION", "POLICY", "ANNOUNCEMENT"}:
        return cleaned or subject or "주요 변화"
    if event_type in {"SCHEDULED_EVENT", "SPORTS_EVENT", "ENTERTAINMENT_EVENT"} and subject:
        if event_type == "SCHEDULED_EVENT" and action in {"발표", "발매", "출시", "공개"} and action in cleaned:
            return _editorial_headline(cleaned, subject=subject)
        if event_type == "SCHEDULED_EVENT" and any(
            marker in cleaned for marker in ("프로젝트", "기념", "선보인다")
        ) and len(cleaned) <= 60:
            return _editorial_headline(cleaned, subject=subject)
        # Keep event headlines factual and short; omit article-style hype
        # after the event verb.
        event_action = action if action in _EVENT_ACTIONS else ""
        event_date = date if date and date not in subject else ""
        if event_action:
            return " ".join(part for part in (subject, event_date, event_action) if part).strip() or cleaned
        return f"{subject} 일정" if date else subject
    return _editorial_headline(title, subject=subject)


def _summary(
    title: str,
    event_type: str,
    subject: str,
    action: str,
    date: str,
    location: str,
    numbers: tuple[str, ...],
    change: str,
    source_count: int,
    uncertainty: str,
    completion_evidence: str = "",
    market_observation: MetricObservation | None = None,
    market_observations: tuple[MetricObservation, ...] = (),
    temporal_state: str = "",
    supporting_titles: tuple[str, ...] = (),
    event_facts: tuple[EventFact, ...] = (),
    cause: str = "",
    condition: str = "",
    policy_object: str = "",
) -> str:
    relation_fact = _event_relation_fact(event_facts)
    if relation_fact is not None:
        relation_sentence = _event_relation_summary(title, completion_evidence, relation_fact)
        if relation_sentence:
            return relation_sentence
    if event_type == "EARNINGS" and subject:
        observation = next(iter(market_observations), None)
        period, metric, value = (
            (observation.period, observation.metric, observation.value)
            if observation is not None
            else _earnings_fact_parts(completion_evidence or title)
        )
        if metric and value:
            period_text = f"{period} " if period else ""
            if observation is not None and observation.direction:
                sentence = (
                    f"{subject}의 {period_text}{metric}이 "
                    f"{value} {observation.direction}했다고 밝혔다."
                )
            else:
                sentence = (
                    f"{subject}{_subject_particle(subject)} {period_text}{metric} "
                    f"{value}{_object_particle(value)} 기록했다고 밝혔다."
                )
            if uncertainty:
                sentence += f" {uncertainty}"
            return sentence.strip()
    if event_type in {"STATISTIC", "MARKET", "MARKET_MOVE", "EARNINGS"} and subject:
        summary_subject = "" if _TIME_PREFIX_RE.match(subject) else subject
        summary_subject = _fact_subject(summary_subject)
        observations = tuple(
            observation
            for observation in (market_observations or ((market_observation,) if market_observation else ()))
            if observation.value and observation.direction and observation.direction != "변동"
        )
        if observations:
            sentences: list[str] = []
            for observation in observations[:3]:
                marker = observation.direction
                verb = {"강세": "상승", "약세": "하락"}.get(marker, marker)
                sentence_subject = _fact_subject(observation.instrument or summary_subject)
                sentences.append(
                    f"{sentence_subject}{_particle(sentence_subject)} {observation.value} {verb}했다."
                )
            sentence = " ".join(sentences)
            if completion_evidence:
                # Add one additional, trusted clause when the lead contains
                # a concrete related fact.  Do not paste a generic evidence
                # macro or borrow a second metric's direction.
                detail_parts = re.split(r"(?:했고|하며|지만|그리고|,|，)", completion_evidence)
                detail = next(
                    (
                        part.strip(" ,，:·-—")
                        for part in detail_parts
                        if len(part.strip()) >= 12
                        and not any(
                            marker in part
                            for marker in (
                                "공식 발표와",
                                "여러 보도",
                                "여러 매체",
                                "핵심 내용",
                                "세부 내용",
                            )
                        )
                        and not any(observation.instrument in part for observation in observations)
                    ),
                    "",
                )
                if detail and summary_information_gain(title, detail):
                    sentence += f" {detail.rstrip(' .!?')}."
            if source_count > 1:
                sentence += " 같은 흐름이 여러 보도에서 확인됐다."
            return sentence
        quote_detail = _market_quote_detail(title, numbers, change)
        run_phrase = _market_run_phrase(title)
        if quote_detail:
            source_note = "여러 보도에서 확인됐다." if source_count > 1 else "한 건의 보도에서 제시됐다."
            sentence = f"{summary_subject} {quote_detail}이 {source_note}"
        elif run_phrase:
            sentence = f"{summary_subject}의 {run_phrase}가 이어졌다."
        elif (
            event_type == "MARKET"
            and len(numbers) >= 2
            and any(marker in change for marker in ("최대", "최고", "급등", "급락", "변동"))
        ):
            sentence = f"{summary_subject} 변동폭이 {numbers[0]}과 {numbers[1]} 사이를 오가며 {change} 수준으로 확대됐다."
        elif (
            event_type == "MARKET"
            and change
            and any(marker in change for marker in ("최대", "최고", "변동폭"))
        ):
            metric_number = _market_metric_number(title, numbers)
            if metric_number:
                sentence = f"{summary_subject} 변동폭이 {_number_with_ro(metric_number)} {change} 수준으로 확대됐다."
            else:
                sentence = f"{summary_subject} 변동성이 {change} 수준으로 확대됐다."
        elif change and change not in _GENERIC_CHANGE_WORDS:
            marker = next((word for word in _DIRECTIONAL_CHANGE_WORDS if word in change), "")
            if marker == "강보합세" and summary_subject and numbers:
                sentence = f"{summary_subject}{_particle(summary_subject)} {numbers[0]}에서 강보합세를 보였다."
            elif marker and summary_subject and numbers and numbers[0].endswith(("%", "달러", "선")):
                verb = {"강세": "상승", "약세": "하락"}.get(marker, marker)
                if numbers[0].endswith("선"):
                    sentence = f"{summary_subject}{_particle(summary_subject)} {numbers[0]}에서 {verb} 흐름을 보였다."
                else:
                    sentence = f"{summary_subject}{_particle(summary_subject)} {_number_with_ro(numbers[0])} {verb}했다."
            elif marker and summary_subject:
                sentence = _market_direction_sentence(summary_subject, marker)
            else:
                lead = f"{summary_subject}의 " if summary_subject else ""
                if numbers:
                    sentence = f"{lead}{numbers[0]} 수치가 "
                    sentence += "여러 보도에서 확인됐다." if source_count > 1 else "한 건의 보도에서 제시됐다. 추가 확인이 필요하다."
                else:
                    sentence = ""
        elif source_count > 1:
            lead = f"{summary_subject}의 " if summary_subject else ""
            sentence = f"{lead}{numbers[0]} 수치가 여러 보도에서 확인됐다." if numbers else ""
        else:
            lead = f"{summary_subject}의 " if summary_subject else ""
            sentence = f"{lead}{numbers[0]} 수치가 한 건의 보도에서 제시돼 추가 확인이 필요하다." if numbers else ""
    elif event_type in {"SCHEDULED_EVENT", "SPORTS_EVENT", "ENTERTAINMENT_EVENT"} and subject:
        event_phrase = action if action in _EVENT_ACTIONS else ""
        if any(marker in completion_evidence for marker in _COMPLETION_MARKERS):
            if event_type == "ENTERTAINMENT_EVENT" and event_phrase == "컴백":
                duration_match = re.search(r"\d+\s?년만", title)
                duration = duration_match.group(0).replace("만", " 만에") if duration_match else ""
                season = "여름" if "여름" in title else ""
                detail = " ".join(value for value in (duration, season) if value)
                sentence = f"{subject}{_subject_particle(subject)} {detail + ' ' if detail else ''}컴백 활동을 마쳤다."
            else:
                when = f"{date} " if date else ""
                where = f"{location} " if location else ""
                event_noun = event_phrase or "행사"
                particle = "이" if event_noun == "컴백" else "가"
                sentence = f"{subject}의 {when}{where}{event_noun}{particle} 성황리에 진행됐다."
        elif event_type == "ENTERTAINMENT_EVENT" and ("컴백" in title or action == "컴백") and date:
            sentence = f"{subject}가 {date} 컴백한다."
        elif event_type == "ENTERTAINMENT_EVENT" and ("앨범" in title or action == "발매") and date:
            sentence = f"{subject}가 {date} 앨범을 발매한다."
        elif event_phrase == "컴백" and date:
            sentence = f"{subject}의 컴백은 {date}로 예정돼 있다."
        elif date or location:
            when = f"{date} " if date else ""
            where = f"{location}에서 " if location else ""
            phrase = f"{event_phrase} 일정이" if event_phrase else "일정이"
            sentence = f"{subject} {phrase} {when}{where}예정돼 있다."
        else:
            if event_phrase == "컴백":
                sentence = f"{subject}의 컴백이 확인됐다."
            elif event_phrase:
                sentence = f"{subject}의 {event_phrase} 소식이 확인됐다."
            else:
                sentence = f"{subject}의 행사 소식이 확인됐다."
    elif event_type in {"POLICY", "REGULATION"} and subject:
        role_sentence = _policy_role_sentence(subject, condition, policy_object, action)
        if role_sentence:
            sentence = role_sentence
            if uncertainty:
                sentence += f" {uncertainty}"
            return sentence.strip()
        detail = normalize_text(completion_evidence)
        normalized_title = normalize_text(title)
        if normalized_title and detail.startswith(normalized_title):
            detail = detail[len(normalized_title) :].strip(" ,:·-—")
        detail = _strip_news_byline(detail)
        structured_sentence = _structured_policy_sentence(title, completion_evidence)
        if structured_sentence and "MALFORMED_SUBJECT_BOUNDARY" in editorial_text_issues(completion_evidence):
            sentence = structured_sentence
            if uncertainty:
                sentence += f" {uncertainty}"
            return sentence.strip()
        if (
            len(detail) >= 20
            and not _TRUNCATION_RE.search(detail)
            and not any(marker in detail for marker in _GENERIC_SUMMARY_MARKERS)
            and summary_information_gain(title, detail)
        ):
            sentence = detail.rstrip(" .!?。！") + "."
            if uncertainty:
                sentence += f" {uncertainty}"
            return sentence.strip()
        policy_action = action if action in {"발표", "공개", "시행", "고시", "확정", "요구", "촉구", "줄여라"} else "정책 변화"
        if structured_sentence:
            sentence = structured_sentence
            if uncertainty:
                sentence += f" {uncertainty}"
            return sentence.strip()
        if policy_action in {"요구", "촉구", "줄여라"}:
            clean_title = _clean_headline(title)
            sentence = f"{clean_title}는 정책 요구로 제시됐다."
        elif policy_action in {"시행", "고시", "확정"} and date:
            if policy_action == "시행":
                sentence = f"{subject}{_particle(subject)} {date}부터 법 적용이 시작된다."
            else:
                sentence = f"{subject}{_particle(subject)} {date}부터 {policy_action}된다."
        elif policy_action in {"시행", "고시", "확정"}:
            sentence = f"{subject}{_particle(subject)} {policy_action} 절차가 시작됐다."
        else:
            sentence = f"{subject}의 {policy_action} 내용이 확인됐다."
    elif event_type == "PRODUCT_RELEASE" and subject:
        release_subject = subject or _clean_headline(title).split(",", 1)[0].strip()
        source_detail = normalize_text(completion_evidence)
        if (
            source_detail
            and not _TRUNCATION_RE.search(source_detail)
            and summary_information_gain(title, source_detail)
        ):
            sentence = _strip_news_byline(source_detail).rstrip(" .!?。！") + "."
            if uncertainty:
                sentence += f" {uncertainty}"
            return sentence.strip()
        listing = re.search(
            r"(?:오는\s*)?(\d{1,2}\s?일)\s*상장\s*예정인\s*([A-Za-z0-9가-힣·&+\- ]+?(?:ETF|펀드))",
            completion_evidence,
        )
        if listing:
            listing_date, listing_product = listing.groups()
            sentence = f"{listing_product.strip()}{_subject_particle(listing_product.strip())} {listing_date} 상장될 예정이다."
        elif "상장" in title and date:
            sentence = f"{release_subject}{_subject_particle(release_subject)} {date} 상장될 예정이다."
        elif date and not any(marker in title for marker in ("데뷔곡", "앨범", "음원", "싱글", "신곡", "발매")):
            sentence = f"{release_subject}{_subject_particle(release_subject)} {date} 출시된다."
        elif "일정" in completion_evidence and not date:
            sentence = f"{release_subject}의 출시 일정이 공개됐다."
        else:
            if "데뷔곡" in title:
                release_noun, release_verb, release_fact = "데뷔곡", "발매", "데뷔곡 발매"
            elif "앨범" in title:
                release_noun, release_verb, release_fact = "앨범", "발매", "앨범 발매"
            elif any(marker in title for marker in ("음원", "싱글", "신곡", "발매")):
                release_noun, release_verb, release_fact = "신곡", "발매", "신곡 발매"
            elif "도구" in title or "서비스" in title:
                release_noun, release_verb, release_fact = "도구·서비스", "출시", "도구·서비스 출시"
            else:
                release_noun, release_verb, release_fact = "제품", "출시", "출시"
            fact_number = next(
                (
                    value
                    for value in _meaningful_numbers(numbers, title)
                    if not _DATE_COUNTER_RE.fullmatch(value) and not _DATE_STAMP_RE.fullmatch(value)
                ),
                "",
            )
            if fact_number and not date:
                noun = "요금제" if "요금제" in title else release_noun
                base_subject = re.sub(r"\s+(?:신규\s*)?" + re.escape(noun) + r"$", "", release_subject).strip()
                base_subject = base_subject or release_subject
                sentence = (
                    f"{base_subject}{_subject_particle(base_subject)} "
                    f"{fact_number} {noun}를 새로 내놓았다."
                )
            elif date and release_verb == "발매":
                sentence = f"{release_subject}{_subject_particle(release_subject)} {date} {release_noun}을 {release_verb}한다."
            elif date and release_verb == "출시":
                sentence = f"{release_subject}{_subject_particle(release_subject)} {date} {release_noun}을 {release_verb}한다."
            else:
                sentence = f"{release_subject}의 {release_fact} 소식이 확인됐다."
    elif event_type == "AWARD_CHART" and subject:
        fact_map = _event_fact_map(event_facts)
        chart_number = fact_map.get("CHART_RANK", "") or next((value for value in numbers if value.endswith("위")), "")
        music_context = any(
            marker in title for marker in (
                "음악", "음원", "앨범", "가요", "아이돌", "가수", "차트", "빌보드",
                "Billboard", "billboard", "멜론", "노래",
            )
        )
        if chart_number and music_context:
            vote_count = fact_map.get("VOTE_COUNT", "")
            streak = fact_map.get("STREAK_WEEKS", "")
            if vote_count and vote_count not in title:
                sentence = f"{subject}{_particle(subject)} {vote_count}를 받아 음악 차트 {chart_number}에 올랐다."
            elif streak and re.search(r"[A-Za-z]$", subject):
                sentence = f"{subject}의 음악 차트 {chart_number} 기록이 {streak}째 이어졌다."
            elif streak and streak not in title:
                sentence = f"{subject}{_particle(subject)} {streak} 연속 음악 차트 {chart_number}를 기록했다."
            elif re.search(r"[A-Za-z]$", subject):
                sentence = f"음악 차트에서 {subject}의 순위는 {chart_number}였다."
            else:
                sentence = f"{subject}{_subject_particle(subject)} 음악 차트 {chart_number}에 올랐다."
        elif chart_number:
            sentence = f"{_clean_headline(title)}."
        else:
            sentence = f"{_clean_headline(title)}."
        if not summary_information_gain(title, sentence):
            supporting_fact = _award_supporting_fact(title, supporting_titles)
            if supporting_fact and chart_number and music_context:
                supporting_fact = _naturalize_release_onset(supporting_fact)
                connector = (
                    supporting_fact
                    if supporting_fact.endswith(("부터", "후", "당일"))
                    else f"{supporting_fact}{_instrumental_particle(supporting_fact)}"
                )
                sentence = f"{subject}{_particle(subject)} {connector} 음악 차트 {chart_number}에 올랐다."
    elif event_type.startswith("RECRUITMENT") and subject:
        fact_map = _event_fact_map(event_facts)
        ratio_value = fact_map.get("COMPETITION_RATIO", "")
        selected_value = fact_map.get("SELECTION_COUNT", "")
        applicant_value = fact_map.get("APPLICANT_COUNT", "")
        ratio_match = re.search(r"\d+(?:\.\d+)?\s?대\s?\d+", f"{title} {completion_evidence}")
        counts_match = re.search(
            r"([\d,]+명)\s*(?:이|가|을|를)?\s*(선발|모집).*?([\d,]+명)\s*(?:이|가|을|를)?\s*지원",
            completion_evidence,
        )
        if ratio_value and selected_value and applicant_value:
            recruitment_label = "" if subject.endswith(("공채", "채용", "시험")) else " 공채"
            sentence = (
                f"{subject}{recruitment_label}는 {selected_value} 선발에 {applicant_value} 지원해 "
                f"{ratio_value} 경쟁률을 기록했다."
            )
        elif counts_match and ratio_match:
            selected, selection_word, applicants = counts_match.groups()
            ratio = re.sub(r"\s+", "", ratio_match.group(0))
            sentence = f"{subject} {ratio} 경쟁률을 기록했고, {selected} {selection_word}에 {applicants} 지원했다."
        elif counts_match:
            selected, selection_word, applicants = counts_match.groups()
            sentence = f"{subject} 공채에서 {selected} {selection_word}에 {applicants} 지원했다."
        elif ratio_match:
            sentence = f"{subject} 공채 경쟁률은 {re.sub(r'\s+', '', ratio_match.group(0))}였다."
        else:
            sentence = ""
        if not sentence:
            sentence = f"{_clean_headline(title)}."
    elif event_type == "INDUSTRY_CHANGE" and subject:
        sentence = _industry_fact_summary(
            title,
            subject,
            action,
            completion_evidence,
            event_facts,
        )
    elif event_type == "ROSTER_PERSONNEL" and subject:
        if action == "선발":
            lineup = _lineup_detail(completion_evidence)
            if len(lineup) >= 2:
                detail = f"{lineup[0]}{_conjunction_particle(lineup[0])} {lineup[1]}"
                context = " ".join(part for part in (date, location) if part)
                context = f"{context} 경기의 " if context else "경기의 "
                sentence = f"{context}선발로 {detail}{_subject_particle(detail)} 예고됐다."
            else:
                sentence = ""
        else:
            sentence = ""
        if not sentence:
            clean_title = _clean_headline(title)
            if numbers and clean_title:
                sentence = f"{clean_title}."
            else:
                action_text = action or "선수단 변동"
                sentence = f"{subject}의 {action_text}{_subject_particle(action_text)} 확인됐다."
    elif event_type == "SPORTS_RESULT" and subject:
        detail = normalize_text(completion_evidence)
        if detail.startswith(normalize_text(title)):
            detail = detail[len(normalize_text(title)) :].strip(" ,:·-—")
        if detail and not _TRUNCATION_RE.search(detail) and not editorial_text_issues(detail) and len(detail) >= 12:
            sentence = detail.rstrip(" .!?") + "."
        else:
            result_facts = event_facts or sports_result_facts(f"{title} {completion_evidence}")
            result_map = _event_fact_map(result_facts)
            result_subject = _sports_result_subject(subject, result_facts, title)
            performance = [
                value
                for value in (result_map.get("HOME_RUN_COUNT", ""), result_map.get("RBI_COUNT", ""))
                if value
            ]
            if result_map.get("AWARD") and performance:
                period = result_map.get("PERIOD", "")
                period_label = f"{period} " if period else ""
                performance_text = (
                    f"{performance[0]}과 {performance[1]}"
                    if len(performance) == 2
                    else performance[0]
                )
                sentence = (
                    f"{result_subject}{_subject_particle(result_subject)} {period_label}월간 MVP로 선정됐다. "
                    f"{performance_text}을 기록했다."
                )
            else:
                score_match = re.search(r"\d+\s*[-대]\s*\d+", title)
                if score_match:
                    result_word = "승리" if "승리" in title else "패배" if "패배" in title else "경기 결과"
                    sentence = f"{result_subject}의 {result_word} 스코어는 {re.sub(r'\s+', '', score_match.group(0))}로 기록됐다."
                else:
                    sentence = ""
    elif event_type == "SPORTS_INTERRUPTION" and subject:
        evidence = f"{title} {completion_evidence}".casefold()
        league = "프로야구" if "프로야구" in evidence or "프로야구" in subject.casefold() else ("KBO" if "kbo" in evidence else subject)
        cause_label = {
            "HEAT": "폭염",
            "RAIN": "우천",
        }.get(cause, "") or next((marker for marker in ("폭염", "우천", "악천후", "기상") if marker in evidence), "")
        cause_phrase = f"{cause_label}{_instrumental_particle(cause_label)} " if cause_label else ""
        resume_date = (
            f"{date} "
            if date in {"어제", "오늘", "내일", "모레"}
            else f"{date}에 "
            if date
            else ""
        )
        if temporal_state == "RESUMING":
            sentence = f"{league} 경기가 {cause_phrase}중단된 뒤 {resume_date}재개될 예정이다."
        elif temporal_state == "RESUMED":
            sentence = f"{league} 경기가 {cause_phrase}중단된 뒤 {resume_date}재개됐다."
        elif temporal_state == "CANCELLED" or "취소" in evidence:
            sentence = f"{league} 경기가 폭염 영향으로 취소됐다."
        elif "휴식" in evidence:
            sentence = f"{league} 경기가 {cause_phrase}휴식기에 들어갔다."
        else:
            sentence = f"{league} 경기가 {cause_phrase}중단됐다."
    elif event_type == "MERCHANDISE" and subject:
        sentence = f"{subject} 관련 상품 소식이 보도됐다."
    elif event_type == "ANNOUNCEMENT":
        if "콘셉트 포토" in title and subject:
            sentence = f"{subject}가 데뷔 콘셉트 포토를 공개했다."
        elif action == "공개" and subject:
            sentence = f"{subject}의 공개 내용이 확인됐다."
        else:
            sentence = f"{subject or _clean_headline(title)} 발표가 확인됐다."
    else:
        if source_count > 1:
            sentence = "여러 매체가 같은 이슈를 전했지만, 공통으로 확인되는 세부 사실은 제한적이다."
        else:
            sentence = "단일 검색 결과만 확인되어 세부 내용은 추가 확인이 필요하다."
    if uncertainty:
        sentence += f" {uncertainty}"
    return _normalise_display_sentence(sentence.replace("...", "").replace("…", "").strip())


def clean_headline(value: str) -> str:
    """Return a safe display title without search-result formatting artifacts."""

    return _clean_headline(value)


def _evidence_summary(summary: str) -> str:
    """Expose a story-specific fact, never a repeated evidence macro."""

    return normalize_text(summary)


def synthesize_cluster(
    cluster: StoryCluster,
    *,
    topic_name: str,
    trend_metrics: tuple[TrendMetric, ...],
    event_type_override: str | None = None,
    event_signature_override: str | None = None,
    conflict_state_override: str | None = None,
    canonical_event_override: CanonicalEvent | None = None,
) -> tuple[str, str, str, tuple[str, ...], StoryFacts, Certainty]:
    canonical_event = canonical_event_override
    items = event_owned_items(cluster, canonical_event)
    if canonical_event is not None and canonical_event.evidence_owner_ids and not items:
        return (
            "",
            "",
            "",
            (),
            StoryFacts(
                event_type=canonical_event.event_type,
                canonical_event_id=canonical_event.canonical_event_id,
                conflict_state="UNRESOLVED_CONFLICT",
            ),
            Certainty.UNCERTAIN,
        )
    items = items or cluster.items
    headline_item = best_headline_item(items)
    title = effective_title(headline_item) or _clean_headline(headline_item.title)
    owned_headline_lead = (
        event_owned_lead(headline_item, canonical_event.event_type)
        if canonical_event is not None
        else effective_lead(headline_item)
    )
    owned_fact_lead = (
        owned_headline_lead
        if canonical_event is not None
        else _fact_lead(headline_item)
    )
    headline_evidence = " ".join(
        value for value in (effective_title(headline_item), owned_headline_lead) if value
    )
    fact_headline_evidence = " ".join(
        value for value in (effective_title(headline_item), owned_fact_lead) if value
    )
    title_evidence = " ".join(effective_title(item) for item in items if effective_title(item))
    repeated_numbers = _repeated_values(items, _numbers)
    repeated_dates = _repeated_values(items, _dates)
    repeated_times = _repeated_values(items, _times)
    repeated_locations = _repeated_values(items, _locations)
    numbers = _unique(list(_numbers(headline_evidence)) + list(repeated_numbers))
    display_numbers = _meaningful_numbers(numbers, title)
    metadata_dates = _unique(
        [
            date
            for item in items
            for date in _event_dates(
                event_owned_lead(item, canonical_event.event_type)
                if canonical_event is not None
                else safe_evidence_text(item.metadata_description)
            )
        ]
    )
    dates = _unique(
        list(_dates(effective_title(headline_item)))
        + list(_event_dates(owned_fact_lead))
        + list(repeated_dates)
        + list(metadata_dates)
    )
    times = _unique(list(_times(headline_evidence)) + list(repeated_times))
    locations = _unique(
        list(_locations(headline_evidence))
        + list(_locations(fact_headline_evidence))
        + list(repeated_locations)
    )
    # Classify the representative headline first. Descriptions may mention
    # generic words such as "정책" or "공개" while the headline carries the
    # actual subject (for example a market statistic). This keeps the
    # synthesis anchored to the strongest visible evidence.
    title_event_type = _event_type(title, _numbers(title))
    lead_event_type = _event_type(owned_headline_lead, _numbers(owned_headline_lead))
    inferred_event_type = title_event_type if title_event_type != "OTHER" else (
        lead_event_type if lead_event_type != "OTHER" else _event_type(title_evidence, numbers)
    )
    # Production selection already has the editorial event gate. Reuse that
    # decision for synthesis so the audit and the emitted StoryFacts cannot
    # diverge when two deterministic classifiers have different precedence.
    event_type = (
        canonical_event.event_type
        if canonical_event is not None
        else event_type_override or inferred_event_type
    )
    resolved_event_facts = (
        canonical_event.facts
        if canonical_event is not None
        else industry_change_facts(f"{title} {_fact_lead(headline_item)}")
        if event_type == "INDUSTRY_CHANGE"
        else ()
    )
    market_observations = (
        canonical_event.observations
        if canonical_event is not None and canonical_event.observations
        else earnings_observations(title)
        if event_type == "EARNINGS"
        else metric_observations(title)
    )
    market_observation = next(iter(market_observations), None)
    # Do not borrow an action from another headline in a broad cluster. A
    # secondary article may describe a different event while sharing the
    # same entity or theme. Market stories need a market outcome as their
    # action; an explanatory phrase such as ``금리 인상`` is not that
    # outcome.
    if canonical_event is not None and canonical_event.action:
        action = canonical_event.action
    elif event_type in {"STATISTIC", "MARKET", "MARKET_MOVE"}:
        action = (
            next((observation.direction for observation in market_observations if observation.direction), "")
            or market_direction(title)
        )
    elif event_type.startswith("RECRUITMENT"):
        # Recruitment competition/result stories frequently carry a lead
        # verb such as ``공개``. The taxonomy already expresses the event;
        # do not promote that incidental verb into StoryFacts.action.
        action = ""
    else:
        action = _action(title) or _action(owned_headline_lead)
    if event_type == "SPORTS_INTERRUPTION":
        interruption_evidence = headline_evidence.casefold()
        subject = (
            canonical_event.subject
            if canonical_event is not None and canonical_event.subject
            else "프로야구" if any(term in interruption_evidence for term in ("프로야구", "kbo", "야구")) else "KBO"
        )
        if canonical_event is not None and canonical_event.action:
            action = canonical_event.action
        elif "재개" in interruption_evidence:
            action = "재개"
        elif any(term in interruption_evidence for term in ("중단", "멈춘", "취소", "휴식", "방학")):
            action = "중단"
    else:
        earnings_observation = next(iter(earnings_observations(title)), None) if event_type == "EARNINGS" else None
        if earnings_observation is not None:
            # Reuse the bound earnings observation so a period such as
            # ``2026년`` cannot be mistaken for part of the company name.
            subject = earnings_observation.instrument
            display_numbers = _unique(
                [value for value in (earnings_observation.period, earnings_observation.value) if value]
            )
        else:
            # Use all title numbers while deriving the noun subject. Date
            # counters may be unsafe as display metrics, but they still mark
            # where the subject ends (반도체특별법 11일 시행).
            subject = _domain_subject(title, _subject(title, action, numbers), event_type)
        if event_type.startswith("RECRUITMENT"):
            subject = _recruitment_subject(title, subject)
        if event_type == "AWARD_CHART":
            subject = _award_subject(
                title,
                subject,
                titles=tuple(effective_title(item) for item in items if effective_title(item)),
            )
        if canonical_event is not None and canonical_event.subject:
            subject = canonical_event.subject
    if event_type in {"STATISTIC", "MARKET", "MARKET_MOVE"}:
        if market_observations:
            # Keep each metric bound to its own instrument and direction.
            display_numbers = tuple(observation.value for observation in market_observations[:3])
        else:
            # Numbers found only in a market lead may be a time, comparison
            # context, or another entity's value. Without a bound observation
            # they are not all safe display facts. Retain only values with a
            # meaningful market unit; bare publication-time counters are not
            # facts about the market move.
            display_numbers = tuple(
                value
                for value in _meaningful_numbers(numbers, title)
                if not _TIME_COUNTER_RE.fullmatch(value)
            )
        if market_observation is not None:
            change = market_observation.direction or action
            if market_observation.instrument:
                subject = market_observation.instrument
        else:
            change = (
                _tail_after_first_number(title, display_numbers)
                or (_change_phrases(title)[:1] or ("",))[0]
                or action
            )
    else:
        change = _tail_after_first_number(title, display_numbers) or (_change_phrases(title)[:1] or ("",))[0]
    if resolved_event_facts:
        canonical_values = tuple(_event_fact_value(fact) for fact in resolved_event_facts)
        if event_type.startswith("RECRUITMENT") or event_type in {"AWARD_CHART", "SPORTS_RESULT", "INDUSTRY_CHANGE"}:
            display_numbers = _unique(list(canonical_values) + list(display_numbers))
        if canonical_event is not None and canonical_event.direction:
            change = canonical_event.direction
    repeated = _repeated_values(items, _numbers)
    if not repeated:
        repeated = _repeated_values(items, _dates)
    if not repeated:
        repeated = _repeated_values(items, _locations)
    if not repeated and len(items) > 1:
        repeated = _repeated_terms(items)
    representative_values = _unique(list(_numbers(title)) + list(_dates(title)) + list(_locations(title)))
    unique_facts = tuple(value for value in representative_values if value not in repeated)
    uncertainty = ""
    numeric_values = repeated_numbers
    # Keep all headline numbers for conflict detection, while only repeated
    # or representative numbers are eligible for display facts.
    all_numeric = _unique(list(_numbers(title_evidence)))
    if len(numeric_values) == 0 and len(all_numeric) > 1 and event_type in {"STATISTIC", "MARKET", "EARNINGS"}:
        units = {re.sub(r"[\d,.\s]", "", value) for value in all_numeric}
        if len(units) == 1:
            uncertainty = "보도마다 수치가 달라 추가 확인이 필요하다."
    official = _official_source(items)
    source_count = len(
        {
            canonical_publisher(
                str(getattr(item, "publisher", "")),
                str(getattr(item, "source_domain", "")),
            )
            for item in items
            if getattr(item, "publisher", "") or getattr(item, "source_domain", "")
        }
    )
    trend_state = _trend_state(cluster.topic_id, trend_metrics)
    canonical_date, date_conflict = canonical_event_date(
        title,
        owned_fact_lead,
        event_type=event_type,
        state=canonical_event.temporal_state if canonical_event is not None else "",
    )
    if canonical_event is not None:
        date = (
            canonical_event.date
            if event_type == "SPORTS_INTERRUPTION"
            else canonical_event.date or canonical_date or (dates[0] if dates else "")
        )
        location = canonical_event.location or (locations[0] if locations else "")
        date_conflict = date_conflict or canonical_event.conflict_state == "DATE_CONFLICT"
    else:
        date = canonical_date or (dates[0] if dates else "")
        location = locations[0] if locations else ""
    next_signal = _next_signal(event_type, headline_evidence, date, action)
    conflict_state = conflict_state_override or "NO_CONFLICT"
    if date_conflict:
        conflict_state = "DATE_CONFLICT"
    temporal_state = canonical_event.temporal_state if canonical_event is not None else ""
    if event_type == "SPORTS_INTERRUPTION" and not temporal_state:
        combined = f"{title} {fact_headline_evidence}".casefold()
        if "재개" in combined:
            future_resume = any(
                marker in combined
                for marker in (
                    "예정",
                    "재개한다",
                    "재개할",
                    "재개될",
                    "다시 시작한다",
                    "다시 시작할",
                    "다시 문을 연다",
                    "문을 연다",
                    "내일",
                    "모레",
                    "오는",
                )
            )
            temporal_state = "RESUMING" if future_resume else "RESUMED"
        elif "취소" in combined:
            temporal_state = "CANCELLED"
        elif "중단" in combined or "멈춘" in combined:
            temporal_state = "INTERRUPTED"
    facts = StoryFacts(
        subject=subject,
        action=action,
        object=canonical_event.object if canonical_event is not None else "",
        cause=canonical_event.cause if canonical_event is not None else "",
        condition=canonical_event.condition if canonical_event is not None else "",
        event_type=event_type,
        date=date,
        time=times[0] if times else "",
        location=location,
        key_numbers=display_numbers[:3],
        key_changes=_unique(
            (
                [action]
                if event_type in {"STATISTIC", "MARKET", "MARKET_MOVE", "EARNINGS"} and action
                else [change]
                if len(market_observations) <= 1 and change
                else [
                    f"{observation.instrument} {observation.direction}"
                    for observation in market_observations[:3]
                    if observation.direction
                ]
            )
            + (
                []
                if market_observation is not None
                else list(_change_phrases(" ".join(_clean_headline(getattr(item, "title", "")) for item in items)))
            )
        )[:3],
        official_source=official,
        source_count=source_count,
        source_diversity=source_count,
        repeated_facts=repeated[:3],
        unique_facts=unique_facts[:3],
        trend_state=trend_state,
        next_known_event=next_signal,
        uncertainty=uncertainty,
        event_signature=event_signature_override
        or (canonical_event.event_signature if canonical_event is not None else "")
        or canonical_event_signature(event_type, title, lead=_fact_lead(headline_item), subject=subject, action=action),
        conflict_state=conflict_state,
        temporal_state=temporal_state,
        canonical_event_id=(
            canonical_event.canonical_event_id
            if canonical_event is not None
            else event_signature_override or ""
        ),
        temporal_facts=canonical_event.temporal_facts if canonical_event is not None else (),
        fixture_id=canonical_event.fixture_id if canonical_event is not None else "",
        event_owner_ids=(
            canonical_event.evidence_owner_ids if canonical_event is not None else ()
        ),
        fact_evidence_ids=(
            canonical_event.evidence_owner_ids
            if canonical_event is not None
            else ()
        ),
        representative_evidence_id=(
            canonical_event.representative_evidence_id if canonical_event is not None else ""
        ),
        primary_focus_terms=(
            canonical_event.primary_focus_terms
            if canonical_event is not None
            else primary_event_focus_terms(event_type, title, subject, resolved_event_facts)
        ),
    )
    headline_source = effective_title(headline_item)
    if not headline_item.metadata_title or not safe_evidence_text(headline_item.metadata_title):
        headline_source = headline_item.title
    headline = _headline(
        headline_source,
        event_type,
        subject,
        display_numbers,
        change,
        date=date,
        action=action,
        temporal_state=temporal_state,
        observations=market_observations,
        event_facts=resolved_event_facts,
    )
    completion_evidence = (
        _best_event_completion_evidence(
            items,
            canonical_event,
            title,
            facts.primary_focus_terms,
        )
        if canonical_event is not None
        else fact_headline_evidence
    )
    relation_completion_evidence = (
        completion_evidence or owned_fact_lead
        if _event_relation_fact(resolved_event_facts) is not None
        else completion_evidence
    )
    summary = _summary(
        title,
        event_type,
        subject,
        action,
        date,
        location,
        display_numbers,
        change,
        source_count,
        uncertainty,
        relation_completion_evidence,
        market_observation=market_observation,
        market_observations=market_observations,
        temporal_state=temporal_state,
        supporting_titles=tuple(effective_title(item) for item in items if effective_title(item)),
        event_facts=resolved_event_facts,
        cause=canonical_event.cause if canonical_event is not None else "",
        condition=canonical_event.condition if canonical_event is not None else "",
        policy_object=canonical_event.object if canonical_event is not None else "",
    )
    if (
        event_type in {"STATISTIC", "MARKET", "MARKET_MOVE"}
        and market_observation is not None
        and market_observation.instrument
        and market_observation.value
        and market_observation.direction
        and len(market_observations) == 1
        and summary
        and not summary_information_gain(headline, summary)
    ):
        # Keep the complete value in the summary and use a compact factual
        # headline.  This preserves the metric tuple without requiring an
        # unrelated lead solely to manufacture headline/summary difference.
        headline = f"{market_observation.instrument} {market_observation.direction}"
    if canonical_event is not None and not summary_preserves_primary_focus(
        summary,
        facts.primary_focus_terms,
    ):
        summary = ""
    evidence = _evidence_summary(summary)
    watch = (next_signal,) if next_signal else ()
    corroborated, _ = evidence_corroborated(items)
    if corroborated or official:
        certainty = Certainty.CONFIRMED
    elif event_type != "OTHER" and (numbers or dates or action):
        certainty = Certainty.SUPPORTED_SINGLE_SOURCE
    else:
        certainty = Certainty.UNCERTAIN
    return headline, summary, evidence, watch, facts, certainty
