from __future__ import annotations

import os
import urllib.error
from urllib.parse import parse_qs, urlparse
import unittest
from unittest.mock import patch

from insight_desk.api.kosis import KosisClient
from insight_desk.api.transport import HttpResponse


class SequenceTransport:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0
        self.urls: list[str] = []

    def request(self, method, url, headers, body=None, timeout=20.0):
        self.calls += 1
        self.urls.append(url)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _statistics(client: KosisClient) -> object:
    return client.statistics(
        org_id="101",
        table_id="DT_TEST",
        object_l1="ALL",
        item_id="T1",
        period_type="M",
        max_periods=1,
    )


class KosisTransportResilienceTests(unittest.TestCase):
    def test_generated_json_parameter_contract_includes_jsonvd(self) -> None:
        transport = SequenceTransport([HttpResponse(status=200, body=b"[]", headers={})])
        client = KosisClient("key", transport=transport)
        with patch.dict(os.environ, {}, clear=True):
            client.statistics(
                org_id="101",
                table_id="DT_1J22001",
                object_l1="T10",
                object_l2="0",
                item_id="T",
                period_type="M",
                max_periods=1,
            )

        self.assertEqual(transport.calls, 1)
        query = parse_qs(urlparse(transport.urls[0]).query, keep_blank_values=True)
        self.assertEqual(
            set(query),
            {
                "method",
                "apiKey",
                "format",
                "jsonVD",
                "orgId",
                "tblId",
                "objL1",
                "objL2",
                "itmId",
                "prdSe",
                "newEstPrdCnt",
            },
        )
        self.assertEqual(query["jsonVD"], ["Y"])
        self.assertNotIn("outputFields", query)
        self.assertEqual(query["orgId"], ["101"])
        self.assertEqual(query["tblId"], ["DT_1J22001"])
        self.assertEqual(query["objL1"], ["T10"])
        self.assertEqual(query["objL2"], ["0"])
        self.assertEqual(query["itmId"], ["T"])
        self.assertEqual(query["prdSe"], ["M"])
        self.assertEqual(query["newEstPrdCnt"], ["1"])

    def test_explicit_output_fields_use_kosis_selector_contract(self) -> None:
        transport = SequenceTransport([HttpResponse(status=200, body=b"[]", headers={})])
        KosisClient("key", transport=transport).statistics(
            org_id="101",
            table_id="DT_1J22001",
            object_l1="T10",
            object_l2="0",
            item_id="T",
            period_type="M",
            max_periods=1,
            output_fields=("ORG_ID", "TBL_ID", "TBL_NM", "PRD_DE", "DT"),
        )
        query = parse_qs(urlparse(transport.urls[0]).query, keep_blank_values=True)
        self.assertEqual(query["jsonVD"], ["Y"])
        self.assertEqual(query["outputFields"], ["ORG_ID TBL_ID TBL_NM PRD_DE DT"])

    def test_marked_probe_fields_do_not_change_unmarked_runtime_field_shape(self) -> None:
        marked_fields = "ORG_ID TBL_ID TBL_NM ITM_ID ITM_NM UNIT_NM PRD_SE PRD_DE DT"
        marked = SequenceTransport([HttpResponse(status=200, body=b"[]", headers={})])
        with patch.dict(
            os.environ,
            {"INSIGHT_DESK_KOSIS_PROBE_OUTPUT_FIELDS": marked_fields},
            clear=True,
        ):
            _statistics(KosisClient("key", transport=marked))
        marked_query = parse_qs(urlparse(marked.urls[0]).query, keep_blank_values=True)
        self.assertEqual(marked_query["jsonVD"], ["Y"])
        self.assertEqual(marked_query["outputFields"], [marked_fields])

        unmarked = SequenceTransport([HttpResponse(status=200, body=b"[]", headers={})])
        with patch.dict(os.environ, {}, clear=True):
            _statistics(KosisClient("key", transport=unmarked))
        unmarked_query = parse_qs(urlparse(unmarked.urls[0]).query, keep_blank_values=True)
        self.assertEqual(unmarked_query["jsonVD"], ["Y"])
        self.assertNotIn("outputFields", unmarked_query)

    def test_transient_url_error_is_retried_then_success_is_returned(self) -> None:
        transport = SequenceTransport(
            [
                urllib.error.URLError("temporary DNS failure"),
                HttpResponse(status=200, body=b"[]", headers={}),
            ]
        )
        payload = _statistics(KosisClient("key", transport=transport))
        self.assertEqual(payload, [])
        self.assertEqual(transport.calls, 2)

    def test_transport_failure_remains_fail_closed_after_bounded_attempts(self) -> None:
        transport = SequenceTransport(
            [urllib.error.URLError("temporary failure") for _ in range(3)]
        )
        with self.assertRaises(urllib.error.URLError):
            _statistics(KosisClient("key", transport=transport))
        self.assertEqual(transport.calls, 3)

    def test_http_failure_is_not_retried(self) -> None:
        transport = SequenceTransport(
            [HttpResponse(status=503, body=b"{}", headers={})]
        )
        with self.assertRaisesRegex(RuntimeError, "KOSIS HTTP 503"):
            _statistics(KosisClient("key", transport=transport))
        self.assertEqual(transport.calls, 1)

    def test_retry_budget_cannot_be_zero(self) -> None:
        transport = SequenceTransport([])
        with self.assertRaisesRegex(ValueError, "transport_attempts"):
            _statistics(KosisClient("key", transport=transport, transport_attempts=0))
        self.assertEqual(transport.calls, 0)


if __name__ == "__main__":
    unittest.main()
