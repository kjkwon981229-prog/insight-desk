from __future__ import annotations

from .baseball_identity import kbo_visible_result_redundant
from .market_identity import same_market_session_close_fingerprint


def visible_event_redundant(
    *,
    topic_id: str,
    prior_headline: str,
    prior_summary: str,
    candidate_headline: str,
    candidate_summary: str,
) -> bool:
    """Recognize only high-precision visible duplicates before semantic identity calls.

    This publication gate is intentionally narrower than general event identity. It handles two
    measured perspective-only duplicates whose visible surfaces already contain enough explicit
    evidence to resolve the repeated event: reciprocal KBO final results and one domestic market
    close described once by a named index and once as the broad market. It never performs fuzzy
    matching and does not alter the Phase 6 semantic-verification contract.
    """

    if topic_id == "kbo_hanwha":
        return kbo_visible_result_redundant(
            prior_headline=prior_headline,
            prior_summary=prior_summary,
            candidate_headline=candidate_headline,
            candidate_summary=candidate_summary,
        )

    if topic_id == "economy":
        prior = " ".join(f"{prior_headline} {prior_summary}".split())
        candidate = " ".join(f"{candidate_headline} {candidate_summary}".split())
        return same_market_session_close_fingerprint(prior, candidate)

    return False
