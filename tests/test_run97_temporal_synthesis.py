from __future__ import annotations

import unittest

from insight_desk.pipeline.semantics import EventFact
from insight_desk.pipeline.synthesis import _event_relation_summary, _relation_headline


def _relation(subject: str, object_text: str, action: str) -> EventFact:
    return EventFact(
        "EVENT_RELATION",
        object_text,
        subject=subject,
        relation=action,
        object=object_text,
    )


class Run97TemporalSynthesisTests(unittest.TestCase):
    def test_groundbreaking_future_does_not_become_completed(self) -> None:
        summary = _event_relation_summary(
            "SK하이닉스, 미국 인디애나 HBM 패키징 공장 착공식",
            "SK하이닉스가 27일 착공식을 연다.",
            _relation("SK하이닉스", "미국 인디애나 HBM 패키징 공장", "착공"),
        )
        self.assertIn("27일", summary)
        self.assertIn("착공 예정이다", summary)
        self.assertNotIn("들어갔다", summary)

    def test_groundbreaking_completed_stays_completed(self) -> None:
        summary = _event_relation_summary(
            "SK하이닉스, 미국 인디애나 HBM 패키징 공장 착공식",
            "SK하이닉스가 착공식을 열었다.",
            _relation("SK하이닉스", "미국 인디애나 HBM 패키징 공장", "착공"),
        )
        self.assertIn("착공에 들어갔다", summary)
        self.assertNotIn("예정", summary)

    def test_departure_announcement_stays_prospective_and_uses_particle(self) -> None:
        summary = _event_relation_summary(
            "트와이스 채영, 14년 만에 JYP 떠난다",
            "트와이스 채영이 떠난다고 밝혔다.",
            _relation("트와이스 채영", "JYP", "떠남"),
        )
        self.assertIn("JYP를 떠난다고 밝혔다", summary)
        self.assertNotIn("떠났다", summary)
        self.assertNotIn("JYP을", summary)

    def test_departure_completed_stays_completed(self) -> None:
        summary = _event_relation_summary(
            "트와이스 채영, JYP 떠남",
            "트와이스 채영이 떠났다.",
            _relation("트와이스 채영", "JYP", "떠남"),
        )
        self.assertIn("JYP를 떠났다", summary)
        self.assertNotIn("예정", summary)

    def test_investment_planned_does_not_become_completed(self) -> None:
        summary = _event_relation_summary(
            "A사, AI 사업 투자",
            "A사가 투자하기로 했다.",
            _relation("A사", "AI 사업", "투자"),
        )
        self.assertIn("투자할 예정이다", summary)
        self.assertNotIn("투자했다", summary)

    def test_investment_completed_stays_completed(self) -> None:
        summary = _event_relation_summary(
            "A사, AI 사업 투자",
            "A사가 투자했다.",
            _relation("A사", "AI 사업", "투자"),
        )
        self.assertIn("투자했다", summary)
        self.assertNotIn("예정", summary)

    def test_relation_headline_keeps_material_object_context(self) -> None:
        groundbreaking = _relation("SK하이닉스", "미국 인디애나 HBM 패키징 공장", "착공")
        selection = _relation("코팅솔루션포유", "NVIDIA 협업 프로그램", "선정")
        groundbreaking_headline = _relation_headline(groundbreaking)
        selection_headline = _relation_headline(selection)
        self.assertIn("인디애나", groundbreaking_headline)
        self.assertIn("HBM 패키징 공장", groundbreaking_headline)
        self.assertNotEqual(groundbreaking_headline, "SK하이닉스, 공장 착공")
        self.assertIn("NVIDIA 협업 프로그램", selection_headline)
        self.assertNotEqual(selection_headline, "코팅솔루션포유, 프로그램 선정")


if __name__ == "__main__":
    unittest.main()
