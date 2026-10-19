from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from .config import CurationConfig


@dataclass(frozen=True, slots=True)
class Scored:
    key: str
    topic_id: str
    topic_priority: int
    total: float
    source_domain: str = ""


@dataclass(frozen=True, slots=True)
class SelectionResult:
    selected: tuple[Scored, ...]
    dropped: tuple[tuple[Scored, str], ...]


def select_daily(
    candidates: Sequence[Scored],
    *,
    cfg: CurationConfig,
    accept: Callable[[Scored], str | None] | None = None,
) -> SelectionResult:
    """점수 순으로 한도 안에서 고른다.

    `accept`가 있으면 한도를 통과한 후보마다 호출하고(카드 생성·원문 대조 같은 비싼 검사), 사유 문자열을
    돌려주면 그 후보는 `dropped`에 그 사유로 기록하고 자리를 차지하지 않는다. 그래서 대조에서 떨어진 글
    대신 다음 점수의 글이 올라온다.
    """
    seen_keys: set[str] = set()
    unique: list[Scored] = []
    for c in candidates:
        if c.key not in seen_keys:
            seen_keys.add(c.key)
            unique.append(c)

    unique.sort(key=lambda x: (-x.total, -x.topic_priority, x.key))

    selected: list[Scored] = []
    dropped: list[tuple[Scored, str]] = []
    topic_counts: dict[str, int] = {}

    for c in unique:
        if c.total < cfg.pass_score_for(c.topic_id):
            dropped.append((c, "below_pass_score"))
            continue
        if len(selected) >= cfg.max_daily:
            dropped.append((c, "daily_cap"))
            continue
        tc = topic_counts.get(c.topic_id, 0)
        if tc >= cfg.max_per_topic:
            dropped.append((c, "topic_cap"))
            continue
        if accept is not None:
            refusal = accept(c)
            if refusal is not None:
                dropped.append((c, refusal))
                continue
        selected.append(c)
        topic_counts[c.topic_id] = tc + 1

    return SelectionResult(selected=tuple(selected), dropped=tuple(dropped))
