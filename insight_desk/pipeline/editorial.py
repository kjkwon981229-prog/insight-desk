from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from ..domain.models import EvidenceType, NewsItem, Topic
from .clustering import StoryCluster, market_primary_text
from .normalization import normalize_text

_TRUNCATION_RE = re.compile(r"\.{2,}|…")
_TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣·]{2,}")
_NUMBER_RE = re.compile(r"(?<![A-Za-z가-힣])\d[\d,.]*(?:\s?(?:조원|억원|만원|천만|만\s?달러|억\s?달러|달러|개월|주년|원|%|퍼센트|명|건|배|개|곳|일|월|년|분|시|위|점|대|선|km))?")
_DATE_RE = re.compile(r"(?:20\d{2}\s?년\s?)?\d{1,2}\s?(?:월\s?\d{1,2}\s?일|일)")
_GENERIC_HEADLINE_RE = re.compile(r"^(?:.+\s)?관련\s*(?:보도|소식|기사)$")
_GENERIC_SUMMARY_MARKERS = (
    "단일 검색 결과만 확인되어",
    "공통으로 확인되는 세부 사실은 제한적이다",
)
_EVENT_PATTERNS: tuple[tuple[str, tuple[str, ...], float], ...] = (
    ("REGULATION", ("규제", "법안", "고시", "허용", "금지", "시행", "제도 개편"), 84.0),
    ("POLICY", ("정책 발표", "정책 결정", "정책 시행", "정책 개편", "대책 발표", "대책 시행", "기준금리", "공고", "요구", "촉구", "줄여라"), 76.0),
    ("EARNINGS", ("실적", "매출", "영업이익", "순이익", "가이던스", "공시"), 78.0),
    ("AWARD_CHART", ("1위", "차트", "관왕", "수상"), 74.0),
    ("PRODUCT_RELEASE", ("출시", "발매", "선공개", "음원", "신곡", "싱글", "데뷔곡", "신규상장", "상장", "예약판매", "판매 개시", "사양 확정"), 68.0),
    ("INDUSTRY_CHANGE", ("투자 유치", "유치", "인수", "전략", "데이터센터", "서비스 전환", "할당", "계약", "생산"), 66.0),
    ("SPORTS_INTERRUPTION", ("폭염", "중단", "멈춘"), 70.0),
    ("SPORTS_RESULT", ("경기 결과", "승리했다", "패배했다", "승리 확정", "우승", "승률", "연승", "연패", "홈런", "순위", "기록"), 72.0),
    ("ROSTER_PERSONNEL", ("선발", "엔트리", "부상", "트레이드", "등록", "말소"), 74.0),
    ("SCHEDULED_EVENT", ("일정", "예정", "개최", "시구", "공연", "콘서트", "컴백", "월드투어"), 64.0),
    ("ANNOUNCEMENT", ("발표", "공지", "공개"), 62.0),
    ("STATISTIC", ("통계", "지표", "평균", "변동폭", "최고", "최대", "최저", "상승", "하락", "증가", "감소"), 68.0),
    ("MARKET_MOVE", ("환율", "코스피", "증시", "주가", "금리", "변동성", "급등", "급락"), 64.0),
    ("MERCHANDISE", ("굿즈", "유니폼", "패션", "상품", "기념품", "리본핀", "콜라보"), 18.0),
)
_GENERIC_TERMS = {
    "관련", "보도", "소식", "기사", "변화", "주요", "뉴스", "확인", "공개", "발표", "포토",
    "올해", "이번", "지난", "전망", "이슈",
}
_LOW_VALUE_EVENT_TYPES = {
    "LOW_VALUE_APPEARANCE",
    "ROUTINE_SCHEDULE",
    "ROUTINE_MARKET_QUOTE",
}
_ROUTINE_SCHEDULE_MARKERS = ("주요일정", "일정표", "금주 일정", "이번 주 일정", "이번주 일정")
_ROUTINE_MARKET_QUALIFIERS = (
    "변동성", "변동폭", "금융위기", "사상", "최대", "최고", "최저", "급등", "급락",
    "개입", "정책", "기준금리", "결정",
)
_COMPLETED_ENTERTAINMENT_MARKERS = (
    "성료",
    "대성황",
    "성황",
    "마쳤다",
    "진행했다",
    "진행됐다",
    "열렸다",
)
_ENTERTAINMENT_EVENT_MARKERS = (
    "컴백",
    "콘서트",
    "공연",
    "앨범",
    "음원",
    "발매",
    "가수",
    "그룹",
)
_HEADLINE_ACTION_MARKERS = (
    "시구", "개최", "공연", "콘서트", "출시", "발매", "발표", "공개", "시행",
    "선발", "중단", "멈춘", "재개", "취소", "경기", "매각", "인수", "인상", "인하",
    "규제", "유치", "투자", "트레이드", "부상", "승리", "패배", "컴백", "전략",
    "할당", "계약",
)


def _fold(value: str) -> str:
    return unicodedata.normalize("NFKC", normalize_text(value)).casefold()


def _compact(value: str) -> str:
    return re.sub(r"[^a-z0-9가-힣]", "", _fold(value))


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(token for token in _TOKEN_RE.findall(_fold(value)) if len(token) >= 2))


def _contains(text: str, phrase: str) -> bool:
    compact_text = _compact(text)
    compact_phrase = _compact(phrase)
    return bool(compact_phrase and compact_phrase in compact_text)


def _contains_intent_term(text: str, phrase: str) -> bool:
    """Match intent vocabulary without treating company compounds as teams.

    Some configured intent terms are short Korean names that also occur as
    prefixes in unrelated organizations.  ``한화`` must match the baseball
    team when it is a standalone name (including ordinary particles), but not
    ``한화에어로스페이스`` in an economy article.  Other vocabulary keeps the
    existing substring behavior so broad configured anchors retain recall.
    """

    if _compact(phrase) == "한화":
        folded = _fold(text)
        return bool(
            re.search(
                r"(?<![가-힣A-Za-z0-9])한화"
                r"(?:은|는|이|가|을|를|의|도|만|와|과|에|에서|로|으로)?"
                r"(?![가-힣A-Za-z0-9])",
                folded,
            )
        )
    return _contains(text, phrase)


def safe_evidence_text(value: str) -> str:
    text = normalize_text(value)
    return "" if _TRUNCATION_RE.search(text) else text


def effective_title(item: NewsItem) -> str:
    metadata_title = safe_evidence_text(item.metadata_title)
    if metadata_title:
        return metadata_title
    search_title = safe_evidence_text(item.title)
    if search_title:
        return search_title
    raw = normalize_text(item.metadata_title or item.title)
    marker = _TRUNCATION_RE.search(raw)
    return raw[: marker.start()].strip(" ,·-—") if marker else raw


def effective_lead(item: NewsItem) -> str:
    metadata_description = safe_evidence_text(item.metadata_description)
    return metadata_description or safe_evidence_text(item.summary)


def effective_text(item: NewsItem) -> str:
    return " ".join(part for part in (effective_title(item), effective_lead(item)) if part)


def best_headline_item(items: tuple[NewsItem, ...]) -> NewsItem:
    """Choose the concrete source headline used for display and signatures."""

    def quality(item: NewsItem) -> tuple[float, float, str]:
        title = effective_title(item)
        compact = re.sub(r"\s+", "", title)
        score = min(32.0, len(compact))
        if item.metadata_title and safe_evidence_text(item.metadata_title):
            score += 18.0
        if any(
            marker in title
            for marker in (*_HEADLINE_ACTION_MARKERS, "차트", "수상", "변동폭", "최대", "최고", "상승", "하락", "출발")
        ):
            score += 16.0
        if re.search(r"^(?:내일의|오늘의)\s*(?:경기|일정)", title):
            score -= 20.0
        if title.startswith(("관련 보도", "관련 소식", "관련 기사")):
            score -= 30.0
        if _TRUNCATION_RE.search(item.title):
            score -= 12.0
        heat_sports = (
            any(term in title for term in ("폭염", "열파"))
            and any(term in title for term in ("KBO", "프로야구", "야구"))
        )
        if heat_sports:
            score += 24.0
            if any(term in title for term in ("중단", "멈춘", "취소")):
                score += 12.0
            if any(term in title for term in ("→", "리셋", "체력 충전")):
                score -= 10.0
        return score, item.score, title

    return max(items, key=quality)


def topic_anchor_terms(topic: Topic) -> tuple[str, ...]:
    """Return configured intent vocabulary plus a narrow test/config fallback."""

    values = list(topic.intent_anchors)
    values.extend(_TOKEN_RE.findall(topic.name))
    values.extend(_TOKEN_RE.findall(topic.id.replace("_", " ")))
    values.extend(topic.all_news_queries)
    return tuple(dict.fromkeys(value for value in values if value.strip()))


@dataclass(frozen=True)
class RelevanceAssessment:
    score: float
    passed: bool
    direct_title_match: bool
    lead_match: bool
    background_only: bool
    negative_match: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class EventAssessment:
    event_type: str
    significance: float
    concrete_fact_count: int
    passed: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceAssessment:
    strength: float
    publisher_diversity: int
    official: bool
    metadata_complete: bool
    passed: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class EditorialAssessment:
    relevance: RelevanceAssessment
    event: EventAssessment
    evidence: EvidenceAssessment
    completeness: float
    novelty: str
    event_signature: str
    qualified: bool
    final_score: float
    reasons: tuple[str, ...]


def assess_relevance(cluster: StoryCluster, topic: Topic) -> RelevanceAssessment:
    best: RelevanceAssessment | None = None
    anchors = topic_anchor_terms(topic)
    for item in cluster.items:
        title = effective_title(item)
        lead = effective_lead(item)
        raw_body = safe_evidence_text(item.summary)
        query = item.query
        query_tokens = _tokens(query)
        title_query = _contains(title, query)
        lead_query = _contains(lead, query)
        body_query = _contains(raw_body, query)
        title_token_hits = sum(1 for token in query_tokens if _contains(title, token))
        lead_token_hits = sum(1 for token in query_tokens if _contains(lead, token))
        anchor_title = any(_contains_intent_term(title, anchor) for anchor in anchors)
        core_anchor_title = any(_contains_intent_term(title, anchor) for anchor in topic.intent_anchors)
        anchor_lead = any(_contains_intent_term(lead, anchor) for anchor in anchors)
        query_title_match = bool(title_query or title_token_hits)
        query_supporting_match = bool(lead_query or lead_token_hits or body_query)
        required_match = not topic.required_intent_terms or any(
            _contains_intent_term(f"{title} {lead}", term) for term in topic.required_intent_terms
        )
        negative_title = any(_contains(title, term) for term in topic.negative_context)
        negative_lead = any(_contains(lead, term) for term in topic.negative_context)
        negative_body = any(_contains(raw_body, term) for term in topic.negative_context)

        score = 0.0
        reasons: list[str] = []
        if title_query:
            score += 58.0
            reasons.append("EXACT_QUERY_IN_TITLE")
        elif title_token_hits:
            score += 42.0 + min(10.0, title_token_hits * 4.0)
            reasons.append("QUERY_TOKEN_IN_TITLE")
        elif lead_query:
            score += 32.0
            reasons.append("EXACT_QUERY_IN_LEAD")
        elif lead_token_hits:
            score += 24.0
            reasons.append("QUERY_TOKEN_IN_LEAD")
        elif body_query or any(_contains(raw_body, token) for token in query_tokens):
            score += 8.0
            reasons.append("QUERY_ONLY_IN_SNIPPET")

        if anchor_title:
            score += 42.0
            reasons.append("CORE_ENTITY_IN_TITLE")
        elif anchor_lead:
            score += 14.0
            reasons.append("CORE_ENTITY_IN_LEAD")
        if negative_title:
            score -= 30.0
            reasons.append("NEGATIVE_CONTEXT_IN_TITLE")
        elif negative_lead:
            score -= 22.0
            reasons.append("NEGATIVE_CONTEXT_IN_LEAD")
        elif negative_body:
            score -= 14.0
            reasons.append("NEGATIVE_CONTEXT_IN_SNIPPET")

        background_only = bool(
            (body_query or any(_contains(raw_body, token) for token in query_tokens))
            and not (title_query or title_token_hits or lead_query or lead_token_hits or anchor_title)
        )
        if background_only:
            score -= 28.0
            reasons.append("BACKGROUND_ONLY_MENTION")
        # A named query found only in the supporting snippet is not enough
        # when the headline is about a broad topic anchor.  This blocks, for
        # example, a Claude search result whose title is only about a generic
        # AI cost-management tool.  Broad topic queries still match through
        # their own title token.
        supporting_only_mismatch = bool(
            not query_title_match
            and core_anchor_title
            and not any(_compact(query) == _compact(anchor) for anchor in topic.intent_anchors)
        )
        if supporting_only_mismatch:
            score -= 35.0
            reasons.append("QUERY_NOT_IN_TITLE")
        if not required_match:
            score -= 45.0
            reasons.append("REQUIRED_INTENT_MISSING")
        if not title_query and not title_token_hits and not anchor_title and not (lead_query or lead_token_hits or anchor_lead):
            score -= 18.0
            reasons.append("NO_TITLE_OR_LEAD_INTENT")

        assessment = RelevanceAssessment(
            score=round(max(0.0, min(100.0, score)), 3),
            passed=(
                score >= 40.0
                and bool(query_title_match or (anchor_title and not supporting_only_mismatch))
                and not background_only
                and not (negative_title or negative_lead)
                and not supporting_only_mismatch
                and required_match
            ),
            direct_title_match=bool(query_title_match or (anchor_title and not supporting_only_mismatch)),
            lead_match=bool(lead_query or lead_token_hits or anchor_lead),
            background_only=background_only,
            negative_match=bool(negative_title or negative_lead or negative_body),
            reasons=tuple(dict.fromkeys(reasons)),
        )
        if best is None or assessment.score > best.score:
            best = assessment
    return best or RelevanceAssessment(0.0, False, False, False, True, False, ("NO_EVIDENCE",))


def _event_terms_for(topic: Topic) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*topic.event_terms, *(term for _, terms, _ in _EVENT_PATTERNS for term in terms))))


def _is_routine_schedule(title_text: str) -> bool:
    compact = _compact(title_text)
    return any(_compact(marker) in compact for marker in _ROUTINE_SCHEDULE_MARKERS) or (
        _contains(title_text, "금주") and _contains(title_text, "일정")
    )


def _is_ceremonial_appearance(title_text: str) -> bool:
    # A first-pitch/first-bat announcement is an entertainment appearance,
    # not a baseball result, roster change, or meaningful game event.
    return any(_contains(title_text, marker) for marker in ("시구", "시타")) and not any(
        _contains(title_text, marker)
        for marker in ("경기 결과", "승리", "패배", "홈런", "순위", "선발", "엔트리", "부상", "트레이드")
    )


def _is_low_value_fan_event(title_text: str) -> bool:
    """Reject fan-invite/thank-you coverage that is not a core music event."""

    fan_context = any(_contains(title_text, marker) for marker in ("팬", "답례품", "기념품", "굿즈"))
    event_context = any(_contains(title_text, marker) for marker in ("행사", "초대", "부르더니", "선물"))
    substantive_event = any(
        _contains(title_text, marker)
        for marker in ("발매", "출시", "컴백", "앨범", "음원", "차트", "콘서트", "공연", "수상")
    )
    return fan_context and event_context and not substantive_event


def _is_low_value_kpop_institutional_event(title_text: str, topic: Topic) -> bool:
    """Reject institutional K-POP mentions without a music subject/action."""

    topic_key = _compact(f"{topic.id} {topic.name}")
    if "kpop" not in topic_key and "케이팝" not in topic_key:
        return False
    institutional_context = any(
        _contains(title_text, marker)
        for marker in ("교육청", "학교", "청소년", "국제교류", "말하기대회", "축하공연")
    )
    music_subject_or_event = any(
        _contains(title_text, marker)
        for marker in (
            "가수", "그룹", "아티스트", "기획사", "앨범", "음원", "차트", "컴백", "콘서트",
            "월드투어", "팬미팅", "뮤직비디오", "발매", "신곡", "데뷔", "빌보드", "음악방송",
            "수상", "계약",
        )
    )
    return institutional_context and not music_subject_or_event


def _is_routine_market_quote(title_text: str) -> bool:
    lowered = title_text.casefold()
    return any(marker in lowered for marker in ("ndf", "선물환")) and not any(
        _contains(title_text, marker) for marker in _ROUTINE_MARKET_QUALIFIERS
    )


def _is_completed_entertainment_event(title_text: str) -> bool:
    return (
        any(_contains(title_text, marker) for marker in _COMPLETED_ENTERTAINMENT_MARKERS)
        and any(_contains(title_text, marker) for marker in _ENTERTAINMENT_EVENT_MARKERS)
    )


def assess_event(cluster: StoryCluster, topic: Topic) -> EventAssessment:
    text = " ".join(effective_text(item) for item in cluster.items)
    # Synthesis and the public headline use the same best source headline.
    # Do not let a secondary cluster member's release word change the audited
    # event type of a primary announcement (or vice versa).
    title_text = effective_title(best_headline_item(cluster.items))
    event_type = "OTHER"
    significance = 0.0
    matched_terms: list[str] = []
    def standalone(term: str) -> bool:
        if " " in term:
            return _contains(text, term)
        return bool(re.search(rf"(?<![가-힣A-Za-z0-9]){re.escape(term)}(?![가-힣A-Za-z0-9])", text, re.IGNORECASE))

    sports_context = any(
        standalone(term)
        for term in ("야구", "KBO", "프로야구", "구단", "선수", "홈런", "엔트리", "선발", "트레이드", "경기 결과")
    )
    recruitment_context = (
        any(_contains(text, term) for term in ("공채", "채용", "공무원", "시험", "원서접수", "합격자"))
        and any(_contains(text, term) for term in ("선발", "지원", "경쟁률", "합격자"))
    )
    def detect_event(source: str) -> tuple[str, float, list[str]]:
        detected_type = "OTHER"
        detected_value = 0.0
        detected_terms: list[str] = []
        for candidate_type, patterns, value in _EVENT_PATTERNS:
            if candidate_type in {"SPORTS_INTERRUPTION", "SPORTS_RESULT"} and not sports_context:
                continue
            if candidate_type == "ROSTER_PERSONNEL" and not (sports_context or recruitment_context):
                continue
            hits = [pattern for pattern in patterns if _contains(source, pattern)]
            if hits and value > detected_value:
                detected_type = candidate_type
                detected_value = value
                detected_terms = hits
        return detected_type, detected_value, detected_terms

    heat_interruption = (
        sports_context
        and any(_contains(text, term) for term in ("폭염", "열파"))
        and any(_contains(text, term) for term in ("중단", "멈춘", "휴식", "재개", "취소"))
    )

    # The title is the strongest intent/event evidence.  Only fall back to
    # the combined lead text when the title contains no recognizable event;
    # this prevents a secondary sentence (for example an album mention in a
    # sports article) from changing the story's event type.
    if heat_interruption:
        event_type, significance, matched_terms = "SPORTS_INTERRUPTION", 70.0, ["폭염"]
    elif _is_low_value_fan_event(title_text) or _is_low_value_kpop_institutional_event(title_text, topic):
        event_type, significance, matched_terms = "LOW_VALUE_APPEARANCE", 20.0, ["LOW_VALUE_APPEARANCE"]
    elif _is_completed_entertainment_event(title_text):
        # ``컴백`` and ``공연`` are also used for future schedules. A completed
        # activity must not be recorded as a scheduled event when synthesis
        # already classifies the same evidence as an entertainment event.
        event_type, significance, matched_terms = "ENTERTAINMENT_EVENT", 64.0, ["ENTERTAINMENT_EVENT"]
    else:
        event_type, significance, matched_terms = detect_event(title_text)
        if event_type == "OTHER":
            event_type, significance, matched_terms = detect_event(text)
    if event_type == "SCHEDULED_EVENT" and any(
        _contains(text, term) for term in ("블루카펫", "행사 참석", "행사 일정에 참석", "포토")
    ) and not any(_contains(text, term) for term in ("공연", "콘서트", "컴백", "앨범", "경기 결과", "시구")):
        event_type = "LOW_VALUE_APPEARANCE"
        significance = 20.0
        matched_terms = ["LOW_VALUE_APPEARANCE"]
    if event_type == "SCHEDULED_EVENT" and _is_routine_schedule(title_text):
        event_type = "ROUTINE_SCHEDULE"
        significance = 18.0
        matched_terms = ["ROUTINE_SCHEDULE"]
    elif event_type == "SCHEDULED_EVENT" and _is_ceremonial_appearance(title_text):
        event_type = "LOW_VALUE_APPEARANCE"
        significance = 18.0
        matched_terms = ["LOW_VALUE_APPEARANCE"]
    elif event_type in {"STATISTIC", "MARKET_MOVE", "MARKET"} and _is_routine_market_quote(title_text):
        event_type = "ROUTINE_MARKET_QUOTE"
        significance = 22.0
        matched_terms = ["ROUTINE_MARKET_QUOTE"]
    if event_type == "SCHEDULED_EVENT":
        # ``주요일정`` or ``금주 일정`` alone is a calendar label, not a
        # concrete event. Keep genuine dated events and public recruitment
        # schedules, but reject a single thin search result that cannot
        # produce a factual briefing sentence.
        has_scheduled_signal = bool(_DATE_RE.search(text)) or any(
            _contains(text, term)
            for term in (
                "예정", "개최", "시구", "공연", "콘서트", "컴백", "월드투어",
                "시험 일정", "원서접수", "합격자", "공고",
            )
        )
        if not has_scheduled_signal:
            event_type = "OTHER"
            significance = 0.0
            matched_terms = []
    numbers = tuple(dict.fromkeys(_NUMBER_RE.findall(text)))
    dates = tuple(dict.fromkeys(_DATE_RE.findall(text)))
    event_terms = _event_terms_for(topic)
    topic_terms = topic_anchor_terms(topic)
    title_subject = any(_contains(title_text, term) for term in topic_terms)
    action_signal_terms = (
        "발표", "공개", "출시", "발매", "유치", "투자", "인수", "규제", "시행", "고시", "요구", "촉구", "줄여라",
        "상승", "하락", "증가", "감소", "변동", "급등", "급락", "통계", "지표", "실적",
        "경기 결과", "승리", "패배", "중단", "멈춘", "컴백", "공연", "콘서트", "트레이드", "부상",
        "차트", "관왕", "수상", "순위", "일정", "예정", "시구", "선발", "엔트리",
    )
    action = bool(any(_contains(title_text, term) or _contains(text, term) for term in action_signal_terms))
    concrete = int(bool(title_subject)) + int(action) + int(bool(numbers or dates))
    if event_type == "MERCHANDISE":
        significance = min(significance, 18.0)
    if event_type in _LOW_VALUE_EVENT_TYPES:
        reasons = (event_type, "LOW_VALUE_EVENT")
    elif event_type == "OTHER":
        reasons = ("NO_CONCRETE_EVENT",)
    else:
        reasons = (event_type, "CONCRETE_EVENT" if concrete >= 2 else "WEAK_EVENT_STRUCTURE")
    metric_signal = True
    if event_type in {"STATISTIC", "MARKET", "EARNINGS"}:
        metric_signal = any(
            _contains(title_text, term) or _contains(text, term)
            for term in (
                "집계", "기록", "평균", "변동폭", "최고", "최대", "최저", "상승", "하락",
                "증가", "감소", "급등", "급락", "실적", "매출", "영업이익", "공시", "수치",
            )
        )
        if not metric_signal:
            reasons = (*reasons, "WEAK_METRIC_SIGNAL")
    passed = (
        event_type not in {"OTHER", *_LOW_VALUE_EVENT_TYPES}
        and significance >= 35.0
        and concrete >= 2
        and action
        and metric_signal
    )
    return EventAssessment(event_type, round(significance, 3), concrete, passed, reasons)


def _is_official(item: NewsItem) -> bool:
    if EvidenceType.OFFICIAL_SOURCE in item.provenance:
        return True
    domain = item.source_domain.casefold()
    return domain.endswith((".go.kr", ".gov", ".or.kr")) or "bok.or.kr" in domain


def assess_evidence(cluster: StoryCluster) -> EvidenceAssessment:
    publishers = {item.publisher or item.source_domain for item in cluster.items if item.publisher or item.source_domain}
    official = any(_is_official(item) for item in cluster.items)
    metadata_complete = any(
        len(effective_title(item)) >= 12 and len(effective_lead(item)) >= 24 for item in cluster.items
    )
    repeated = max(0, len(cluster.items) - len(publishers))
    strength = min(40.0, len(publishers) * 14.0) + (42.0 if official else 0.0)
    if metadata_complete:
        strength += 18.0
    strength -= min(8.0, repeated * 1.5)
    reasons: list[str] = []
    if official:
        reasons.append("OFFICIAL_SOURCE")
    if len(publishers) >= 2:
        reasons.append("INDEPENDENT_PUBLISHERS")
    elif publishers:
        reasons.append("SINGLE_PUBLISHER")
    if metadata_complete:
        reasons.append("COMPLETE_METADATA")
    passed = bool(publishers) and (len(publishers) >= 2 or official or metadata_complete)
    return EvidenceAssessment(
        round(max(0.0, min(100.0, strength)), 3),
        len(publishers),
        official,
        metadata_complete,
        passed,
        tuple(reasons),
    )


def completeness_score(cluster: StoryCluster) -> float:
    representative = cluster.representative
    title = effective_title(representative)
    lead = effective_lead(representative)
    raw_title = representative.metadata_title or representative.title
    score = 25.0 if title and raw_title and not _TRUNCATION_RE.search(raw_title) else 0.0
    score += 25.0 if lead and not _TRUNCATION_RE.search(lead) else 0.0
    score += 15.0 if _NUMBER_RE.search(title) or _DATE_RE.search(title) else 0.0
    score += 15.0 if any(_NUMBER_RE.search(effective_text(item)) for item in cluster.items) else 0.0
    score += 20.0 if cluster.source_count > 1 else 0.0
    return min(100.0, score)


def is_generic_headline(value: str) -> bool:
    text = normalize_text(value)
    return not text or bool(_GENERIC_HEADLINE_RE.match(text)) or text in {"관련 보도", "관련 소식"}


def is_generic_summary(value: str) -> bool:
    text = normalize_text(value)
    return any(marker in text for marker in _GENERIC_SUMMARY_MARKERS)


def _truncated_prefix_has_event_fact(item: NewsItem) -> bool:
    """Allow a truncated title when its safe lead prefix proves the event."""

    for value in (item.metadata_description, item.summary):
        text = normalize_text(value)
        marker = _TRUNCATION_RE.search(text)
        if not marker:
            continue
        prefix = text[:marker.start()].strip(" ,·-—")
        if len(prefix) < 12:
            continue
        has_date = bool(_DATE_RE.search(prefix) or re.search(r"\d{1,2}\s?월", prefix))
        has_event = any(
            _contains(prefix, term)
            for term in ("발매", "출시", "컴백", "공연", "콘서트", "개최", "진행", "시작", "공개", "예정")
        )
        if has_date and has_event:
            return True
    return False


def event_signature(cluster: StoryCluster, event: EventAssessment | None = None) -> str:
    assessed = event or assess_event(cluster, Topic(cluster.topic_id, cluster.topic_id, True, False, 50, ()))
    if assessed.event_type == "SPORTS_INTERRUPTION":
        evidence = " ".join(effective_text(item) for item in cluster.items)
        league = "프로야구" if any(term in evidence for term in ("프로야구", "KBO", "야구")) else "야구"
        heat = "폭염" if any(term in evidence for term in ("폭염", "열파")) else ""
        dates = _DATE_RE.findall(evidence)
        return "|".join(dict.fromkeys((assessed.event_type, league, heat, *dates[:1])))
    headline_item = best_headline_item(cluster.items)
    title = effective_title(headline_item)
    if any(
        marker.casefold() in title.casefold()
        for marker in ("환율", "원달러", "원·달러", "코스피", "KOSPI", "코스닥", "KOSDAQ")
    ):
        title = market_primary_text(headline_item) or title
    terms = [token for token in _tokens(title) if token not in _GENERIC_TERMS]
    numbers = _NUMBER_RE.findall(title)
    dates = _DATE_RE.findall(title)
    return "|".join(dict.fromkeys((assessed.event_type, *terms[:8], *numbers[:3], *dates[:2])))


def assess_cluster(
    cluster: StoryCluster,
    topic: Topic,
    *,
    novelty: str = "UNKNOWN_HISTORY",
) -> EditorialAssessment:
    relevance = assess_relevance(cluster, topic)
    event = assess_event(cluster, topic)
    evidence = assess_evidence(cluster)
    completeness = completeness_score(cluster)
    signature = event_signature(cluster, event)
    representative = cluster.representative
    raw_headline = representative.metadata_title or representative.title
    # A source headline may use an editorial ellipsis even when the clause
    # before it is a complete, fact-bearing headline.  The renderer removes
    # the marker; selection should reject only the resulting generic or empty
    # headline, not every article that contains the marker.
    generic_headline = is_generic_headline(effective_title(representative))
    generic_summary = is_generic_summary(effective_lead(representative))
    truncated_title_without_lead = bool(
        representative.title
        and _TRUNCATION_RE.search(representative.title)
        and not (representative.metadata_title and safe_evidence_text(representative.metadata_title))
        and not effective_lead(representative)
    )
    completed_event_headline = any(
        _contains(effective_title(representative), marker)
        for marker in ("대성황", "성황", "성료", "진행", "개최", "열렸다", "마쳤다")
    )
    thin_truncated_schedule = (
        cluster.source_count == 1
        and truncated_title_without_lead
        and event.event_type == "SCHEDULED_EVENT"
        and not _DATE_RE.search(effective_title(representative))
        and not completed_event_headline
        and not _truncated_prefix_has_event_fact(representative)
    )
    single_source_supported = (
        cluster.source_count == 1
        and (
            evidence.official
            or evidence.metadata_complete
            or (
                relevance.passed
                and relevance.direct_title_match
                and relevance.score >= 40
                and event.significance >= 64
                and event.concrete_fact_count >= 2
            )
        )
    )
    synthesis_ready = not (
        event.event_type in {"STATISTIC", "MARKET_MOVE", "MARKET"}
        and not (
            _NUMBER_RE.search(effective_title(cluster.representative))
            or _DATE_RE.search(effective_title(cluster.representative))
            or effective_lead(cluster.representative)
            or cluster.source_count > 1
        )
    )
    reasons = list(relevance.reasons + event.reasons + evidence.reasons)
    if single_source_supported:
        reasons.append("SUPPORTED_SINGLE_SOURCE")
    if generic_headline:
        reasons.append("GENERIC_HEADLINE")
    if generic_summary:
        reasons.append("GENERIC_SUMMARY")
    if thin_truncated_schedule:
        reasons.append("TRUNCATED_EVENT_WITHOUT_LEAD")
    if novelty == "NEW":
        novelty_value = 100.0
        reasons.append("NEW")
    elif novelty == "UPDATE":
        novelty_value = 86.0
        reasons.append("UPDATE")
    elif novelty == "UNCHANGED":
        novelty_value = 0.0
        reasons.append("UNCHANGED")
    else:
        novelty_value = 52.0
        reasons.append("UNKNOWN_HISTORY")
    recency = max(0.0, min(100.0, representative.score))
    personal = min(100.0, max(0.0, float(topic.priority)))
    score = (
        relevance.score * 0.32
        + event.significance * 0.25
        + evidence.strength * 0.16
        + completeness * 0.10
        + novelty_value * 0.10
        + recency * 0.05
        + personal * 0.02
    )
    hard_reject = (
        generic_headline
        or generic_summary
        or thin_truncated_schedule
        or not relevance.passed
        or not event.passed
        or not evidence.passed and not single_source_supported
        or (novelty == "UNCHANGED")
        or (event.event_type == "MERCHANDISE" and not evidence.official)
        or event.event_type in _LOW_VALUE_EVENT_TYPES
        or not synthesis_ready
        or (cluster.source_count == 1 and not single_source_supported)
        or (event.event_type == "OTHER" and cluster.source_count == 1 and event.concrete_fact_count == 0)
    )
    qualified = not hard_reject and score >= 42.0
    if qualified:
        reasons.append("QUALIFIED")
    else:
        reasons.append("REJECTED_BY_EDITORIAL_GATE")
    return EditorialAssessment(
        relevance=relevance,
        event=event,
        evidence=evidence,
        completeness=round(completeness, 3),
        novelty=novelty,
        event_signature=signature,
        qualified=qualified,
        final_score=round(score, 4),
        reasons=tuple(dict.fromkeys(reasons)),
    )


def why_selected(assessment: EditorialAssessment) -> tuple[str, ...]:
    reasons: list[str] = []
    if assessment.relevance.score >= 70:
        reasons.append("HIGH_INTENT")
    elif assessment.relevance.passed:
        reasons.append("DIRECT_TOPIC_MATCH")
    if assessment.event.passed:
        reasons.append("CONCRETE_EVENT")
    if assessment.evidence.official:
        reasons.append("OFFICIAL_SOURCE")
    elif assessment.evidence.publisher_diversity >= 2:
        reasons.append("MULTI_SOURCE")
    elif assessment.evidence.metadata_complete:
        reasons.append("COMPLETE_METADATA")
    else:
        reasons.append("SUPPORTED_SINGLE_SOURCE")
    if assessment.novelty in {"NEW", "UPDATE"}:
        reasons.append(assessment.novelty)
    return tuple(reasons)
