from __future__ import annotations

from collections import defaultdict

from ..domain.models import KeywordGroup, TrendMetric, TrendPoint
from .semantics import contains_intent_term


# Naver Trend ratios are relative indices, not measurements with arbitrary
# precision.  Treat a move as material only when it clears both the one-index
# point floor and, for a non-zero baseline, the five-percent relative floor.
_MIN_MATERIAL_DELTA = 1.0
_MIN_MATERIAL_RELATIVE = 0.05


def _trend_state(delta: float | None, previous: float | None) -> str:
    if delta is None or previous is None:
        return "INSUFFICIENT_COMPARISON"
    material = abs(delta) >= _MIN_MATERIAL_DELTA or (
        previous > 0 and abs(delta) / previous >= _MIN_MATERIAL_RELATIVE
    )
    if not material:
        return "NO_MEANINGFUL_CHANGE"
    return "RISE" if delta > 0 else "FALL"


def effective_trend_state(metric: TrendMetric) -> str:
    """Read the persisted state, with compatibility for old in-memory data.

    Older fixtures and archived objects predate ``TrendMetric.state`` and
    therefore carry the default value even when both comparison ratios are
    present.  Re-evaluate only that legacy shape using the same deterministic
    materiality rule; never infer a direction when the comparison is absent.
    """

    if metric.state != "INSUFFICIENT_COMPARISON":
        return metric.state
    if metric.delta is not None and metric.previous_ratio is not None:
        return _trend_state(metric.delta, metric.previous_ratio)
    return "INSUFFICIENT_COMPARISON"


def parse_trend_batches(
    batches: tuple[tuple[str, tuple[KeywordGroup, ...], dict[str, object]], ...]
) -> tuple[TrendPoint, ...]:
    points: list[TrendPoint] = []
    for batch_id, groups, payload in batches:
        group_by_name = {group.name: group for group in groups}
        results = payload.get("results", [])
        if not isinstance(results, list):
            continue
        for result in results:
            if not isinstance(result, dict):
                continue
            name = str(result.get("title", ""))
            group = group_by_name.get(name)
            if group is None:
                continue
            data = result.get("data", [])
            if not isinstance(data, list):
                continue
            for raw_point in data:
                if not isinstance(raw_point, dict):
                    continue
                try:
                    period = str(raw_point["period"])
                    ratio = float(raw_point["ratio"])
                except (KeyError, TypeError, ValueError):
                    continue
                points.append(
                    TrendPoint(
                        group_id=group.id,
                        group_name=group.name,
                        topic_id=group.topic_id,
                        period=period,
                        ratio=ratio,
                        batch_id=batch_id,
                        aliases=tuple(group.keywords),
                    )
                )
    return tuple(points)


def compute_trend_metrics(points: tuple[TrendPoint, ...]) -> tuple[TrendMetric, ...]:
    grouped: dict[str, list[TrendPoint]] = defaultdict(list)
    for point in points:
        grouped[point.group_id].append(point)
    metrics: list[TrendMetric] = []
    for group_id, group_points in grouped.items():
        ordered = sorted(group_points, key=lambda point: point.period)
        current = ordered[-1].ratio if ordered else None
        previous = ordered[-2].ratio if len(ordered) >= 2 else None
        history = [point.ratio for point in ordered[-8:-1]]
        moving_average = sum(history) / len(history) if history else None
        delta = current - previous if current is not None and previous is not None else None
        change_percent = None
        if delta is not None and previous and previous > 0:
            change_percent = delta / previous * 100.0
        spike_score = None
        if delta is not None and moving_average is not None:
            spike_score = delta + max(0.0, current - moving_average) * 0.5
        state = _trend_state(delta, previous)
        if state == "INSUFFICIENT_COMPARISON":
            interpretation = "비교 기준 부족"
        elif state == "NO_MEANINGFUL_CHANGE":
            interpretation = "유의미한 변화 없음"
        elif state == "RISE":
            interpretation = "직전 구간보다 상승"
        else:
            interpretation = "직전 구간보다 하락"
        first = ordered[0]
        metrics.append(
            TrendMetric(
                group_id=group_id,
                group_name=first.group_name,
                topic_id=first.topic_id,
                batch_id=first.batch_id,
                current_ratio=current,
                previous_ratio=previous,
                moving_average=moving_average,
                delta=delta,
                change_percent=change_percent,
                spike_score=spike_score,
                interpretation=interpretation,
                points=tuple(ordered),
                state=state,
                aliases=tuple(dict.fromkeys(alias for point in ordered for alias in point.aliases)),
            )
        )
    # Never sort by absolute ratio: batches are independent and ratio is relative.
    return tuple(sorted(metrics, key=lambda metric: (metric.topic_id, metric.group_name)))
