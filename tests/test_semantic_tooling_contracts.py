from __future__ import annotations

import importlib.util
import unittest

from insight_desk.semantic import (
    AliasCandidate,
    KiwiMorphologyHelper,
    MorphologyToken,
    RapidFuzzAliasRetriever,
)


HAS_KIWI = importlib.util.find_spec("kiwipiepy") is not None
HAS_RAPIDFUZZ = importlib.util.find_spec("rapidfuzz") is not None


class SemanticToolingContractTests(unittest.TestCase):
    def test_morphology_token_requires_valid_exact_source_span(self) -> None:
        token = MorphologyToken("정부", "정부", "NNG", 0, 2)
        self.assertEqual((token.start, token.end), (0, 2))
        with self.assertRaises(ValueError):
            MorphologyToken("정부", "정부", "NNG", 2, 2)

    def test_alias_candidate_score_is_bounded(self) -> None:
        self.assertEqual(AliasCandidate("SK하이닉스", 100.0, 0).score, 100.0)
        with self.assertRaises(ValueError):
            AliasCandidate("SK하이닉스", 100.1, 0)

    @unittest.skipUnless(HAS_KIWI, "semantic-local optional dependency not installed")
    def test_kiwi_preserves_source_offsets_without_claiming_ner_authority(self) -> None:
        text = "잠실 한화 왕옌청 두산 곽빈 선발투수 예고"
        tokens = KiwiMorphologyHelper().analyze(text)
        self.assertTrue(tokens)
        for token in tokens:
            self.assertEqual(token.surface, text[token.start : token.end])
        for name in ("왕옌청", "곽빈"):
            start = text.index(name)
            end = start + len(name)
            covered = {
                index
                for token in tokens
                for index in range(max(start, token.start), min(end, token.end))
            }
            self.assertEqual(covered, set(range(start, end)))

    @unittest.skipUnless(HAS_RAPIDFUZZ, "semantic-local optional dependency not installed")
    def test_rapidfuzz_retrieves_candidates_but_does_not_decide_identity(self) -> None:
        retriever = RapidFuzzAliasRetriever()
        results = retriever.retrieve(
            "SK하이닉스",
            ("SK하이닉스", "SK 하이닉스", "두산 베어스"),
            limit=3,
        )
        self.assertEqual(results[0].value, "SK하이닉스")
        self.assertEqual(results[0].score, 100.0)
        self.assertGreater(results[1].score, results[2].score)


if __name__ == "__main__":
    unittest.main()
