from __future__ import annotations

import re

from .baseball_identity import (
    kbo_visible_lineup_redundant,
    kbo_visible_result_redundant,
    same_game_result_fingerprint,
)
from .market_identity import same_market_session_close_fingerprint
from .statistical_identity import same_statistical_release_fingerprint


_POLICY_DAY_RE = re.compile(r"(?<!\d)([1-9]|[12]\d|3[01])일")
_BOK_POLICY_ACTOR_RE = re.compile(r"(?:한국은행|한은|금융통화위원회|금통위)")
_ACTIVE_RATE_DECISION_RE = re.compile(
    r"(?:기준금리|정책금리)(?:를|을|는|가|의)?\s*"
    r"[^.!?。！？]{0,40}?"
    r"결정(?:한다|합니다|했다|했습니다|하며|하고|할|하기|할\s+예정)"
)


def _same_scheduled_bok_policy_decision(left_text: str, right_text: str) -> bool:
    """Identify child publications of one scheduled BOK rate-decision meeting.

    This is intentionally narrower than general monetary-policy similarity. Both source surfaces
    must name the Bank of Korea / Monetary Policy Board, actively describe a policy-rate decision,
    and carry exactly the same explicit calendar day. Outlook or dot-plot child facts may therefore
    collapse into the parent meeting, while same-day unrelated BOK releases remain distinct.
    """

    left = " ".join(left_text.split())
    right = " ".join(right_text.split())
    left_days = set(_POLICY_DAY_RE.findall(left))
    right_days = set(_POLICY_DAY_RE.findall(right))
    if len(left_days) != 1 or left_days != right_days:
        return False
    return all(
        _BOK_POLICY_ACTOR_RE.search(text) is not None
        and _ACTIVE_RATE_DECISION_RE.search(text) is not None
        for text in (left, right)
    )


def visible_event_redundant(
    *,
    topic_id: str,
    prior_headline: str,
    prior_summary: str,
    candidate_headline: str,
    candidate_summary: str,
    prior_source_text: str = "",
    candidate_source_text: str = "",
) -> bool:
    """Recognize only high-precision publication duplicates before semantic identity calls.

    The gate remains narrower than general event identity. KBO results, starting lineups, market
    closes, and scheduled BOK rate decisions are resolved from deterministic identity surfaces.
    KBO final results, official statistical releases, and scheduled monetary-policy meetings may
    additionally use exact source provenance when generation erased identity-bearing detail from one
    visible child fact. Source-backed paths remain deterministic and contradiction-sensitive; they do
    not alter the Phase 6 semantic-verification contract.
    """

    if topic_id == "kbo_hanwha":
        visible_duplicate = kbo_visible_lineup_redundant(
            prior_headline=prior_headline,
            prior_summary=prior_summary,
            candidate_headline=candidate_headline,
            candidate_summary=candidate_summary,
        ) or kbo_visible_result_redundant(
            prior_headline=prior_headline,
            prior_summary=prior_summary,
            candidate_headline=candidate_headline,
            candidate_summary=candidate_summary,
        )
        if visible_duplicate:
            return True
        return bool(
            prior_source_text
            and candidate_source_text
            and same_game_result_fingerprint(prior_source_text, candidate_source_text)
        )

    if topic_id == "economy":
        prior = " ".join(f"{prior_headline} {prior_summary}".split())
        candidate = " ".join(f"{candidate_headline} {candidate_summary}".split())
        if same_market_session_close_fingerprint(prior, candidate):
            return True
        if same_statistical_release_fingerprint(prior, candidate):
            return True
        if _same_scheduled_bok_policy_decision(prior, candidate):
            return True
        if not prior_source_text or not candidate_source_text:
            return False
        return (
            same_statistical_release_fingerprint(prior_source_text, candidate_source_text)
            or _same_scheduled_bok_policy_decision(prior_source_text, candidate_source_text)
        )

    return False
