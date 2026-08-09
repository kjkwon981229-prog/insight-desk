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
_GENERIC_ACTION_TERMS = {"발표", "공개", "일정", "기록", "변동", "확인"}
_DATE_NUMBER_RE = re.compile(
    r"(?:20\d{2}\s?년|\d{1,2}\s?(?:월|일)|\d+(?:[,\.]\d+)?\s?(?:%|원|달러|억|만|명|건|배|개|곳|주년|위|점|대))"
)


def _event_parts(item: NewsItem) -> tuple[set[str], set[str], set[str]]:
    text = " ".join(
        value
        for value in (
            item.metadata_title,
            item.title,
            item.metadata_description,
            item.summary if not re.search(r"\.{2,}|…", item.summary) else "",
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


def _similar(a: NewsItem, b: NewsItem) -> bool:
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
