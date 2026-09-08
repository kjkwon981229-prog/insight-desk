from __future__ import annotations

import re


_BROAD_MARKET_RE = re.compile(r"(?:국내|한국)\s*(?:증시|주식시장)|(?<![가-힣])증시(?![가-힣])")
_DAY_RE = re.compile(r"(?<!\d)([1-9]|[12]\d|3[01])일")
_FULL_DATE_RE = re.compile(
    r"(?:(20\d{2})년\s*)?(?:(1[0-2]|[1-9])월\s*)?([1-9]|[12]\d|3[01])일"
)
_ISO_DATE_RE = re.compile(r"(20\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])")
_CLOSE_RE = re.compile(r"(?:마감|장을\s+마쳤|거래를\s+마쳤|종가)")
_DIRECTION_RE = re.compile(
    r"(?P<up>상승(?:세)?|반등|올라|오르|오른)|"
    r"(?P<down>하락(?:세)?|급락|내려|내리|내린)"
)
_MAX_DIRECTION_TO_CLOSE_CHARS = 50


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


def _market_perspective_compatible(left: str, right: str) -> bool:
    left_kind = _index_kind(left)
    right_kind = _index_kind(right)
    if left_kind is not None and right_kind is not None and left_kind != right_kind:
        return False
    return bool(
        (left_kind is not None and right_kind is None and _broad_market(right))
        or (right_kind is not None and left_kind is None and _broad_market(left))
    )


def market_subject_perspective_compatible(left: str, right: str) -> bool:
    """Return True only for broad-market versus one named-index subject perspective."""

    return _market_perspective_compatible(left, right)


def _date_parts(value: str | None) -> tuple[int | None, int | None, int] | None:
    normalized = _normalized(value or "")
    korean = _FULL_DATE_RE.fullmatch(normalized)
    if korean is not None:
        year, month, day = korean.groups()
        return (
            int(year) if year is not None else None,
            int(month) if month is not None else None,
            int(day),
        )
    iso = _ISO_DATE_RE.fullmatch(normalized)
    if iso is not None:
        year, month, day = iso.groups()
        return int(year), int(month), int(day)
    return None


def _dates_compatible(left: str | None, right: str | None) -> bool:
    left_normalized = _normalized(left or "")
    right_normalized = _normalized(right or "")
    if not left_normalized or not right_normalized:
        return False
    if left_normalized == right_normalized:
        return True
    left_parts = _date_parts(left)
    right_parts = _date_parts(right)
    if left_parts is None or right_parts is None:
        return False
    left_year, left_month, left_day = left_parts
    right_year, right_month, right_day = right_parts
    if left_day != right_day:
        return False
    if left_month is not None and right_month is not None and left_month != right_month:
        return False
    if left_year is not None and right_year is not None and left_year != right_year:
        return False
    return True


def _close_direction(value: str) -> str | None:
    """Resolve the direction nearest the final close cue, not an earlier intraday move."""

    normalized = _normalized(value)
    close_matches = list(_CLOSE_RE.finditer(normalized))
    if not close_matches:
        return None
    close = close_matches[-1]
    directions = list(_DIRECTION_RE.finditer(normalized[: close.start()]))
    if not directions:
        return None
    nearest = directions[-1]
    if close.start() - nearest.end() > _MAX_DIRECTION_TO_CLOSE_CHARS:
        return None
    return "up" if nearest.lastgroup == "up" else "down"


def same_market_session_fact_perspective(
    *,
    left_subject: str,
    right_subject: str,
    left_text: str,
    right_text: str,
    left_date: str | None,
    right_date: str | None,
) -> bool:
    """Identify one close despite grammatical subject and date-surface differences.

    Fact extractors may choose a causal actor such as ``개인·기관 매수세`` as the subject even
    when the action explicitly says ``국내 증시가 ... 마쳤다``. Use the complete evidence-bound
    fact surface for the market perspective, while requiring compatible explicit calendar dates and
    the same closing direction. The subject-only path remains available as an additional anchor but
    is not required.
    """

    if not (
        _market_perspective_compatible(left_text, right_text)
        or market_subject_perspective_compatible(left_subject, right_subject)
    ):
        return False
    if not _dates_compatible(left_date, right_date):
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

    if not _market_perspective_compatible(left, right):
        return False

    left_direction = _close_direction(left)
    right_direction = _close_direction(right)
    return left_direction is not None and left_direction == right_direction
