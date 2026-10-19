from __future__ import annotations

import unittest

from insight_desk.curation.sentences import split_sentences


class TestSplitSentences(unittest.TestCase):
    def test_basic_split(self):
        body = "첫 번째 문장입니다. 두 번째 문장입니다! 세 번째 문장입니까?"
        result = split_sentences(body)
        self.assertEqual(len(result), 3)
        self.assertTrue(result[0].startswith("첫 번째"))
        self.assertTrue(result[1].startswith("두 번째"))
        self.assertTrue(result[2].startswith("세 번째"))

    def test_decimal_not_split(self):
        body = "물가가 3.2 퍼센트 상승했습니다. 이는 큰 폭입니다."
        result = split_sentences(body)
        self.assertTrue(any("3.2" in s for s in result))

    def test_abbreviation_not_split(self):
        body = "U.S. 정부가 새로운 정책을 발표했습니다. 이는 중요합니다."
        result = split_sentences(body)
        self.assertTrue(any("U.S." in s for s in result))

    def test_quote_period_not_split(self):
        body = '그는 "안녕하세요." 라고 말했습니다. 그리고 떠났습니다.'
        result = split_sentences(body)
        self.assertTrue(any('"안녕하세요."' in s for s in result))

    def test_short_sentence_removed(self):
        body = "짧다. 이것은 충분히 긴 문장입니다. ok."
        result = split_sentences(body)
        for s in result:
            self.assertGreaterEqual(len(s), 8)

    def test_max_sentences(self):
        body = ". ".join(f"이것은 테스트 문장 번호 {i} 입니다" for i in range(50))
        result = split_sentences(body, max_sentences=5)
        self.assertLessEqual(len(result), 5)

    def test_max_chars(self):
        body = ". ".join(f"이것은 테스트 문장 번호 {i} 입니다" for i in range(100))
        result = split_sentences(body, max_chars=100)
        total = sum(len(s) for s in result)
        self.assertLessEqual(total, 200)

    def test_duplicate_removal(self):
        body = "같은 문장입니다. 같은 문장입니다. 다른 문장입니다."
        result = split_sentences(body)
        count = sum(1 for s in result if "같은 문장입니다" in s)
        self.assertEqual(count, 1)

    def test_newline_split(self):
        body = "첫 번째 줄입니다.\n두 번째 줄입니다."
        result = split_sentences(body)
        self.assertEqual(len(result), 2)

    def test_empty_body(self):
        self.assertEqual(split_sentences(""), ())


if __name__ == "__main__":
    unittest.main()
