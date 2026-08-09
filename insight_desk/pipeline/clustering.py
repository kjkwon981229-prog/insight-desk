from __future__ import annotations

import re
from dataclasses import dataclass

from ..domain.models import NewsItem


@dataclass(frozen=True)
class StoryCluster:
    topic_id: str
    items: tuple[NewsItem, ...]

    @property
    def representative(self) -> NewsItem:
        return max(self.items, key=lambda item: (item.score, len(item.summary), item.title))

    @property
    def source_count(self) -> int:
        return len({item.source_domain for item in self.items})


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z0-9가-힣]{2,}", text)}


_EVENT_TERMS = {
    "규제", "정책", "발표", "공개", "출시", "투자", "유치", "인수", "실적", "공시",
    "경기", "승리", "패배", "부상", "트레이드", "선발", "엔트리", "시행", "일정",
    "컴백", "공연", "콘서트", "차트", "기록", "상승", "하락", "급등", "급락", "변동",
    "폭염", "중단", "멈춘", "논란",
}
_GENERIC_TERMS = {"관련", "보도", "소식", "뉴스", "주요", "변화", "이슈", "확인"}
_CONTEXT_TERMS = {"행사", "일정", "참석", "포토", "블루카펫", "대표", "얼굴", "내일의", "오늘의"}
_CLUSTER_GENERIC_ENTITIES = {
    "앨범", "미니", "싱글", "음악", "차트", "가요계", "그룹", "신인", "걸그룹",
    "보이그룹", "콘셉트", "포토", "국내외", "글로벌", "집", "모델", "서비스",
    "제품", "신제품", "사업", "시장", "업계", "리그", "경기", "선수", "구단",
}
_GENERIC_ACTION_TERMS = {"발표", "공개", "일정", "기록", "변동", "확인"}
_DATE_NUMBER_RE = re.compile(
    r"(?:20\d{2}\s?년|\d{1,2}\s?(?:월|일)|\d+(?:[,\.]\d+)?\s?(?:%|원|달러|억|만|명|건|배|개|곳|주년|위|점|대))"
)
_DATE_MARKER_RE = re.compile(r"(?:20\d{2}\s?년\s?)?\d{1,2}\s?(?:월(?:\s?\d{1,2}\s?일)?|일)")


def _item_text(item: NewsItem) -> str:
    return " ".join(
        value
        for value in (
            item.query,
            item.metadata_title,
            item.title,
            item.metadata_description,
            item.summary if not re.search(r"\.{2,}|…", item.summary) else "",
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
    text = " ".join(
        value for value in (headline, item.metadata_description, item.summary) if value
    ).lower()
    return bool(
        any(term in text for term in ("폭염", "열파"))
        and any(term in text for term in ("kbo", "프로야구", "한국 야구", "야구"))
    )


def _event_parts(item: NewsItem) -> tuple[set[str], set[str], set[str]]:
    # The NAVER description is a retrieval snippet, not a trustworthy body
    # document.  Its trailing clauses often mention an unrelated person,
    # brand, or event.  Do not let that incidental tail merge otherwise
    # separate stories.  Use the title and optional enriched metadata as the
    # event signature; the dedicated heat-interruption rule above is the only
    # bounded exception that needs the snippet context.
    text = " ".join(
        value
        for value in (
            item.metadata_title,
            item.title,
            item.metadata_description,
        )
        if value
    ).lower()
    tokens = _tokens(text)
    entities = {
        token
        for token in tokens
        if token not in _EVENT_TERMS
        and token not in _GENERIC_TERMS
        and token not in _CONTEXT_TERMS
        and token not in _CLUSTER_GENERIC_ENTITIES
        and not token.isdigit()
        and not _DATE_NUMBER_RE.fullmatch(token)
    }
    if "프로야구" in text:
        entities.add("야구")
    if "kbo" in text:
        entities.add("야구")
    actions = {
        term for term in _EVENT_TERMS if term in text and term not in _GENERIC_ACTION_TERMS
    }
    dates_numbers = set(_DATE_NUMBER_RE.findall(text))
    return entities, actions, dates_numbers


def _date_markers(item: NewsItem) -> set[str]:
    text = " ".join(value for value in (item.metadata_title, item.title) if value)
    return {re.sub(r"\s+", "", value) for value in _DATE_MARKER_RE.findall(text)}


def _similar(a: NewsItem, b: NewsItem) -> bool:
    if _is_sports_heat_story(a) and _is_sports_heat_story(b):
        return True
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
    # A shared entity alone is not enough: the action/event or a concrete date
    # must also line up. This prevents two unrelated stories about one company
    # or artist from being over-merged.
    return bool(shared_entities and (shared_actions or shared_dates))


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
