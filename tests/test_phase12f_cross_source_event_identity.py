from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import unittest

from insight_desk.core import VerificationCheck
from insight_desk.semantic import judge_same_event_mutual_entailment


@dataclass
class FakeVerifier:
    verifier_id: str
    model_id: str
    answers: list[bool | None] = field(default_factory=list)
    calls: int = 0

    def verify(
        self,
        *,
        check_id: str,
        claim_text: str,
        evidence_text: str,
        evidence_ids: tuple[str, ...],
    ) -> VerificationCheck:
        del claim_text, evidence_text
        self.calls += 1
        answer = self.answers.pop(0) if self.answers else None
        return VerificationCheck(
            check_id=check_id,
            verifier_id=self.verifier_id,
            model_id=self.model_id,
            evidence_ids=evidence_ids,
            entailed=answer,
            error_code=None if answer is not None else "synthetic_unavailable",
            zero_cost=True,
        )


LEFT = "23일 대전에서 LG 트윈스가 한화 이글스를 12-3으로 이겼다."
RIGHT = "프로야구 LG 트윈스는 23일 대전 한화전에서 12-3 대승을 거뒀다."


class CrossSourceEventIdentityTests(unittest.TestCase):
    def test_same_event_requires_bidirectional_support_from_both_independent_slots(self) -> None:
        local = FakeVerifier("local-nli", "mdeberta", [True, True])
        primary = FakeVerifier("cloudflare", "failover", [True, True])
        result = judge_same_event_mutual_entailment(
            LEFT,
            RIGHT,
            primary=primary,
            secondary=local,
        )
        self.assertIs(result.same_event, True)
        self.assertEqual(result.secondary_checks, 2)
        self.assertEqual(result.primary_checks, 2)
        self.assertEqual(local.calls, 2)
        self.assertEqual(primary.calls, 2)

    def test_local_negative_short_circuits_external_identity_calls(self) -> None:
        local = FakeVerifier("local-nli", "mdeberta", [False])
        primary = FakeVerifier("cloudflare", "failover", [True, True])
        result = judge_same_event_mutual_entailment(
            "LG가 한화를 12-3으로 이겼다.",
            "LG가 한화전 선발 투수를 발표했다.",
            primary=primary,
            secondary=local,
        )
        self.assertIs(result.same_event, False)
        self.assertEqual(local.calls, 1)
        self.assertEqual(primary.calls, 0)

    def test_local_unavailable_keeps_events_separate_without_external_spend(self) -> None:
        local = FakeVerifier("local-nli", "mdeberta", [None])
        primary = FakeVerifier("cloudflare", "failover", [True, True])
        result = judge_same_event_mutual_entailment(
            LEFT,
            RIGHT,
            primary=primary,
            secondary=local,
        )
        self.assertIsNone(result.same_event)
        self.assertEqual(local.calls, 1)
        self.assertEqual(primary.calls, 0)

    def test_primary_unavailable_after_local_support_keeps_events_separate(self) -> None:
        local = FakeVerifier("local-nli", "mdeberta", [True, True])
        primary = FakeVerifier("cloudflare", "failover", [None])
        result = judge_same_event_mutual_entailment(
            LEFT,
            RIGHT,
            primary=primary,
            secondary=local,
        )
        self.assertIsNone(result.same_event)
        self.assertEqual(local.calls, 2)
        self.assertEqual(primary.calls, 1)

    def test_production_consumes_event_identity_before_visible_slot(self) -> None:
        source = Path("scripts/phase11_daily_production.py").read_text(encoding="utf-8")
        self.assertIn("judge_same_event_mutual_entailment", source)
        self.assertIn('stage="event_identity"', source)
        self.assertIn('reason="cross_source_same_event_already_published"', source)
        self.assertIn('"identity_stats": identity_stats', source)
        self.assertLess(
            source.index('reason="cross_source_same_event_already_published"'),
            source.index("published.append("),
        )


if __name__ == "__main__":
    unittest.main()
