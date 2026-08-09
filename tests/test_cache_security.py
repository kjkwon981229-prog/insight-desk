from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from insight_desk.collectors.cache import ResponseCache
from insight_desk.security import redact_mapping


class CacheSecurityTests(unittest.TestCase):
    def test_cache_key_and_payload_exclude_headers(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="insight-desk-cache-"))
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        cache = ResponseCache(root / "responses.json")
        key = cache.key("GET", "https://naverapihub.apigw.ntruss.com/search/v1/news?query=AI", None)
        cache.set(key, {"items": [{"title": "공개 결과"}]})
        self.assertEqual(cache.get(key), {"items": [{"title": "공개 결과"}]})
        text = (root / "responses.json").read_text(encoding="utf-8")
        self.assertNotIn("X-NCP-APIGW-API-KEY", text)

    def test_mapping_redacts_sensitive_keys(self) -> None:
        value = redact_mapping({"NCP_CLIENT_SECRET": "secret", "nested": {"token": "value", "ok": 1}})
        self.assertEqual(value["NCP_CLIENT_SECRET"], "[REDACTED]")
        self.assertEqual(value["nested"]["token"], "[REDACTED]")
