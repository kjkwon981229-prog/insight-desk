from __future__ import annotations

import json
import unittest
from datetime import date
from urllib.parse import parse_qs, urlsplit

from insight_desk.collectors.naver import BASE_URL, NEWS_PATH, TREND_PATH, NaverApiClient, NaverCredentials
from insight_desk.collectors.transport import HttpResponse
from insight_desk.domain.models import KeywordGroup


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, str], bytes | None]] = []

    def request(self, method, url, headers, body=None, timeout=20.0):
        self.calls.append((method, url, headers, body))
        if method == "GET":
            payload = {"items": []}
        else:
            payload = {"results": []}
        return HttpResponse(200, json.dumps(payload).encode("utf-8"), {})


class NaverContractTests(unittest.TestCase):
    def test_endpoint_and_header_contract(self) -> None:
        transport = FakeTransport()
        client = NaverApiClient(NaverCredentials("id-secret", "secret-value"), transport=transport)
        client.search_news("AI")
        client.search_trend(
            [KeywordGroup("g", "t", "AI", ("AI",))],
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 9),
        )
        self.assertEqual(transport.calls[0][0], "GET")
        self.assertTrue(transport.calls[0][1].startswith(BASE_URL + NEWS_PATH))
        self.assertEqual(transport.calls[1][0], "POST")
        self.assertEqual(transport.calls[1][1], BASE_URL + TREND_PATH)
        self.assertEqual(transport.calls[0][2]["X-NCP-APIGW-API-KEY-ID"], "id-secret")
        self.assertEqual(transport.calls[0][2]["X-NCP-APIGW-API-KEY"], "secret-value")
        self.assertNotIn("id-secret", transport.calls[0][1])
        self.assertNotIn("secret-value", transport.calls[1][3].decode())

    def test_news_sort_channel_is_sent_without_secret_data(self) -> None:
        transport = FakeTransport()
        client = NaverApiClient(NaverCredentials("id-secret", "secret-value"), transport=transport)
        client.search_news("AI", display=3, sort="sim")
        client.search_news("AI", display=2, sort="date")
        sorts = [parse_qs(urlsplit(call[1]).query)["sort"][0] for call in transport.calls]
        self.assertEqual(sorts, ["sim", "date"])
