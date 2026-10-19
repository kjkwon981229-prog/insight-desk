from __future__ import annotations

import unittest
from datetime import datetime, timezone
from typing import Any

from insight_desk.curation.card_generation import build_card
from insight_desk.curation.config import CurationConfig
from insight_desk.curation.scoring import ScoreResult
from insight_desk.curation.selection import Scored, select_daily

NOW = datetime(2026, 10, 19, 1, 0, tzinfo=timezone.utc)
BODY = "삼성전자 매출이 10% 증가했다. 영업이익도 크게 늘었다. 신제품 출시가 예정되어 있다."
SCORE = ScoreResult(
    q1=3, q2=3, q3=1, base_total=7, adjust=0.0, total=7.0, top_question="q1", passed=True, reasons=()
)


def nouns(text: str) -> frozenset[str]:
    return frozenset(word for word in "".join(c if "가" <= c <= "힣" else " " for c in text).split() if len(word) >= 2)


GOOD = {
    "lines": [
        {"text": "삼성전자 매출 10% 증가", "evidence": [0]},
        {"text": "영업이익 확대", "evidence": [1]},
        {"text": "신제품 출시 예정", "evidence": [2]},
    ]
}
BAD_NUMBER = {
    "lines": [
        {"text": "삼성전자 매출 50% 증가", "evidence": [0]},
        {"text": "영업이익 확대", "evidence": [1]},
        {"text": "신제품 출시 예정", "evidence": [2]},
    ]
}


class ScriptedClient:
    def __init__(self, *answers: Any) -> None:
        self.answers = list(answers)
        self.prompts: list[str] = []

    def structured_json(self, **kwargs: Any) -> dict[str, Any]:
        self.prompts.append(kwargs["prompt"])
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


class CardRetryTests(unittest.TestCase):
    def _build(self, *clients: ScriptedClient):
        return build_card(
            title="삼성전자 실적", body=BODY, topic_label="경제", score=SCORE, now=NOW,
            clients=list(clients), noun_extractor=nouns,
        )

    def test_failed_check_gets_one_repair_retry_with_the_reason(self) -> None:
        client = ScriptedClient(BAD_NUMBER, GOOD)
        result = self._build(client)
        self.assertEqual(result.status, "ok")
        self.assertEqual(len(client.prompts), 2)
        self.assertNotIn("탈락", client.prompts[0])
        self.assertIn("탈락", client.prompts[1])
        self.assertIn("숫자", client.prompts[1])

    def test_still_failing_after_the_repair_is_rejected_not_unavailable(self) -> None:
        client = ScriptedClient(BAD_NUMBER, BAD_NUMBER)
        result = self._build(client)
        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.code, "grounding:number")
        self.assertTrue(result.reason)

    def test_provider_error_then_a_bad_answer_is_rejected(self) -> None:
        # 한 모델은 응답을 못 줬고 다른 모델은 답했지만 원문과 맞지 않았다 -> 사용 불가가 아니라 제외.
        result = self._build(ScriptedClient(RuntimeError("429")), ScriptedClient(BAD_NUMBER, BAD_NUMBER))
        self.assertEqual(result.status, "rejected")

    def test_unavailable_card_still_carries_the_deterministic_reason(self) -> None:
        result = self._build()
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.code, "no_client")
        self.assertIn("10%", result.reason)

    def test_provider_error_does_not_retry_the_same_client(self) -> None:
        client = ScriptedClient(RuntimeError("boom"))
        result = self._build(client)
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(len(client.prompts), 1)


class SelectionAcceptTests(unittest.TestCase):
    def test_refused_candidate_does_not_use_a_slot(self) -> None:
        cfg = CurationConfig(max_daily=2, max_per_topic=2)
        pool = [
            Scored(key="a", topic_id="t1", topic_priority=1, total=9.0),
            Scored(key="b", topic_id="t1", topic_priority=1, total=8.5),
            Scored(key="c", topic_id="t1", topic_priority=1, total=8.0),
            Scored(key="d", topic_id="t2", topic_priority=1, total=7.5),
        ]
        refused = {"a"}
        result = select_daily(pool, cfg=cfg, accept=lambda item: "card_rejected:x" if item.key in refused else None)
        self.assertEqual([item.key for item in result.selected], ["b", "c"])
        self.assertEqual([(item.key, why) for item, why in result.dropped], [("a", "card_rejected:x"), ("d", "daily_cap")])

    def test_accept_is_not_called_for_candidates_over_the_caps(self) -> None:
        cfg = CurationConfig(max_daily=1, max_per_topic=1)
        calls: list[str] = []
        pool = [
            Scored(key="a", topic_id="t1", topic_priority=1, total=9.0),
            Scored(key="b", topic_id="t1", topic_priority=1, total=8.0),
        ]
        select_daily(pool, cfg=cfg, accept=lambda item: calls.append(item.key))
        self.assertEqual(calls, ["a"])


if __name__ == "__main__":
    unittest.main()
