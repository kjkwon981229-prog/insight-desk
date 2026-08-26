from __future__ import annotations

from .baseball_identity import (
    kbo_visible_lineup_redundant,
    kbo_visible_result_redundant,
    same_game_result_fingerprint,
)
from .market_identity import same_market_session_close_fingerprint
from .statistical_identity import same_statistical_release_fingerprint


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

    The gate remains narrower than general event identity. KBO results, starting lineups, and market
    closes are resolved from visible surfaces. KBO final results and official statistical releases may
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
        return bool(
            prior_source_text
            and candidate_source_text
            and same_statistical_release_fingerprint(prior_source_text, candidate_source_text)
        )

    return False
