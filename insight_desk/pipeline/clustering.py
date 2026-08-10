from __future__ import annotations

import re
from dataclasses import dataclass

from ..domain.models import NewsItem
from .semantics import canonical_publisher, contains_action


@dataclass(frozen=True)
class StoryCluster:
    topic_id: str
    items: tuple[NewsItem, ...]

    @property
    def representative(self) -> NewsItem:
        return max(self.items, key=lambda item: (item.score, len(item.summary), item.title))

    @property
    def source_count(self) -> int:
        return len({canonical_publisher(item.publisher, item.source_domain) for item in self.items})


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z0-9가-힣]{2,}", text)}


_EVENT_TERMS = {
    "규제", "정책", "발표", "공개", "출시", "투자", "유치", "인수", "실적", "공시",
    "경기", "승리", "패배", "부상", "트레이드", "선발", "엔트리", "시행", "일정",
    "컴백", "공연", "콘서트", "차트", "기록", "상승", "하락", "급등", "급락", "변동",
    "발매", "협업", "프로젝트",
    "폭염", "중단", "멈춘", "논란", "요구", "촉구", "줄여라", "최소화",
}
_GENERIC_TERMS = {"관련", "보도", "소식", "뉴스", "주요", "변화", "이슈", "확인"}
_CONTEXT_TERMS = {"행사", "일정", "참석", "포토", "블루카펫", "대표", "얼굴", "내일의", "오늘의"}
_CLUSTER_GENERIC_ENTITIES = {
    "앨범", "미니", "싱글", "음악", "차트", "가요계", "그룹", "신인", "걸그룹",
    "보이그룹", "콘셉트", "포토", "국내외", "글로벌", "집", "모델", "서비스",
    "제품", "신제품", "사업", "시장", "업계", "리그", "경기", "선수", "구단",
    "kbo", "프로야구", "야구",
    "반도체", "메모리", "hbm", "hbf", "gpu", "ai", "증시", "주가", "첨단산업", "지원",
    "모멘텀", "수혜", "초호황", "확정", "신보", "신곡", "기념", "데뷔", "만에",
}
_GENERIC_ACTION_TERMS = {"발표", "공개", "일정", "기록", "변동", "확인"}
_RELEASE_ACTIONS = {"출시", "발매", "컴백", "release_announcement"}
_RELEASE_NOUNS = {"앨범", "음원", "싱글", "신곡", "신보"}
_POLICY_ACTIONS = {"요구", "촉구", "줄여라", "최소화"}
_HEAT_INTERRUPTION_TERMS = {
    "중단", "멈춘", "휴식", "재개", "취소", "방학", "브레이크", "순연", "재편", "일정"
}
_DATE_NUMBER_RE = re.compile(
    r"(?:20\d{2}\s?년|\d{1,2}\s?(?:월|일)|\d+(?:[,\.]\d+)?\s?(?:%|원|달러|억|만|명|건|배|개|곳|주년|위|점|대|선))"
)
_DATE_MARKER_RE = re.compile(r"(?:20\d{2}\s?년\s?)?\d{1,2}\s?(?:월(?:\s?\d{1,2}\s?일)?|일)")
_MARKET_INSTRUMENTS = (
    ("kospi", ("코스피", "KOSPI")),
    ("kosdaq", ("코스닥", "KOSDAQ")),
    ("usdkrw", ("원·달러", "원달러", "환율")),
    ("jpy", ("엔화",)),
    ("samsung", ("삼성전자",)),
    ("skhynix", ("SK하이닉스", "하이닉스")),
    ("treasury", ("국채선물", "국채")),
    ("nasdaq", ("나스닥", "NASDAQ")),
    ("sp500", ("S&P500", "S&P 500")),
    ("dow", ("다우", "DOW")),
)


def _item_text(item: NewsItem) -> str:
    return " ".join(
        value
        for value in (
            item.query,
            item.metadata_title,
            item.title,
            item.metadata_description,
            item.summary if not re.search(r"\.{2,}|…|·{2,}", item.summary) else "",
        )
        if value
    ).lower()


def _is_sports_heat_story(item: NewsItem) -> bool:
    """Recognize the league-wide heat interruption theme across headlines.

    Search headlines describe the same disruption with different wording
    (``폭염은 물러가도``, ``폭염에 멈춘``, ``폭염 휴식``).  Requiring exact
    action-token overlap leaves those reports in separate clusters and lets
    one analytical headline masquerade as a second event.
    """

    # A description can append a separate ceremonial event (for example a
    # first-pitch notice) to an otherwise unrelated headline. Require the
    # heat signal in the headline itself; use the lead only to establish the
    # sports context for an analytical heat headline.
    headline = " ".join(value for value in (item.metadata_title, item.title) if value).lower()
    if not any(term in headline for term in ("폭염", "열파")):
        return False
    trusted_lead = " ".join(
        value
        for value in (item.metadata_description, item.summary)
        if value and not re.search(r"\.{2,}|…|·{2,}", value)
    ).lower()
    return bool(
        any(term in headline for term in ("폭염", "열파"))
        and any(term in f"{headline} {trusted_lead}" for term in ("kbo", "프로야구", "한국 야구", "야구"))
        and (
            any(term in headline for term in _HEAT_INTERRUPTION_TERMS)
            or any(term in trusted_lead for term in _HEAT_INTERRUPTION_TERMS)
        )
    )


def _event_parts(item: NewsItem) -> tuple[set[str], set[str], set[str]]:
    # The NAVER description is a retrieval snippet, not a trustworthy body
    # document.  Its trailing clauses often mention an unrelated person,
    # brand, or event.  Do not let that incidental tail merge otherwise
    # separate stories.  Use the title and optional enriched metadata as the
    # event signature; the dedicated heat-interruption rule above is the only
    # bounded exception that needs the snippet context.
    text = (
        market_primary_text(item)
        if _market_instruments(item)
        else " ".join(value for value in (item.metadata_title, item.title) if value)
    ).lower()
    tokens = _tokens(text)
    entities = {
        token
        for token in tokens
        if token not in _EVENT_TERMS
        and token not in _GENERIC_TERMS
        and token not in _CONTEXT_TERMS
        and token not in _CLUSTER_GENERIC_ENTITIES
        # A numeric level/result such as ``1300원대`` or ``55경기`` is a
        # supporting fact, not an entity.  Let the dedicated number set
        # carry it so a shared number cannot join unrelated events.
        and not token[0].isdigit()
        and not _DATE_NUMBER_RE.fullmatch(token)
    }
    actions = {
        term
        for term in _EVENT_TERMS
        if (contains_action(text, term) if term in {"부상", "투자", "트레이드", "선발", "경기", "승리", "패배", "상승", "하락"} else term in text)
        and term not in _GENERIC_ACTION_TERMS
    }
    dates_numbers = {
        value for value in _DATE_NUMBER_RE.findall(text)
        # An anniversary is shared context, not an event date.  Treating
        # ``20주년`` as a merge key lets a release and a separate anniversary
        # campaign form one transitive cluster.
        if not value.endswith("주년")
    }
    if "발표" in text and any(noun in text for noun in _RELEASE_NOUNS):
        # ``발표`` is intentionally generic elsewhere, but ``신곡 발표`` (and
        # its equivalents) is a release signal that should align with
        # ``발매``/``컴백`` headlines without joining policy announcements.
        actions.add("release_announcement")
    return entities, actions, dates_numbers


def _date_markers(item: NewsItem) -> set[str]:
    text = " ".join(value for value in (item.metadata_title, item.title) if value)
    return {re.sub(r"\s+", "", value) for value in _DATE_MARKER_RE.findall(text)}


def market_primary_text(item: NewsItem) -> str:
    """Return the primary clause of a market headline when it is explicit."""

    text = " ".join(value for value in (item.metadata_title, item.title) if value)
    primary_clause = re.split(r"(?:…|\.{2,}|·{2,})", text, maxsplit=1)[0].strip()
    if any(marker.casefold() in primary_clause.casefold() for _, markers in _MARKET_INSTRUMENTS for marker in markers):
        return primary_clause
    return text


def _market_instruments(item: NewsItem) -> set[str]:
    """Return primary market instruments from trusted headline text.

    A headline can append a second instrument after an ellipsis (for example
    a KOSPI lead followed by an exchange-rate note).  That secondary clause
    must not become a clustering bridge to an otherwise separate story.
    """

    text = market_primary_text(item)
    return {
        instrument
        for instrument, markers in _MARKET_INSTRUMENTS
        if any(marker.casefold() in text.casefold() for marker in markers)
    }


def _similar(a: NewsItem, b: NewsItem) -> bool:
    if _is_sports_heat_story(a) and _is_sports_heat_story(b):
        return True
    left_instruments = _market_instruments(a)
    right_instruments = _market_instruments(b)
    # A shared macro driver such as ``금리`` or ``상승`` is not enough to
    # merge separate instruments.  Prevent transitive clusters from turning
    # an index, a stock, and a currency into one synthetic market story.
    if left_instruments and right_instruments and not left_instruments & right_instruments:
        return False
    left_dates = _date_markers(a)
    right_dates = _date_markers(b)
    # Different dated events about the same entity are not one story merely
    # because they share a generic action such as ``컴백`` or ``출시``.
    if left_dates and right_dates and not left_dates & right_dates:
        return False
    left = _tokens(a.title)
    right = _tokens(b.title)
    if not left or not right:
        return False
    if len(left & right) / len(left | right) >= 0.45 and (left & right) - _GENERIC_TERMS:
        return True
    left_entities, left_actions, left_dates = _event_parts(a)
    right_entities, right_actions, right_dates = _event_parts(b)
    shared_entities = left_entities & right_entities
    shared_actions = left_actions & right_actions
    shared_dates = left_dates & right_dates
    actions_compatible = (
        not left_actions
        or not right_actions
        or bool(left_actions & right_actions)
        or (left_actions <= _RELEASE_ACTIONS and right_actions <= _RELEASE_ACTIONS)
    )
    # A shared entity alone is not enough: the action/event or a concrete date
    # must also line up. This prevents two unrelated stories about one company
    # or artist from being over-merged.
    same_release_family = bool(
        left_actions
        and right_actions
        and left_actions <= _RELEASE_ACTIONS
        and right_actions <= _RELEASE_ACTIONS
    )
    same_policy_family = bool(
        left_actions
        and right_actions
        and left_actions <= _POLICY_ACTIONS
        and right_actions <= _POLICY_ACTIONS
        and len(shared_entities) >= 2
    )
    return bool(
        shared_entities
        and (shared_actions or same_release_family or same_policy_family or (shared_dates and actions_compatible))
    )


def cluster_news(items: tuple[NewsItem, ...]) -> tuple[StoryCluster, ...]:
    # A duplicate can legitimately match more than one personal interest.
    # Build topic-local views after cross-topic dedupe so config order does not
    # steal attribution from the secondary interest.
    clusters: list[tuple[str, list[NewsItem]]] = []
    for item in items:
        topic_ids = tuple(dict.fromkeys(item.matched_topic_ids or (item.topic_id,)))
        for topic_id in topic_ids:
            placed = False
            for existing_topic_id, cluster in clusters:
                if existing_topic_id == topic_id and any(_similar(item, member) for member in cluster):
                    cluster.append(item)
                    placed = True
                    break
            if not placed:
                clusters.append((topic_id, [item]))
    return tuple(StoryCluster(topic_id=topic_id, items=tuple(cluster)) for topic_id, cluster in clusters)
