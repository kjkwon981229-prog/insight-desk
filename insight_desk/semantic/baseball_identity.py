from __future__ import annotations

import re


_SCORE_RE = re.compile(r"(?<!\d)(\d{1,2})\s*(?:대|[-:])\s*(\d{1,2})(?!\d)")
_DAY_RE = re.compile(r"(?<!\d)([0-3]?\d)일(?!\s*(?:간|동안|후|뒤|째))")
_OUTCOME_CUES = ("승리", "이겼", "이기고", "꺾", "제압", "패배", "졌다", "패했다")
_WIN_CUES = ("완파", "제압", "꺾", "이겼", "승리")
_LOSS_CUES = ("패배", "패하며", "패했다", "패전", "졌다")
_KBO_TEAM_ALIASES = {
    "한화": ("한화 이글스", "한화"),
    "SSG": ("SSG 랜더스", "SSG랜더스", "SSG"),
    "KIA": ("KIA 타이거즈", "KIA"),
    "LG": ("LG 트윈스", "LG"),
    "두산": ("두산 베어스", "두산"),
    "롯데": ("롯데 자이언츠", "롯데"),
    "삼성": ("삼성 라이온즈", "삼성"),
    "KT": ("KT 위즈", "kt wiz", "KT"),
    "NC": ("NC 다이노스", "NC"),
    "키움": ("키움 히어로즈", "키움"),
}
_LOCATION_ALIASES = {
    "인천": ("인천", "SSG랜더스필드", "SSG 랜더스필드"),
    "대전": ("대전", "한화생명 볼파크"),
    "서울잠실": ("잠실", "잠실야구장"),
    "고척": ("고척", "고척스카이돔", "고척 스카이돔"),
    "수원": ("수원", "수원KT위즈파크", "KT위즈파크", "kt wiz park"),
    "광주": ("광주", "기아챔피언스필드", "광주-기아 챔피언스 필드", "광주기아챔피언스필드"),
    "대구": ("대구", "대구삼성라이온즈파크", "삼성라이온즈파크"),
    "부산": ("부산", "사직", "사직야구장"),
    "창원": ("창원", "창원NC파크", "NC파크"),
}


def _team_set(text: str) -> frozenset[str]:
    folded = text.casefold()
    matched: set[str] = set()
    for canonical, aliases in _KBO_TEAM_ALIASES.items():
        if any(alias.casefold() in folded for alias in aliases):
            matched.add(canonical)
    return frozenset(matched)


def _score_pair(text: str) -> tuple[int, int] | None:
    match = _SCORE_RE.search(text)
    if match is None:
        return None
    left, right = (int(value) for value in match.groups())
    return tuple(sorted((left, right)))


def _day(text: str) -> int | None:
    match = _DAY_RE.search(text)
    if match is None:
        return None
    return int(match.group(1))


def _locations(text: str) -> frozenset[str]:
    folded = text.casefold()
    return frozenset(
        canonical
        for canonical, aliases in _LOCATION_ALIASES.items()
        if any(alias.casefold() in folded for alias in aliases)
    )


def _winning_team(text: str, teams: frozenset[str]) -> str | None:
    normalized = " ".join(text.split())
    if len(teams) != 2 or not normalized:
        return None
    win_surface = "|".join(re.escape(cue) for cue in _WIN_CUES)
    for team in sorted(teams):
        team_aliases = sorted(_KBO_TEAM_ALIASES[team], key=len, reverse=True)
        opponent_aliases = [
            alias
            for opponent in teams
            if opponent != team
            for alias in sorted(_KBO_TEAM_ALIASES[opponent], key=len, reverse=True)
        ]
        for team_alias in team_aliases:
            for opponent_alias in opponent_aliases:
                pattern = (
                    rf"{re.escape(team_alias)}(?:은|는|이|가|,)?"
                    rf"[^.!?。！？]{{0,90}}?{re.escape(opponent_alias)}"
                    rf"(?:을|를|와|과|에게|에|,)?[^.!?。！？]{{0,50}}?"
                    rf"(?:{win_surface})"
                )
                if re.search(pattern, normalized, flags=re.IGNORECASE):
                    return team
    return None


def _losing_team(text: str, teams: frozenset[str]) -> str | None:
    normalized = " ".join(text.split())
    if len(teams) != 2 or not normalized:
        return None
    loss_surface = "|".join(re.escape(cue) for cue in _LOSS_CUES)
    for team in sorted(teams):
        team_aliases = sorted(_KBO_TEAM_ALIASES[team], key=len, reverse=True)
        opponent_aliases = [
            alias
            for opponent in teams
            if opponent != team
            for alias in sorted(_KBO_TEAM_ALIASES[opponent], key=len, reverse=True)
        ]
        for team_alias in team_aliases:
            for opponent_alias in opponent_aliases:
                pattern = (
                    rf"{re.escape(team_alias)}(?:은|는|이|가|,)?"
                    rf"[^.!?。！？]{{0,180}}?{re.escape(opponent_alias)}"
                    rf"[^.!?。！？]{{0,120}}?(?:{loss_surface})"
                )
                if re.search(pattern, normalized, flags=re.IGNORECASE):
                    return team
    return None


def _resolved_winner(text: str, teams: frozenset[str]) -> str | None:
    winner = _winning_team(text, teams)
    if winner is not None:
        return winner
    loser = _losing_team(text, teams)
    if loser is None:
        return None
    return next((team for team in teams if team != loser), None)


def same_game_result_fingerprint(left_text: str, right_text: str) -> bool:
    """Recognize one KBO final-result event across winner/loser perspective changes.

    This is only a retrieval/identity anchor. It never declares a merge by itself. Both texts must
    explicitly name the same two KBO teams, carry the same reciprocal score, the same day, a shared
    stadium/city anchor, and an outcome predicate. Date/location conflicts therefore remain hard
    contradictions in the canonical identity layer.
    """

    left = " ".join(left_text.split())
    right = " ".join(right_text.split())
    if not left or not right:
        return False

    left_teams = _team_set(left)
    right_teams = _team_set(right)
    if len(left_teams) != 2 or left_teams != right_teams or "한화" not in left_teams:
        return False

    left_score = _score_pair(left)
    right_score = _score_pair(right)
    if left_score is None or left_score != right_score:
        return False

    left_day = _day(left)
    right_day = _day(right)
    if left_day is None or left_day != right_day:
        return False

    if not (_locations(left) & _locations(right)):
        return False

    return any(cue in left for cue in _OUTCOME_CUES) and any(cue in right for cue in _OUTCOME_CUES)


def kbo_visible_result_redundant(
    *,
    prior_headline: str,
    prior_summary: str,
    candidate_headline: str,
    candidate_summary: str,
) -> bool:
    """Suppress a redundant visible KBO result without broad semantic collapsing.

    The prior and candidate must name the same two-team Hanwha matchup, resolve to the same winner,
    and share a stadium/city anchor. Conflicting explicit days block suppression. A scored prior may
    suppress a generic candidate, and reciprocal scored winner/loser reports may collapse only when
    their score pairs agree. Opposite winners, score conflicts, different opponents, or different
    venues remain separate.
    """

    prior = " ".join(f"{prior_headline} {prior_summary}".split())
    candidate = " ".join(f"{candidate_headline} {candidate_summary}".split())
    prior_teams = _team_set(prior)
    candidate_teams = _team_set(candidate)
    if (
        len(prior_teams) != 2
        or prior_teams != candidate_teams
        or "한화" not in prior_teams
    ):
        return False

    prior_locations = _locations(prior)
    candidate_locations = _locations(candidate)
    if not prior_locations or not candidate_locations or not (prior_locations & candidate_locations):
        return False

    prior_day = _day(prior)
    candidate_day = _day(candidate)
    if prior_day is not None and candidate_day is not None and prior_day != candidate_day:
        return False

    prior_winner = _resolved_winner(prior_summary, prior_teams) or _resolved_winner(
        prior_headline, prior_teams
    )
    candidate_winner = _resolved_winner(candidate_summary, candidate_teams) or _resolved_winner(
        candidate_headline, candidate_teams
    )
    if prior_winner is None or prior_winner != candidate_winner:
        return False

    prior_score = _score_pair(prior)
    candidate_score = _score_pair(candidate)
    if prior_score is None:
        return False
    if candidate_score is None:
        return True
    return prior_score == candidate_score
