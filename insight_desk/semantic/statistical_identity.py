from __future__ import annotations

import re


_TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9·]+")
_REFERENCE_MONTH_RE = re.compile(r"(?<!\d)(?:20\d{2}년\s*)?(1[0-2]|[1-9])월")
_STATISTICAL_RELEASE_ACTOR_RE = re.compile(
    r"(?P<actor>[가-힣A-Za-z][가-힣A-Za-z0-9·]{1,29})(?:은|는|이|가|의)\s+"
    r"[^.!?。！？]{0,100}?통계"
)
_MIN_SHARED_RELEASE_TOKENS = 4
_MAX_RELEASE_PREFIX_TOKENS = 8


def _normalized(value: str) -> str:
    return " ".join(value.split()).strip().casefold()


def _single_reference_month(value: str) -> int | None:
    months = {int(month) for month in _REFERENCE_MONTH_RE.findall(_normalized(value))}
    return next(iter(months)) if len(months) == 1 else None


def _release_actor_candidates(value: str) -> set[str]:
    normalized = _normalized(value)
    return {
        match.group("actor").casefold()
        for match in _STATISTICAL_RELEASE_ACTOR_RE.finditer(normalized)
    }


def _release_token_sequences(value: str) -> tuple[tuple[str, ...], ...]:
    tokens = tuple(_TOKEN_RE.findall(_normalized(value)))
    sequences: list[tuple[str, ...]] = []
    for index, token in enumerate(tokens):
        if token != "통계":
            continue
        start = max(0, index - _MAX_RELEASE_PREFIX_TOKENS + 1)
        sequences.append(tokens[start : index + 1])
    return tuple(sequences)


def _shared_release_suffix(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
    shared: list[str] = []
    for left_token, right_token in zip(reversed(left), reversed(right)):
        if left_token != right_token:
            break
        shared.append(left_token)
    return tuple(reversed(shared))


def same_statistical_release_fingerprint(left_text: str, right_text: str) -> bool:
    """Identify sibling metrics published from one exact official statistical release.

    This is a high-precision parent-event fingerprint, not fuzzy text similarity. Both visible cards
    must name the same grammatical release actor, contain exactly one compatible reference month,
    and share an exact multi-token release label ending in ``통계``. Metric names and values may
    differ because those are child facts of the same publication event.
    """

    left_month = _single_reference_month(left_text)
    right_month = _single_reference_month(right_text)
    if left_month is None or left_month != right_month:
        return False

    left_actors = _release_actor_candidates(left_text)
    right_actors = _release_actor_candidates(right_text)
    if not left_actors or left_actors.isdisjoint(right_actors):
        return False

    for left in _release_token_sequences(left_text):
        for right in _release_token_sequences(right_text):
            shared = _shared_release_suffix(left, right)
            if len(shared) < _MIN_SHARED_RELEASE_TOKENS:
                continue
            if shared[-1] != "통계":
                continue
            if len("".join(shared)) < 10:
                continue
            return True
    return False
