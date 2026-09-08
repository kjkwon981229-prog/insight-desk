from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import unittest

from insight_desk.core import VerificationCheck
from insight_desk.semantic import judge_same_event_mutual_entailment
from insight_desk.semantic.identity import has_strong_shared_event_anchor


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
LS_LONG = (
    "LS일렉트릭이 북미 빅테크 기업과 체결한 인공지능 AI 데이터센터 전력설비 공급계약 "
    "규모를 2배 이상 확대했다. 6월 계약서 물량은 1064억원으로 납기 경쟁력을 강화한다."
)
LS_SHORT = (
    "LS일렉트릭이 미국 빅테크 기업과 맺은 인공지능 데이터센터 전력설비 공급 계약 "
    "규모를 기존 1064억원에서 2309억원으로 두 배 이상 늘렸다."
)


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

    def test_live_ls_contract_pair_has_strong_shared_event_anchor(self) -> None:
        self.assertTrue(has_strong_shared_event_anchor(LS_LONG, LS_SHORT))

    def test_live_ls_contract_detail_asymmetry_can_still_resolve_same_event(self) -> None:
        local = FakeVerifier("local-nli", "mdeberta", [False, True])
        primary = FakeVerifier("cloudflare", "failover", [True, False])
        result = judge_same_event_mutual_entailment(
            LS_LONG,
            LS_SHORT,
            primary=primary,
            secondary=local,
        )
        self.assertIs(result.same_event, True)
        self.assertEqual(
            result.reason,
            "strong_shared_event_anchor_with_independent_asymmetric_support",
        )
        self.assertEqual(result.secondary_checks, 2)
        self.assertEqual(result.primary_checks, 2)

    def test_shared_company_and_number_without_event_anchor_does_not_relax_negative(self) -> None:
        left = "LS일렉트릭이 1064억원 규모의 AI 데이터센터 전력설비 공급계약을 확대했다."
        right = "LS일렉트릭이 1064억원을 투입해 부산 공장 생산라인을 증설한다고 발표했다."
        self.assertFalse(has_strong_shared_event_anchor(left, right))
        local = FakeVerifier("local-nli", "mdeberta", [False])
        primary = FakeVerifier("cloudflare", "failover", [True, True])
        result = judge_same_event_mutual_entailment(
            left,
            right,
            primary=primary,
            secondary=local,
        )
        self.assertIs(result.same_event, False)
        self.assertEqual(local.calls, 1)
        self.assertEqual(primary.calls, 0)

    def test_strong_anchor_still_rejects_when_one_verifier_rejects_both_directions(self) -> None:
        local = FakeVerifier("local-nli", "mdeberta", [False, False])
        primary = FakeVerifier("cloudflare", "failover", [True, True])
        result = judge_same_event_mutual_entailment(
            LS_LONG,
            LS_SHORT,
            primary=primary,
            secondary=local,
        )
        self.assertIs(result.same_event, False)
        self.assertEqual(local.calls, 2)
        self.assertEqual(primary.calls, 0)

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
