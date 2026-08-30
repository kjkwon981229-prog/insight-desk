from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from insight_desk.core import FailureKind
from insight_desk.providers.transport import ProviderTransportError
from scripts import qualify_event_understanding_provider_v4 as qualification


def _event(*, actor: str, action: str, evidence: str, participants=(), parent_hint: str = ""):
    return {
        "article_role": "primary",
        "topic_relation": "direct",
        "understanding_status": "resolved",
        "actor": actor,
        "action": action,
        "object": "",
        "event_type": "fixture_event",
        "event_time": "",
        "participants": list(participants),
        "metric": "",
        "unit": "",
        "value": "",
        "attribution": "",
        "parent_event_hint": parent_hint,
        "uncertainty_reasons": [],
        "evidence": [
            {
                "source_id": "__SOURCE_ID__",
                "field": "body",
                "text": evidence,
            }
        ],
    }


class _PassingV4Client:
    model_id = "fixture-v4-model"

    def __init__(self) -> None:
        self.calls = 0
        self.schemas = []

    def structured_json(self, *, prompt, schema, schema_name, system_prompt):
        self.calls += 1
        self.schemas.append(schema)
        source_id = next(
            line.removeprefix("SOURCE_ID: ")
            for line in prompt.splitlines()
            if line.startswith("SOURCE_ID: ")
        )
        body = prompt.split("BODY:\n", 1)[1]
        if "수정 경제전망" in body:
            events = [
                _event(
                    actor="한국은행",
                    action="기준금리를 결정한다",
                    evidence=body,
                    parent_hint="금융통화위원회 회의",
                ),
                _event(
                    actor="한국은행",
                    action="수정 경제전망과 점도표를 공개한다",
                    evidence=body,
                    parent_hint="금융통화위원회 회의",
                ),
            ]
        elif "음악방송 무대를 최초 공개한다" in body:
            events = [
                _event(
                    actor="알파드라이브원",
                    action="음악방송 무대를 최초 공개한다",
                    evidence=body,
                )
            ]
        elif "6-1로 제압" in body:
            events = [
                _event(
                    actor="SSG 랜더스",
                    action="한화 이글스를 6-1로 제압했다",
                    evidence=body,
                    participants=("한화 이글스",),
                )
            ]
        else:
            events = [
                _event(
                    actor="한국은행",
                    action="기준금리를 결정한다",
                    evidence=body,
                )
            ]
        for event in events:
            event["evidence"][0]["source_id"] = source_id
        return {"status": "resolved", "uncertainty_reasons": [], "events": events}


class _TransientV4Client:
    model_id = "fixture-v4-transient"

    def structured_json(self, **kwargs):
        raise ProviderTransportError(failure_kind=FailureKind.TRANSIENT_PROVIDER)


class EventUnderstandingQualificationRunnerV4Tests(unittest.TestCase):
    def test_default_v4_runner_scores_all_four_frozen_cases_without_provider_offsets(self) -> None:
        client = _PassingV4Client()
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            with (
                patch.object(qualification, "_provider_configured", return_value=True),
                patch.object(
                    qualification,
                    "_provider_client",
                    return_value=(client, client.model_id),
                ),
            ):
                code = qualification.qualify(
                    provider="mistral",
                    qualification_path=qualification.DEFAULT_QUALIFICATION,
                    scopes_path=qualification.DEFAULT_SCOPES,
                    report_path=report,
                )
            payload = json.loads(report.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(client.calls, 4)
        self.assertEqual(payload["status"], "MINIMUM_COMPATIBILITY_PASS")
        self.assertEqual(payload["qualification_protocol"], 4)
        self.assertEqual(payload["structured_output_schema"], "event_understanding_schema_v3")
        self.assertEqual(payload["evaluated_cases"], 4)
        self.assertEqual(payload["passed_cases"], 4)
        self.assertTrue(all(item["passed"] for item in payload["cases"]))
        for schema in client.schemas:
            evidence = schema["properties"]["events"]["items"]["properties"]["evidence"]["items"]
            self.assertEqual(evidence["required"], ["source_id", "field", "text"])
            self.assertNotIn("start", evidence["properties"])
            self.assertNotIn("end", evidence["properties"])

    def test_v4_runner_preserves_transient_lifecycle(self) -> None:
        client = _TransientV4Client()
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            with (
                patch.object(qualification, "_provider_configured", return_value=True),
                patch.object(
                    qualification,
                    "_provider_client",
                    return_value=(client, client.model_id),
                ),
            ):
                code = qualification.qualify(
                    provider="mistral",
                    qualification_path=qualification.DEFAULT_QUALIFICATION,
                    scopes_path=qualification.DEFAULT_SCOPES,
                    report_path=report,
                )
            payload = json.loads(report.read_text(encoding="utf-8"))

        self.assertEqual(code, 3)
        self.assertEqual(payload["status"], "QUALIFICATION_BLOCKED_TRANSIENT")
        self.assertEqual(payload["qualification_protocol"], 4)
        self.assertEqual(payload["evaluated_cases"], 4)
        self.assertEqual(payload["passed_cases"], 0)
        self.assertEqual(
            {failure for case in payload["cases"] for failure in case["failures"]},
            {"provider_transport:transient_provider"},
        )

    def test_v4_runner_missing_credentials_is_not_configured_without_cases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            with patch.object(qualification, "_provider_configured", return_value=False):
                code = qualification.qualify(
                    provider="mistral",
                    qualification_path=qualification.DEFAULT_QUALIFICATION,
                    scopes_path=qualification.DEFAULT_SCOPES,
                    report_path=report,
                )
            payload = json.loads(report.read_text(encoding="utf-8"))

        self.assertEqual(code, 2)
        self.assertEqual(payload["status"], "NOT_CONFIGURED")
        self.assertEqual(payload["qualification_protocol"], 4)
        self.assertEqual(payload["structured_output_schema"], "event_understanding_schema_v3")
        self.assertEqual(payload["evaluated_cases"], 0)
        self.assertEqual(payload["passed_cases"], 0)


if __name__ == "__main__":
    unittest.main()
