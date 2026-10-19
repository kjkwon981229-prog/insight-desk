from __future__ import annotations

import unittest
from datetime import datetime
from typing import Any

from insight_desk.curation.card_generation import build_card, build_prompt, CARD_SCHEMA
from insight_desk.curation.scoring import ScoreResult
from insight_desk.curation.grounding import CardLine


def _make_score() -> ScoreResult:
    return ScoreResult(
        q1=3, q2=0, q3=0,
        base_total=3, adjust=0.0, total=3.0,
        top_question="q1", passed=True, reasons=(),
    )


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


class FakeClient:
    def __init__(self, response: dict[str, Any] | None = None, error: Exception | None = None):
        self._response = response
        self._error = error
        self.call_kwargs: dict[str, Any] | None = None

    def structured_json(self, **kwargs: Any) -> dict[str, Any]:
        self.call_kwargs = kwargs
        if self._error:
            raise self._error
        assert self._response is not None
        return self._response


class TestBuildCard(unittest.TestCase):
    def _body(self) -> str:
        return (
            "삼성전자 매출이 10% 증가했다. "
            "영업이익도 크게 늘었다. "
            "신제품 출시가 예정되어 있다."
        )

    def _good_response(self) -> dict[str, Any]:
        return {
            "lines": [
                {"text": "삼성전자 매출 10% 증가", "evidence": [0]},
                {"text": "영업이익 확대", "evidence": [1]},
                {"text": "신제품 출시 예정", "evidence": [2]},
            ]
        }

    def test_first_error_second_ok(self):
        c1 = FakeClient(error=RuntimeError("fail"))
        c2 = FakeClient(response=self._good_response())
        result = build_card(
            title="테스트", body=self._body(), topic_label="경제",
            score=_make_score(), now=datetime(2025, 1, 1),
            clients=[c1, c2], noun_extractor=fake_noun_extractor,
        )
        self.assertEqual(result.status, "ok")
        self.assertIsNotNone(result.card)
        self.assertEqual(result.code, "ok")

    def test_all_error(self):
        c1 = FakeClient(error=RuntimeError("fail"))
        c2 = FakeClient(error=ValueError("fail"))
        result = build_card(
            title="테스트", body=self._body(), topic_label="경제",
            score=_make_score(), now=datetime(2025, 1, 1),
            clients=[c1, c2], noun_extractor=fake_noun_extractor,
        )
        self.assertEqual(result.status, "unavailable")
        self.assertIsNone(result.card)
        self.assertEqual(result.code, "provider_error")

    def test_bad_number_rejected(self):
        resp = {
            "lines": [
                {"text": "삼성전자 매출 99% 증가", "evidence": [0]},
                {"text": "영업이익 확대", "evidence": [1]},
                {"text": "신제품 출시 예정", "evidence": [2]},
            ]
        }
        c1 = FakeClient(response=resp)
        result = build_card(
            title="테스트", body=self._body(), topic_label="경제",
            score=_make_score(), now=datetime(2025, 1, 1),
            clients=[c1], noun_extractor=fake_noun_extractor,
        )
        self.assertEqual(result.status, "rejected")
        self.assertIn("grounding:", result.code)

    def test_no_client(self):
        result = build_card(
            title="테스트", body=self._body(), topic_label="경제",
            score=_make_score(), now=datetime(2025, 1, 1),
            clients=[], noun_extractor=fake_noun_extractor,
        )
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.code, "no_client")
        self.assertIsNone(result.card)

    def test_budget_exhausted(self):
        times = [0.0, 200.0]
        clock = lambda: times.pop(0) if times else 200.0
        c1 = FakeClient(response=self._good_response())
        result = build_card(
            title="테스트", body=self._body(), topic_label="경제",
            score=_make_score(), now=datetime(2025, 1, 1),
            clients=[c1], noun_extractor=fake_noun_extractor,
            clock=clock, budget_seconds=120.0,
        )
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.code, "budget_exhausted")

    def test_too_few_sentences(self):
        result = build_card(
            title="테스트", body="짧다.", topic_label="경제",
            score=_make_score(), now=datetime(2025, 1, 1),
            clients=[FakeClient(response=self._good_response())],
            noun_extractor=fake_noun_extractor,
        )
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.code, "too_few_sentences")


class TestBuildPrompt(unittest.TestCase):
    def test_contains_rules(self):
        prompt = build_prompt(
            title="테스트",
            sentences=["첫 번째 문장입니다.", "두 번째 문장입니다."],
            topic_label="경제",
        )
        self.assertIn("[0]", prompt)
        self.assertIn("[1]", prompt)
        self.assertIn("금지", prompt)
        self.assertIn("한국어", prompt)

    def test_keyword_call(self):
        c = FakeClient(response={
            "lines": [
                {"text": "삼성전자 매출 10% 증가", "evidence": [0]},
                {"text": "영업이익 확대", "evidence": [1]},
                {"text": "신제품 출시 예정", "evidence": [2]},
            ]
        })
        body = "삼성전자 매출이 10% 증가했다. 영업이익도 크게 늘었다. 신제품 출시가 예정되어 있다."
        build_card(
            title="테스트", body=body, topic_label="경제",
            score=_make_score(), now=datetime(2025, 1, 1),
            clients=[c], noun_extractor=fake_noun_extractor,
        )
        self.assertIsNotNone(c.call_kwargs)
        self.assertIn("prompt", c.call_kwargs)
        self.assertIn("schema", c.call_kwargs)
        self.assertIn("schema_name", c.call_kwargs)
        self.assertEqual(c.call_kwargs["schema_name"], "insight_desk_card_lines")


if __name__ == "__main__":
    unittest.main()
