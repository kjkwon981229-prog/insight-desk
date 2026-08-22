from __future__ import annotations

import unittest

from dataset import build_cases
from provider_contract import schema_for
from score import _equivalent


class BenchmarkFairnessTests(unittest.TestCase):
    def test_every_direct_gold_field_is_emittable_by_its_task_schema(self) -> None:
        cases = build_cases()
        self.assertEqual(len(cases), 85)
        for case in cases:
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

    def test_action_allows_more_specific_supported_phrase(self) -> None:
        self.assertTrue(_equivalent("action", "공식 선정", "선정"))
        self.assertTrue(_equivalent("action", "기준금리 추가 인상 가능성 언급", "추가 인상"))
        self.assertFalse(_equivalent("action", "해지", "선정"))

    def test_categorical_fields_remain_exact(self) -> None:
        self.assertTrue(_equivalent("temporal_state", "PLANNED", "PLANNED"))
        self.assertFalse(_equivalent("temporal_state", "COMPLETED", "PLANNED"))
        self.assertFalse(_equivalent("event_type", "ANNOUNCEMENT", "INDUSTRY_CHANGE"))


if __name__ == "__main__":
    unittest.main()
