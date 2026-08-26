from __future__ import annotations

from .baseball_identity import kbo_visible_result_redundant
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

    The gate remains narrower than general event identity. KBO results and market closes are resolved
    from visible surfaces. Official statistical releases may additionally use exact source provenance
    when generation erased the release label from one child fact. The source-backed path still requires
    the same actor, reference month, and exact multi-token statistical release label; it never performs
    fuzzy matching and does not alter the Phase 6 semantic-verification contract.
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
