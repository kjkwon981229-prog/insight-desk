from __future__ import annotations

import json
import os
import unittest
from unittest.mock import MagicMock, patch

import providers
from provider_contract import TASK_SCHEMAS, prompt_for


CASE = {
    "id": "contract-test",
    "task": "MATERIAL_EVENT",
    "input": {"title": "A사, AI 사업단 신설", "lead": "A사가 AI 사업단을 신설했다."},
}

OUTPUT = {
    "is_material_event": True,
    "event_type": "INDUSTRY_CHANGE",
    "action": "신설",
    "polarity": "POSITIVE",
    "temporal_state": "COMPLETED",
}


class ProviderContractTests(unittest.TestCase):
    def test_all_strict_schemas_are_closed_and_fully_required(self) -> None:
        for task, schema in TASK_SCHEMAS.items():
            with self.subTest(task=task):
                self.assertFalse(schema["additionalProperties"])
                self.assertEqual(set(schema["properties"]), set(schema["required"]))

    def test_prompt_contains_case_input_but_not_gold(self) -> None:
        rendered = prompt_for(CASE)
        self.assertIn("A사, AI 사업단 신설", rendered)
        self.assertNotIn("INDUSTRY_CHANGE", rendered)

    @patch("providers.urllib.request.urlopen")
    def test_http_transport_sets_explicit_api_client_headers(self, urlopen) -> None:
        response = MagicMock()
        response.read.return_value = b"{}"
        urlopen.return_value.__enter__.return_value = response

        providers._post_json(
            "https://example.invalid/api",
            {"hello": "world"},
            {"Authorization": "Bearer test"},
            attempts=1,
        )

        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("User-agent"), "insight-desk-bakeoff/0.1")
        self.assertEqual(request.get_header("Accept"), "application/json")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(request.get_header("Authorization"), "Bearer test")

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}, clear=False)
    @patch("providers._post_json")
    def test_groq_uses_strict_schema(self, post_json) -> None:
        post_json.return_value = {
            "choices": [{"message": {"content": json.dumps(OUTPUT, ensure_ascii=False)}}]
        }
        actual = providers.call_groq20(CASE)
        self.assertEqual(actual, OUTPUT)
        payload = post_json.call_args.args[1]
        self.assertEqual(payload["model"], "openai/gpt-oss-20b")
        self.assertTrue(payload["response_format"]["json_schema"]["strict"])
        self.assertEqual(
            payload["response_format"]["json_schema"]["schema"],
            TASK_SCHEMAS["MATERIAL_EVENT"],
        )

    @patch.dict(
        os.environ,
        {"CLOUDFLARE_ACCOUNT_ID": "account", "CLOUDFLARE_API_TOKEN": "test-token"},
        clear=False,
    )
    @patch("providers._post_json")
    def test_cloudflare_uses_json_schema_mode(self, post_json) -> None:
        post_json.return_value = {"success": True, "result": {"response": OUTPUT}}
        actual = providers.call_cloudflare(CASE)
        self.assertEqual(actual, OUTPUT)
        url = post_json.call_args.args[0]
        payload = post_json.call_args.args[1]
        self.assertIn("@cf/deepseek-ai/deepseek-r1-distill-qwen-32b", url)
        self.assertEqual(payload["response_format"]["type"], "json_schema")
        self.assertEqual(payload["response_format"]["json_schema"], TASK_SCHEMAS["MATERIAL_EVENT"])

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False)
    @patch("providers._post_json")
    def test_gemini_uses_structured_output_schema(self, post_json) -> None:
        post_json.return_value = {
            "candidates": [
                {"content": {"parts": [{"text": json.dumps(OUTPUT, ensure_ascii=False)}]}}
            ]
        }
        actual = providers.call_gemini(CASE)
        self.assertEqual(actual, OUTPUT)
        url = post_json.call_args.args[0]
        payload = post_json.call_args.args[1]
        self.assertIn("gemini-3.7-flash:generateContent", url)
        text_format = payload["generationConfig"]["responseFormat"]["text"]
        self.assertEqual(text_format["mimeType"], "application/json")
        self.assertEqual(text_format["schema"], TASK_SCHEMAS["MATERIAL_EVENT"])


if __name__ == "__main__":
    unittest.main()
