from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import unittest

from insight_desk.core import EventUnderstandingRequest, SourceDocument
from insight_desk.event_understanding_adapter_v2 import build_event_understanding_prompt


PUBLICATION_TIME = datetime(2026, 8, 27, 0, 15, tzinfo=timezone.utc)
BODY = "한국은행 금융통화위원회는 27일 회의를 열어 기준금리를 결정한다."


def source() -> SourceDocument:
    return SourceDocument(
        source_id="source:temporal-handoff",
        candidate_ids=("candidate:temporal-handoff",),
        publisher="example-news",
        url="https://example.com/temporal-handoff",
        title="한국은행 27일 기준금리 결정",
        body=BODY,
        fetched_at=PUBLICATION_TIME,
        publication_time=PUBLICATION_TIME,
        retrieved_via="fixture",
        content_sha256=hashlib.sha256(BODY.encode("utf-8")).hexdigest(),
    )


class EventUnderstandingAdapterContractAuditV2Tests(unittest.TestCase):
    def test_source_publication_time_is_part_of_semantic_handoff(self) -> None:
        src = source()
        prompt = build_event_understanding_prompt(
            EventUnderstandingRequest(
                topic="economy",
                semantic_scope="Current monetary-policy events.",
                sources=(src,),
            )
        )
        self.assertIn("PUBLICATION_TIME:", prompt)
        self.assertIn(PUBLICATION_TIME.isoformat(), prompt)
        self.assertIn("SOURCE_PUBLISHER: example-news", prompt)
        self.assertIn("SOURCE_URL: https://example.com/temporal-handoff", prompt)


if __name__ == "__main__":
    unittest.main()
