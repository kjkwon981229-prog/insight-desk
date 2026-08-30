from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
from dataclasses import dataclass, field
from pathlib import Path
import unittest

from insight_desk.core import VerificationCheck
from insight_desk.semantic import judge_same_event_mutual_entailment


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "tests" / "fixtures" / "phase12_story_replay_corpus.json"


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _runs() -> list[dict[str, object]]:
    manifest = _manifest()
    fields = tuple(manifest["card_fields"])
    runs: list[dict[str, object]] = []
    for item in manifest["chunk_files"]:
        path = MANIFEST_PATH.parent / item["path"]
        self_bytes = path.read_bytes()
        if hashlib.sha256(self_bytes).hexdigest() != item["sha256"]:
            raise AssertionError(f"corpus chunk hash mismatch: {path}")
        chunk = json.loads(self_bytes)
        if tuple(chunk["fields"]) != fields:
            raise AssertionError(f"corpus field schema mismatch: {path}")
        for raw_run in chunk["runs"]:
            run_number, artifact_kind, zip_sha, html_sha, cards = raw_run
            runs.append({
                "run": run_number,
                "artifact_kind": artifact_kind,
                "artifact_zip_sha256": zip_sha,
                "html_sha256": html_sha,
                "cards": [dict(zip(fields, raw, strict=True)) for raw in cards],
            })
    return runs


def _cards():
    for run in _runs():
        for card in run["cards"]:
            yield run["run"], card


@dataclass
class _FakeVerifier:
    verifier_id: str
    model_id: str
    answers: list[bool | None] = field(default_factory=list)

    def verify(self, *, check_id: str, claim_text: str, evidence_text: str, evidence_ids: tuple[str, ...]) -> VerificationCheck:
        del claim_text, evidence_text
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


class StructuralReplayCorpusContract(unittest.TestCase):
    def test_corpus_is_exactly_the_verified_193_to_237_marker_productions(self) -> None:
        manifest = _manifest()
        self.assertEqual(
            manifest["scope"]["daily_runs"],
            [193, 196, 199, 203, 206, 209, 212, 215, 218, 221, 224, 227, 230, 234, 237],
        )
        self.assertEqual(manifest["counts"], {
            "runs": 15,
            "cards": 126,
            "p1": 64,
            "pass": 61,
            "admission_unresolved": 1,
            "source_unresolved": 3,
        })
        self.assertEqual(manifest["label_verification"]["status"], "VERIFIED")
        self.assertEqual(manifest["label_verification"]["exact_historical_regression_p1"], 57)
        self.assertEqual(manifest["label_verification"]["retroactive_structural_p1"], 7)
        self.assertEqual(manifest["label_verification"]["human_review_pass"], 61)
        self.assertEqual(manifest["label_verification"]["admission_unresolved"], 1)
        runs = _runs()
        self.assertEqual([run["run"] for run in runs], manifest["scope"]["daily_runs"])
        self.assertEqual(sum(len(run["cards"]) for run in runs), 126)
        verdicts = {"PASS": 0, "P1": 0, "AUDIT_UNRESOLVED": 0}
        for run in runs:
            self.assertRegex(run["artifact_zip_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(run["html_sha256"], r"^[0-9a-f]{64}$")
            for card in run["cards"]:
                self.assertRegex(card["source_content_sha256"], r"^[0-9a-f]{64}$")
                self.assertIn(card["verdict"], verdicts)
                verdicts[card["verdict"]] += 1
        self.assertEqual(verdicts, {"PASS": 61, "P1": 64, "AUDIT_UNRESOLVED": 1})

    def test_unresolved_historical_card_is_fail_closed_for_replay(self) -> None:
        unresolved = [(run, card) for run, card in _cards() if card["verdict"] == "AUDIT_UNRESOLVED"]
        self.assertEqual(len(unresolved), 1)
        run, card = unresolved[0]
        self.assertEqual((run, card["i"]), (237, 5))
        self.assertFalse(card["expected_accepted"])
        self.assertEqual(card["source_verification"], "FORECAST_ATTRIBUTION_EXACT_SOURCE_UNRESOLVED")

    def test_rc20_fixture_uses_the_same_production_identity_api(self) -> None:
        case = _manifest()["rc20"]
        local = _FakeVerifier("local-nli", "mdeberta", [False, True])
        primary = _FakeVerifier("cloudflare", "failover", [True, False])
        result = judge_same_event_mutual_entailment(
            case["left_source_fact"], case["right_source_fact"], primary=primary, secondary=local,
        )
        self.assertIs(result.same_event, case["expected_same_event"])
        self.assertEqual(result.reason, case["expected_reason"])


class StructuralStoryAdmissionRedContract(unittest.TestCase):
    def _story_admission(self):
        self.assertIsNotNone(
            importlib.util.find_spec("insight_desk.story_admission"),
            "shared StoryAdmissionDecision module is required before production may resume",
        )
        return importlib.import_module("insight_desk.story_admission")

    def test_one_shared_story_admission_decision_exists(self) -> None:
        module = self._story_admission()
        self.assertTrue(hasattr(module, "StoryAdmissionDecision"))
        self.assertTrue(hasattr(module, "StoryAdmissionReason"))
        self.assertTrue(hasattr(module, "evaluate_story_admission"))

    def test_all_126_historical_cards_replay_through_one_decision(self) -> None:
        module = self._story_admission()
        evaluate = module.evaluate_story_admission
        for run, card in _cards():
            with self.subTest(run=run, card=card["i"]):
                decision = evaluate(
                    topic=card["topic"], headline=card["headline"], summary=card["summary"], source_text=card["summary"],
                )
                self.assertEqual(decision.accepted, card["expected_accepted"], f"run {run} card {card['i']}: {card['headline']}")
                if card["verdict"] == "P1":
                    expected_reasons = set(card["reasons"])
                    actual_reasons = {reason.value for reason in decision.reasons}
                    self.assertTrue(expected_reasons <= actual_reasons, f"missing reasons: {expected_reasons - actual_reasons}")

    def test_material_generation_production_visible_and_validator_share_the_decision(self) -> None:
        required = {
            "insight_desk/semantic/material.py": "evaluate_story_admission(",
            "insight_desk/generation.py": "evaluate_story_admission(",
            "insight_desk/feed_quality.py": "evaluate_story_admission(",
            "scripts/phase11_daily_production.py": "evaluate_story_admission(",
            "scripts/validate_feed_artifact.py": "evaluate_story_admission(",
        }
        for relative, needle in required.items():
            with self.subTest(path=relative):
                source = (ROOT / relative).read_text(encoding="utf-8")
                self.assertIn(needle, source)

    def test_duplicate_material_and_validator_admission_implementations_are_removed(self) -> None:
        material = (ROOT / "insight_desk/semantic/material.py").read_text(encoding="utf-8")
        validator = (ROOT / "scripts/validate_feed_artifact.py").read_text(encoding="utf-8")
        for legacy in ("def _context_dependent_fragment(", "def _explicit_past_year_event(", "def _dated_context_is_stale("):
            with self.subTest(material_legacy=legacy):
                self.assertNotIn(legacy, material)
        for legacy in (
            "def _stale_sports_retrospective_summary(", "def _stale_explicit_past_year_summary(", "def _stale_dated_context_summary(",
            "_KBO_HEADLINE_SCOPE_CUES =", "_KBO_ENTERTAINMENT_ENTITY_CUES =", "_KBO_ENTERTAINMENT_ACTION_CUES =",
        ):
            with self.subTest(validator_legacy=legacy):
                self.assertNotIn(legacy, validator)


if __name__ == "__main__":
    unittest.main()
