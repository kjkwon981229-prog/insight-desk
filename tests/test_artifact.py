from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from insight_desk.domain.models import (
    Briefing,
    Certainty,
    CollectorStatus,
    EvidenceType,
    NewsItem,
    RunState,
    RunStatus,
    Story,
    StoryFacts,
    Topic,
)
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
        self.assertIn("데이터 기준과 읽는 법", text)
        self.assertIn("상대 관심지수", text)
        css = (root / "assets/css/style.css").read_text(encoding="utf-8")
        self.assertIn("--accent:", css)
        self.assertIn("--space-1:", css)
        self.assertIn("prefers-color-scheme: dark", css)
        self.assertTrue((root / "archive/2026-08-09/index.html").exists())
        json.loads((root / "data/latest.json").read_text(encoding="utf-8"))

    def test_user_view_hides_internal_ids_and_old_microcopy(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="insight-desk-copy-"))
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        collection = CollectorStatus(1, 1, 0, False, 1)
        state = RunState(RunStatus.COMPLETE, True, "2026-08-09T08:00:00+09:00", "2026-07-10", "fixture", collection, collection)
        topic = Topic("t", "테스트", True, False, 50, ("q",))
        item = NewsItem(
            "N001", "t", "q", "테스트 제목", "테스트 요약", "https://example.com/story", "https://n.news.naver.com/story", "https://example.com/story", "2026-08-09T07:00:00+09:00", "example.com", "hash", 1.0,
        )
        story = Story(
            "t", "테스트", "테스트 제목", "테스트 요약", "한 출처에서 확인됐다.", "관심 흐름 확인", "", "", ("후속 발표",), ("N001",), Certainty.CONFIRMED, 1.0, 1, (EvidenceType.SEARCH_SNIPPET,), 0,
            facts=StoryFacts(event_type="STATISTIC", key_numbers=("47원",), key_changes=("금융위기 후 최고",)),
        )
        briefing = Briefing(state, (topic,), ("첫 줄", "둘째 줄", "셋째 줄"), (story,), (item,), (), ())
        render_site(briefing, root)
        text = (root / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("N001", text)
        for forbidden in (
            "왜 보나",
            "근거와 확인할 것",
            "핵심 해석",
            "관심도와의 관계",
            "산업·투자 판단",
            "출처 범위",
        ):
            self.assertNotIn(forbidden, text)
        self.assertIn("전체 근거 보기", text)
        self.assertIn("근거 1곳", text)
        self.assertIn("key-fact-panel", text)
