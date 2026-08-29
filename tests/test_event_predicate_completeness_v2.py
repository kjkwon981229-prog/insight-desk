from __future__ import annotations

import unittest
from types import SimpleNamespace

from insight_desk.event_predicate_v2 import PredicateCompleteness, assess_event_predicate


class _Morphology:
    def __init__(self, tags: tuple[str, ...]) -> None:
        self.tags = tags

    def analyze(self, text: str):
        return tuple(SimpleNamespace(tag=tag, surface=part) for tag, part in zip(self.tags, text.split()))


class EventPredicateCompletenessTests(unittest.TestCase):
    def test_attributive_verb_followed_by_nominal_head_is_not_clause_complete(self) -> None:
        morphology = _Morphology(("VV", "ETM", "NNG"))
        result = assess_event_predicate("가중되는 상황", morphology=morphology)
        self.assertIs(result.completeness, PredicateCompleteness.INCOMPLETE)
        self.assertEqual(result.reason, "attributive_nominal_description")

    def test_finite_event_clause_is_complete(self) -> None:
        morphology = _Morphology(("VV", "EP", "EF"))
        result = assess_event_predicate("기준금리를 올렸다", morphology=morphology)
        self.assertIs(result.completeness, PredicateCompleteness.COMPLETE)

    def test_progressive_finite_clause_is_complete(self) -> None:
        morphology = _Morphology(("VV", "EC", "VX", "EF"))
        result = assess_event_predicate("영향을 미치고 있다", morphology=morphology)
        self.assertIs(result.completeness, PredicateCompleteness.COMPLETE)

    def test_missing_morphology_is_unresolved_not_fabricated(self) -> None:
        result = assess_event_predicate("발표했다", morphology=None)
        self.assertIs(result.completeness, PredicateCompleteness.UNRESOLVED)


if __name__ == "__main__":
    unittest.main()
