from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from insight_desk.domain.models import CollectorStatus, RunState, RunStatus, Topic, Briefing
from insight_desk.web.render import render_site
from insight_desk.web.validate import validate_artifact


class ArtifactTests(unittest.TestCase):
    def test_fixture_like_artifact_is_mobile_and_utf8(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="insight-desk-test-"))
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        collection = CollectorStatus(1, 1, 0, False, 1)
        state = RunState(RunStatus.COMPLETE, True, "2026-08-09T08:00:00+09:00", "2026-07-10", "fixture", collection, collection)
        briefing = Briefing(state, (Topic("t", "테스트", True, False, 50, ("q",)),), ("첫 줄", "둘째 줄", "셋째 줄"), (), (), (), ())
        render_site(briefing, root)
        self.assertEqual(validate_artifact(root), ())
        text = (root / "index.html").read_text(encoding="utf-8")
        self.assertIn("charset=\"utf-8\"", text.lower())
        self.assertIn("width=device-width", text)
        self.assertIn("수집 범위와 방법론 보기", text)
        self.assertIn("상대 관심지수", text)
        css = (root / "assets/css/style.css").read_text(encoding="utf-8")
        self.assertIn("--accent:", css)
        self.assertIn("--space-1:", css)
        self.assertIn("prefers-color-scheme: dark", css)
        self.assertTrue((root / "archive/2026-08-09/index.html").exists())
        json.loads((root / "data/latest.json").read_text(encoding="utf-8"))
