from __future__ import annotations

import re


_BROAD_MARKET_RE = re.compile(r"(?:국내|한국)\s*(?:증시|주식시장)|(?<![가-힣])증시(?![가-힣])")
_INDEX_RE = re.compile(r"(?i)(?<![A-Za-z가-힣])(?:코스피|KOSPI|코스닥|KOSDAQ)(?![A-Za-z가-힣])")
_DAY_RE = re.compile(r"(?<!\d)([1-9]|[12]\d|3[01])일")
_CLOSE_RE = re.compile(r"(?:마감|장을\s+마쳤|거래를\s+마쳤|종가)")
_UP_CLOSE_RE = re.compile(
    r"(?:상승(?:세)?(?:한|해|하며|으로)?|올라|오르며|반등해)[^.!?。！？]{0,90}"
    r"(?:마감|장을\s+마쳤|거래를\s+마쳤)"
)
_DOWN_CLOSE_RE = re.compile(
    r"(?:하락(?:세)?(?:한|해|하며|으로)?|내려|내리며|급락해)[^.!?。！？]{0,90}"
    r"(?:마감|장을\s+마쳤|거래를\s+마쳤)"
)


def _normalized(value: str) -> str:
    return " ".join(value.split()).strip().casefold()


def _index_kind(value: str) -> str | None:
    normalized = _normalized(value)
    kinds: set[str] = set()
    if "코스피" in normalized or "kospi" in normalized:
        kinds.add("kospi")
    if "코스닥" in normalized or "kosdaq" in normalized:
        kinds.add("kosdaq")
    return next(iter(kinds)) if len(kinds) == 1 else None


def _broad_market(value: str) -> bool:
    return _BROAD_MARKET_RE.search(_normalized(value)) is not None


def market_subject_perspective_compatible(left: str, right: str) -> bool:
    """Return True only for broad-market versus one named-index perspective.

    This never equates two different named indexes. It exists only to prevent a grammatical
    perspective difference (for example ``코스피 지수`` versus ``국내 증시``) from becoming a
    deterministic contradiction before the independent semantic identity checks can run.
    """

    left_kind = _index_kind(left)
    right_kind = _index_kind(right)
    left_broad = _broad_market(left)
    right_broad = _broad_market(right)
    return bool(
        (left_kind is not None and right_kind is None and right_broad)
        or (right_kind is not None and left_kind is None and left_broad)
    )


def _close_direction(value: str) -> str | None:
    normalized = _normalized(value)
    if _CLOSE_RE.search(normalized) is None:
        return None
    up = _UP_CLOSE_RE.search(normalized) is not None
    down = _DOWN_CLOSE_RE.search(normalized) is not None
    if up == down:
        return None
    return "up" if up else "down"


def same_market_session_fact_perspective(
    *,
    left_subject: str,
    right_subject: str,
    left_text: str,
    right_text: str,
    left_date: str | None,
    right_date: str | None,
) -> bool:
    """Identify only a same-date close viewed as index versus broad domestic market."""

    if not market_subject_perspective_compatible(left_subject, right_subject):
        return False
    left_date_key = _normalized(left_date or "")
    right_date_key = _normalized(right_date or "")
    if not left_date_key or left_date_key != right_date_key:
        return False
    left_direction = _close_direction(left_text)
    right_direction = _close_direction(right_text)
    return left_direction is not None and left_direction == right_direction


def same_market_session_close_fingerprint(left_text: str, right_text: str) -> bool:
    """Return a high-precision cross-source anchor for one domestic market close.

    The fingerprint requires the same explicit calendar day, one broad-market perspective and one
    named-index perspective, plus the same closing direction. It authorizes only the stronger
    two-slot semantic comparison; it never authorizes a merge by itself.
    """

    left = _normalized(left_text)
    right = _normalized(right_text)
    left_days = set(_DAY_RE.findall(left))
    right_days = set(_DAY_RE.findall(right))
    if len(left_days) != 1 or left_days != right_days:
        return False

    left_kind = _index_kind(left)
    right_kind = _index_kind(right)
    if left_kind is not None and right_kind is not None and left_kind != right_kind:
        return False
    if not (
        (left_kind is not None and _broad_market(right))
        or (right_kind is not None and _broad_market(left))
    ):
        return False

    left_direction = _close_direction(left)
    right_direction = _close_direction(right)
    return left_direction is not None and left_direction == right_direction
