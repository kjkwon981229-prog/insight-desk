from __future__ import annotations

import unittest
from datetime import datetime

from insight_desk.curation.reasons import build_reason, reason_is_grounded
from insight_desk.curation.scoring import ScoreResult


def _make_score(top_question: int = 1) -> ScoreResult:
    return ScoreResult(
        q1=3 if top_question == 1 else 0,
        q2=3 if top_question == 2 else 0,
        q3=3 if top_question == 3 else 0,
        base_total=3,
        adjust=0.0,
        total=3.0,
        top_question=f"q{top_question}",
        passed=True,
        reasons=(),
    )


class TestBuildReason(unittest.TestCase):
    def test_q1_with_number(self):
        score = _make_score(1)
        reason = build_reason(
            score=score,
            topic_label="경제",
            title="테스트",
            body="매출이 500억원 증가했다.",
            now=datetime(2025, 1, 1),
        )
        self.assertIn("500억원", reason)
        self.assertLessEqual(len(reason), 100)

    def test_q1_record_word(self):
        score = _make_score(1)
        reason = build_reason(
            score=score,
            topic_label="스포츠",
            title="테스트",
            body="역대 최고 기록을 달성했다.",
            now=datetime(2025, 1, 1),
        )
        self.assertIn("기록", reason)
        self.assertLessEqual(len(reason), 100)

    def test_q2_topic(self):
        score = _make_score(2)
        reason = build_reason(
            score=score,
            topic_label="기술",
            title="테스트",
            body="새로운 기술이 나왔다.",
            now=datetime(2025, 1, 1),
        )
        self.assertIn("기술", reason)
        self.assertLessEqual(len(reason), 100)

    def test_q3_date(self):
        score = _make_score(3)
        now = datetime(2025, 1, 10)
        reason = build_reason(
            score=score,
            topic_label="이벤트",
            title="테스트",
            body="1월 15일에 행사가 열린다.",
            now=now,
        )
        self.assertIn("15일", reason)
        self.assertLessEqual(len(reason), 100)

    def test_length_limit(self):
        score = _make_score(1)
        reason = build_reason(
            score=score,
            topic_label="a" * 200,
            title="테스트",
            body="내용",
            now=datetime(2025, 1, 1),
        )
        self.assertLessEqual(len(reason), 100)


class TestReasonIsGrounded(unittest.TestCase):
    def test_grounded(self):
        self.assertTrue(reason_is_grounded("매출 500억 증가", "매출이 500억원 증가했다."))

    def test_ungrounded_number(self):
        self.assertFalse(reason_is_grounded("매출 999억 증가", "매출이 500억원 증가했다."))

    def test_quoted_word(self):
        self.assertTrue(reason_is_grounded("'최고' 기록", "역대 최고 기록 달성"))

    def test_quoted_word_missing(self):
        self.assertFalse(reason_is_grounded("'최악' 기록", "역대 최고 기록 달성"))

    def test_template_phrase_rejected(self):
        self.assertFalse(reason_is_grounded("새로 남는 것: 15억 같은 구체적 수치", "매출 15억"))

    def test_reason_uses_body_sentence_not_template(self):
        reason = build_reason(
            score=_make_score(1),
            topic_label="경제",
            title="한화 투자 소식",
            body="회사는 올해 영업이익이 15억원으로 늘었다고 밝혔다. 다른 문장이다.",
            now=datetime(2025, 1, 1),
        )
        self.assertNotIn("구체적 수치", reason)
        self.assertIn("영업이익이 15억원으로 늘었다고 밝혔다", reason)
        self.assertTrue(reason_is_grounded(reason, "회사는 올해 영업이익이 15억원으로 늘었다고 밝혔다. 다른 문장이다.", "한화 투자 소식"))

    def test_topic_label_excluded(self):
        self.assertTrue(reason_is_grounded("관심 분야(없는라벨)와 관련", "관련 내용"))


if __name__ == "__main__":
    unittest.main()
