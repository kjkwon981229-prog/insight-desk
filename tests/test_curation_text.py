from __future__ import annotations

import unittest

from insight_desk.curation.text import content_words, jaccard, normalize


class TestNormalize(unittest.TestCase):
    def test_lowercase_and_spaces(self):
        self.assertEqual(normalize("  Hello   WORLD  "), "hello world")

    def test_nfkc(self):
        self.assertEqual(normalize("\uff21"), "a")


class TestContentWords(unittest.TestCase):
    def test_stopwords_removed(self):
        words = content_words("그리고 하지만 있다 했다 한다 이번 지난 관련 대한 통해 위해")
        self.assertEqual(words, frozenset())

    def test_english_stopwords(self):
        words = content_words("the and for with that this")
        self.assertEqual(words, frozenset())

    def test_josa_removal(self):
        words = content_words("경제는 시장이 데이터를 분석으로")
        self.assertIn("경제", words)
        self.assertIn("시장", words)
        self.assertIn("데이터", words)
        self.assertIn("분석", words)
        self.assertNotIn("경제는", words)

    def test_short_words_excluded(self):
        words = content_words("a i b")
        self.assertEqual(words, frozenset())

    def test_english_lowercase(self):
        words = content_words("Baseball ANALYSIS Data")
        self.assertIn("baseball", words)
        self.assertIn("analysis", words)
        self.assertIn("data", words)


class TestJaccard(unittest.TestCase):
    def test_both_empty(self):
        self.assertEqual(jaccard(frozenset(), frozenset()), 0.0)

    def test_identical(self):
        s = frozenset({"a", "b"})
        self.assertEqual(jaccard(s, s), 1.0)

    def test_partial(self):
        a = frozenset({"a", "b", "c"})
        b = frozenset({"b", "c", "d"})
        self.assertAlmostEqual(jaccard(a, b), 2 / 4)


if __name__ == "__main__":
    unittest.main()
