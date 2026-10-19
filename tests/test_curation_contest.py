from __future__ import annotations

import unittest
from datetime import date, datetime, timezone

from insight_desk.curation.contest import extract_deadline, verify_contest

NOW = datetime(2026, 10, 19, 1, 0, tzinfo=timezone.utc)


def _verdict(body: str, title: str = "제5회 대학생 영상 공모전"):
    return verify_contest(title=title, body=body, now=NOW)


class ContestVerificationTests(unittest.TestCase):
    def test_open_free_student_contest_passes(self) -> None:
        verdict = _verdict("대학생이면 누구나 참가할 수 있습니다. 접수 기간: 2026.10.15 ~ 2026.11.20 까지. 참가비 무료. 주제는 영상 디자인.")
        self.assertTrue(verdict.ok, verdict.reason)
        self.assertEqual(verdict.deadline, date(2026, 11, 20))
        self.assertEqual(verdict.days_left, 32)

    def test_deadline_passed(self) -> None:
        verdict = _verdict("대학생 대상 영상 공모전. 접수 마감: 2026년 10월 10일")
        self.assertEqual(verdict.reason, "contest_deadline_passed")

    def test_deadline_under_seven_days(self) -> None:
        verdict = _verdict("대학생 대상 영상 공모전. 접수 마감: 10월 25일")
        self.assertEqual(verdict.reason, "contest_deadline_under_7d")

    def test_exactly_seven_days_left_passes(self) -> None:
        verdict = _verdict("대학생 대상 영상 공모전. 접수 마감: 10월 26일 까지")
        self.assertTrue(verdict.ok, verdict.reason)

    def test_no_deadline_is_unverified(self) -> None:
        self.assertEqual(_verdict("대학생 영상 공모전을 연다.").reason, "contest_unverified")

    def test_paid_entry_is_rejected(self) -> None:
        verdict = _verdict("대학생 대상 영상 공모전. 접수 마감 11월 30일. 참가비 20,000원 결제 필요")
        self.assertEqual(verdict.reason, "benefit_costs_money")

    def test_free_wording_is_not_cost(self) -> None:
        verdict = _verdict("대학생 대상 영상 공모전. 접수 마감 11월 30일. 참가비 무료")
        self.assertTrue(verdict.ok, verdict.reason)

    def test_non_student_contest_is_ineligible(self) -> None:
        verdict = _verdict("직장인 대상 영상 공모전. 접수 마감 11월 30일.", title="직장인 영상 공모전")
        self.assertEqual(verdict.reason, "contest_ineligible")

    def test_unrelated_field_is_rejected(self) -> None:
        verdict = _verdict("대학생 대상 요리 레시피 대회. 접수 마감 11월 30일.", title="대학생 요리 대회")
        self.assertEqual(verdict.reason, "contest_not_related")

    def test_year_end_deadline_rolls_to_next_year(self) -> None:
        deadline = extract_deadline("접수 마감 1월 5일", date(2026, 12, 20))
        self.assertEqual(deadline, date(2027, 1, 5))

    def test_latest_marked_date_is_the_deadline(self) -> None:
        deadline = extract_deadline("접수 2026.11.01 ~ 2026.11.30 / 시상식 2026.12.20", date(2026, 10, 19))
        self.assertEqual(deadline, date(2026, 11, 30))


if __name__ == "__main__":
    unittest.main()
