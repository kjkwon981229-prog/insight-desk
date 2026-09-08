from __future__ import annotations

import unittest

from insight_desk.core import (
    VerificationCheck,
    VerificationPolicy,
    VerificationVerdict,
    aggregate_verdict,
)


POLICY = VerificationPolicy(
    primary_verifier_id="cloudflare_workers_ai_free",
    secondary_verifier_id="local_mdeberta_nli",
)


def check(check_id: str, verifier_id: str, entailed: bool | None) -> VerificationCheck:
    return VerificationCheck(
        check_id=check_id,
        verifier_id=verifier_id,
        model_id="model",
        evidence_ids=("evidence-1",),
        entailed=entailed,
        error_code="PROVIDER_UNAVAILABLE" if entailed is None else None,
    )


class VerificationPolicyTests(unittest.TestCase):
    def test_two_positive_independent_checks_support_claim(self) -> None:
        verdict = aggregate_verdict(
            (
                check("primary", "cloudflare_workers_ai_free", True),
                check("secondary", "local_mdeberta_nli", True),
            ),
            POLICY,
        )
        self.assertEqual(verdict, VerificationVerdict.SUPPORTED)

    def test_primary_rejection_rejects_claim(self) -> None:
        verdict = aggregate_verdict(
            (
                check("primary", "cloudflare_workers_ai_free", False),
                check("secondary", "local_mdeberta_nli", True),
            ),
            POLICY,
        )
        self.assertEqual(verdict, VerificationVerdict.REJECTED)

    def test_disagreement_is_indeterminate_not_supported(self) -> None:
        verdict = aggregate_verdict(
            (
                check("primary", "cloudflare_workers_ai_free", True),
                check("secondary", "local_mdeberta_nli", False),
            ),
            POLICY,
        )
        self.assertEqual(verdict, VerificationVerdict.INDETERMINATE)

    def test_primary_outage_is_indeterminate_even_if_secondary_is_positive(self) -> None:
        verdict = aggregate_verdict(
            (
                check("primary", "cloudflare_workers_ai_free", None),
                check("secondary", "local_mdeberta_nli", True),
            ),
            POLICY,
        )
        self.assertEqual(verdict, VerificationVerdict.INDETERMINATE)

    def test_missing_secondary_is_not_enough_to_publish(self) -> None:
        verdict = aggregate_verdict(
            (check("primary", "cloudflare_workers_ai_free", True),),
            POLICY,
        )
        self.assertEqual(verdict, VerificationVerdict.INDETERMINATE)

    def test_duplicate_verifier_results_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            aggregate_verdict(
                (
                    check("primary-1", "cloudflare_workers_ai_free", True),
                    check("primary-2", "cloudflare_workers_ai_free", True),
                ),
                POLICY,
            )


if __name__ == "__main__":
    unittest.main()
