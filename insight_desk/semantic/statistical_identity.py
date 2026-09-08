from __future__ import annotations

import re


_TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9·]+")
_REFERENCE_MONTH_RE = re.compile(r"(?<!\d)(?:20\d{2}년\s*)?(1[0-2]|[1-9])월")
_STATISTICAL_RELEASE_ACTOR_RE = re.compile(
    r"(?P<actor>[가-힣A-Za-z][가-힣A-Za-z0-9·]{1,29})(?:은|는|이|가|의)\s+"
    r"[^.!?。！？]{0,100}?통계"
)
_STATISTICAL_RELEASE_TOKEN_RE = re.compile(
    r"통계(?:에서|에는|으로|은|는|이|가|을|를|의|에|로)?$"
)
_OFFICIAL_RELEASE_TITLE_RE = re.compile(
    r"(?P<actor>[가-힣A-Za-z][가-힣A-Za-z0-9·]{1,29})(?:은|는|이|가)\s+"
    r"(?:(?:오늘|당일|\d{1,2}일)\s+)?발표한\s+"
    r"[‘'\"\[]?"
    r"(?:(?:20\d{2}년)\s*)?(?P<month>1[0-2]|[1-9])월\s+"
    r"(?P<title>[가-힣A-Za-z0-9·][가-힣A-Za-z0-9·\s]{3,59}?)"
    r"[’'\"\]]?(?=\s*(?:에\s+따르면|에\s+의하면|에서|으로|$))"
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。！？])\s+|\n+")
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
        if _STATISTICAL_RELEASE_TOKEN_RE.fullmatch(token) is None:
            continue
        start = max(0, index - _MAX_RELEASE_PREFIX_TOKENS + 1)
        sequence = list(tokens[start : index + 1])
        sequence[-1] = "통계"
        sequences.append(tuple(sequence))
    return tuple(sequences)


def _sentences(value: str) -> tuple[str, ...]:
    normalized = _normalized(value)
    if not normalized:
        return ()
    return tuple(
        sentence.strip()
        for sentence in _SENTENCE_SPLIT_RE.split(normalized)
        if sentence.strip()
    ) or (normalized,)


def _official_release_title_surfaces(
    value: str,
) -> tuple[tuple[int, str, tuple[str, ...]], ...]:
    surfaces: list[tuple[int, str, tuple[str, ...]]] = []
    for sentence in _sentences(value):
        for match in _OFFICIAL_RELEASE_TITLE_RE.finditer(sentence):
            title = tuple(_TOKEN_RE.findall(match.group("title").casefold()))
            if len("".join(title)) < 8:
                continue
            surfaces.append(
                (int(match.group("month")), match.group("actor").casefold(), title)
            )
    return tuple(surfaces)


def _same_official_release_title(left_text: str, right_text: str) -> bool:
    for left_month, left_actor, left_title in _official_release_title_surfaces(left_text):
        for right_month, right_actor, right_title in _official_release_title_surfaces(right_text):
            if left_month != right_month or left_actor != right_actor:
                continue
            if left_title == right_title:
                return True
    return False


def _release_surfaces(
    value: str,
) -> tuple[tuple[int, frozenset[str], tuple[tuple[str, ...], ...]], ...]:
    surfaces: list[tuple[int, frozenset[str], tuple[tuple[str, ...], ...]]] = []
    for sentence in _sentences(value):
        month = _single_reference_month(sentence)
        actors = frozenset(_release_actor_candidates(sentence))
        sequences = _release_token_sequences(sentence)
        if month is None or not actors or not sequences:
            continue
        surfaces.append((month, actors, sequences))
    return tuple(surfaces)


def _shared_release_suffix(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
    shared: list[str] = []
    for left_token, right_token in zip(reversed(left), reversed(right)):
        if left_token != right_token:
            break
        shared.append(left_token)
    return tuple(reversed(shared))


def same_statistical_release_fingerprint(left_text: str, right_text: str) -> bool:
    """Identify sibling metrics published from one exact official statistical release.

    This is a high-precision parent-event fingerprint, not fuzzy text similarity. An official
    release can be identified either by an exact quoted/attributed release title after ``발표한``
    or by the existing sentence-local statistical label ending in ``통계``. The exact-title path
    requires the same grammatical actor, reference month, and normalized release-title tokens.
    Metric names and values may differ because they are child facts of the same publication event.
    """

    if _same_official_release_title(left_text, right_text):
        return True

    for left_month, left_actors, left_sequences in _release_surfaces(left_text):
        for right_month, right_actors, right_sequences in _release_surfaces(right_text):
            if left_month != right_month or left_actors.isdisjoint(right_actors):
                continue
            for left in left_sequences:
                for right in right_sequences:
                    shared = _shared_release_suffix(left, right)
                    if len(shared) < _MIN_SHARED_RELEASE_TOKENS:
                        continue
                    if shared[-1] != "통계":
                        continue
                    if len("".join(shared)) < 10:
                        continue
                    return True
    return False
