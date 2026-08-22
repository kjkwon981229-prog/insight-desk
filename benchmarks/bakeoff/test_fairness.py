from __future__ import annotations

import unittest

from dataset import build_cases, build_deferred_selection_cases
from provider_contract import schema_for
from score import _equivalent


class BenchmarkFairnessTests(unittest.TestCase):
    def test_only_semantically_scoreable_cases_enter_hard_score(self) -> None:
        cases = build_cases()
        self.assertEqual(len(cases), 41)
        self.assertEqual(len(build_deferred_selection_cases()), 44)

    def test_every_direct_gold_field_is_emittable_by_its_task_schema(self) -> None:
        for case in build_cases():
            with self.subTest(case=case["id"]):
                properties = schema_for(case)["properties"]
                self.assertLessEqual(set(case["expected"]), set(properties))

    def test_every_enum_gold_value_is_allowed_by_the_schema(self) -> None:
        for case in build_cases():
            properties = schema_for(case)["properties"]
            for key, expected in case["expected"].items():
                enum = properties[key].get("enum")
                if enum is not None:
                    with self.subTest(case=case["id"], field=key):
                        self.assertIn(expected, enum)

    def test_evaluator_only_requirements_are_not_direct_gold(self) -> None:
        for case in build_cases():
            evaluator = case["constraints"].get("evaluator_requirements", {})
            with self.subTest(case=case["id"]):
                self.assertTrue(set(evaluator).isdisjoint(case["expected"]))

    def test_legacy_run96_selection_negatives_are_never_material_event_gold(self) -> None:
        deferred = build_deferred_selection_cases()
        self.assertEqual(len(deferred), 44)
        for case in deferred:
            with self.subTest(case=case["id"]):
                self.assertEqual(case["status"], "deferred_selection_evidence")
                self.assertNotIn("expected", case)
                self.assertNotIn("task", case)

    def test_legacy_event_type_is_not_exact_scored(self) -> None:
        run96_cases = [
            case for case in build_cases() if case["source_suite"] == "run96_recall_precision"
        ]
        self.assertEqual(len(run96_cases), 15)
        for case in run96_cases:
            with self.subTest(case=case["id"]):
                self.assertNotIn("event_type", case["expected"])
                self.assertIn("legacy_event_type", case["constraints"]["evaluator_requirements"])

    def test_action_allows_more_specific_supported_phrase(self) -> None:
        self.assertTrue(_equivalent("action", "공식 선정", "선정"))
        self.assertTrue(_equivalent("action", "기준금리 추가 인상 가능성 언급", "추가 인상"))
        self.assertFalse(_equivalent("action", "해지", "선정"))

    def test_categorical_fields_remain_exact_when_the_taxonomy_is_defined(self) -> None:
        self.assertTrue(_equivalent("temporal_state", "PLANNED", "PLANNED"))
        self.assertFalse(_equivalent("temporal_state", "COMPLETED", "PLANNED"))


if __name__ == "__main__":
    unittest.main()
