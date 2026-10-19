from __future__ import annotations

import unittest

from insight_desk.curation.grounding import CardLine, check_format, check_grounding


def fake_noun_extractor(text: str) -> frozenset[str]:
    words = set()
    current = []
    for ch in text:
        if '\uac00' <= ch <= '\ud7a3':
            current.append(ch)
        else:
            if current:
                words.add("".join(current))
                current = []
    if current:
        words.add("".join(current))
    return frozenset(w for w in words if len(w) >= 2)


class TestCheckFormat(unittest.TestCase):
    def test_ok(self):
        lines = [
            CardLine("매출 10% 증가", (0,)),
            CardLine("영업이익 확대 전망", (1,)),
            CardLine("신제품 출시 예정", (2,)),
        ]
        result = check_format(lines, 3)
        self.assertTrue(result.ok)
        self.assertEqual(result.code, "ok")

    def test_wrong_count(self):
        lines = [CardLine("한 줄", (0,))]
        result = check_format(lines, 3)
        self.assertFalse(result.ok)
        self.assertIn("line_count", result.code)

    def test_too_short(self):
        lines = [
            CardLine("abc", (0,)),
            CardLine("정상 길이입니다", (1,)),
            CardLine("정상 길이입니다", (2,)),
        ]
        result = check_format(lines, 3)
        self.assertFalse(result.ok)
        self.assertIn("length", result.code)

    def test_finite_verb(self):
        lines = [
            CardLine("매출이 증가했다", (0,)),
            CardLine("영업이익 확대", (1,)),
            CardLine("신제품 출시", (2,)),
        ]
        result = check_format(lines, 3)
        self.assertFalse(result.ok)
        self.assertIn("finite_verb", result.code)

    def test_period_end(self):
        lines = [
            CardLine("매출 증가.", (0,)),
            CardLine("영업이익 확대", (1,)),
            CardLine("신제품 출시", (2,)),
        ]
        result = check_format(lines, 3)
        self.assertFalse(result.ok)
        self.assertIn("period_end", result.code)

    def test_evidence_range(self):
        lines = [
            CardLine("매출 증가", (5,)),
            CardLine("영업이익 확대", (1,)),
            CardLine("신제품 출시", (2,)),
        ]
        result = check_format(lines, 3)
        self.assertFalse(result.ok)
        self.assertIn("evidence_range", result.code)

    def test_evidence_dup(self):
        lines = [
            CardLine("매출 증가", (0, 0)),
            CardLine("영업이익 확대", (1,)),
            CardLine("신제품 출시", (2,)),
        ]
        result = check_format(lines, 3)
        self.assertFalse(result.ok)
        self.assertIn("evidence_dup", result.code)


class TestCheckGrounding(unittest.TestCase):
    def test_ok(self):
        sentences = ["삼성전자 매출이 10% 증가했다.", "영업이익도 크게 늘었다.", "신제품 출시가 예정되어 있다."]
        lines = [
            CardLine("삼성전자 매출 10% 증가", (0,)),
            CardLine("영업이익 확대", (1,)),
            CardLine("신제품 출시 예정", (2,)),
        ]
        result = check_grounding(lines, sentences, noun_extractor=fake_noun_extractor)
        self.assertTrue(result.ok)

    def test_number_missing(self):
        sentences = ["매출이 증가했다."]
        lines = [
            CardLine("매출 50% 증가", (0,)),
            CardLine("영업이익 확대", (0,)),
            CardLine("신제품 출시", (0,)),
        ]
        result = check_grounding(lines, sentences, noun_extractor=fake_noun_extractor)
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "grounding:number")
        self.assertEqual(result.line_index, 0)

    def test_unit_mismatch(self):
        sentences = ["매출이 10% 증가했다."]
        lines = [
            CardLine("매출 10억 증가", (0,)),
            CardLine("영업이익 확대", (0,)),
            CardLine("신제품 출시", (0,)),
        ]
        result = check_grounding(lines, sentences, noun_extractor=fake_noun_extractor)
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "grounding:number")

    def test_latin_missing(self):
        sentences = ["Apple 매출이 증가했다."]
        lines = [
            CardLine("Samsung 매출 증가", (0,)),
            CardLine("영업이익 확대", (0,)),
            CardLine("신제품 출시", (0,)),
        ]
        result = check_grounding(lines, sentences, noun_extractor=fake_noun_extractor)
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "grounding:latin")

    def test_quote_missing(self):
        sentences = ["그는 '안녕'이라고 말했다."]
        lines = [
            CardLine("'반갑다'라고 발언", (0,)),
            CardLine("영업이익 확대", (0,)),
            CardLine("신제품 출시", (0,)),
        ]
        result = check_grounding(lines, sentences, noun_extractor=fake_noun_extractor)
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "grounding:quote")

    def test_nouns_low_match(self):
        sentences = ["날씨가 매우 좋다."]
        lines = [
            CardLine("경제성장률 물가지수 고용지표 개선", (0,)),
            CardLine("영업이익 확대", (0,)),
            CardLine("신제품 출시", (0,)),
        ]
        result = check_grounding(lines, sentences, noun_extractor=fake_noun_extractor)
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "grounding:nouns")

    def test_negation_dropped(self):
        sentences = ["행사가 취소되었다."]
        lines = [
            CardLine("행사 진행 예정", (0,)),
            CardLine("영업이익 확대", (0,)),
            CardLine("신제품 출시", (0,)),
        ]
        result = check_grounding(lines, sentences, noun_extractor=fake_noun_extractor)
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "grounding:negation_dropped")

    def test_negation_added(self):
        sentences = ["행사가 진행되었다."]
        lines = [
            CardLine("행사 진행 않음", (0,)),
            CardLine("영업이익 확대", (0,)),
            CardLine("신제품 출시", (0,)),
        ]
        # 명사 일치율이 아니라 부정 표지 검사가 먼저 걸리는 상황만 보기 위해 명사는 고정한다.
        result = check_grounding(lines, sentences, noun_extractor=lambda _text: frozenset({"행사"}))
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "grounding:negation")

    def test_english_weak(self):
        sentences = ["Revenue increased by 10% this quarter."]
        lines = [
            CardLine("Revenue 10% 증가", (0,)),
            CardLine("Revenue increased 확대", (0,)),
            CardLine("this quarter 실적", (0,)),
        ]
        result = check_grounding(lines, sentences, noun_extractor=fake_noun_extractor)
        self.assertTrue(result.ok)
        self.assertTrue(result.weak)


if __name__ == "__main__":
    unittest.main()
