from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from insight_desk.collectors.cache import ResponseCache
from insight_desk.security import configured_secret_values, redact_mapping, scan_secret_values


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

    def test_secret_registry_preserves_the_full_union(self) -> None:
        values = configured_secret_values(
            "explicit-naver-id",
            "explicit-naver-secret",
            environment={
                "NCP_CLIENT_ID": "env-naver-id",
                "NCP_CLIENT_SECRET": "env-naver-secret",
                "OPENDART_API_KEY": "dart-key",
                "KOSIS_API_KEY": "kosis-key",
            },
        )
        self.assertEqual(
            values,
            (
                "env-naver-id",
                "env-naver-secret",
                "dart-key",
                "kosis-key",
                "explicit-naver-id",
                "explicit-naver-secret",
            ),
        )

    def test_secret_scan_covers_unlisted_generated_files(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="insight-desk-secret-tree-"))
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        (root / "data").mkdir()
        (root / "data" / "extra.json").write_text('{"value":"whole-tree-secret"}\n', encoding="utf-8")
        errors = scan_secret_values(root, ("whole-tree-secret",))
        self.assertEqual(errors, ("secret detected in generated tree: data/extra.json",))
