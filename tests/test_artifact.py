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
from scripts.validate_live_acceptance import validate as validate_live_acceptance


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
        self.assertTrue(css.startswith(":root {"))
        self.assertIn("--accent:", css)
        self.assertIn("--space-1:", css)
        self.assertIn("prefers-color-scheme: dark", css)
        self.assertIn("env(safe-area-inset-top)", css)
        self.assertTrue((root / "archive/2026-08-09/index.html").exists())
        manifest = json.loads((root / "manifest.webmanifest").read_text(encoding="utf-8"))
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["x-icon-status"], "APPROVED_CANDIDATE_5_EXTRACTED")
        self.assertEqual({icon["sizes"] for icon in manifest["icons"]}, {"192x192", "512x512"})
        for page in (root / "index.html", root / "latest/index.html", root / "archive/index.html", root / "archive/2026-08-09/index.html"):
            page_text = page.read_text(encoding="utf-8")
            self.assertIn('rel="manifest"', page_text)
            self.assertIn('rel="icon"', page_text)
            self.assertIn('rel="apple-touch-icon"', page_text)
            self.assertIn("apple-mobile-web-app-capable", page_text)
            self.assertIn("viewport-fit=cover", page_text)
        self.assertNotIn("serviceWorker", (root / "index.html").read_text(encoding="utf-8"))
        self.assertIn("data-generated-date", (root / "index.html").read_text(encoding="utf-8"))
        self.assertNotIn("data-latest-briefing", (root / "archive/2026-08-09/index.html").read_text(encoding="utf-8"))
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
        self.assertNotIn('class="hero"', text)
        self.assertNotIn("selection_audit", (root / "data/latest.json").read_text(encoding="utf-8"))
        self.assertIn("data-generated-date", text)

    def test_live_acceptance_rejects_truncation_and_duplicate_events(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="insight-desk-live-qa-"))
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        story = {
            "headline": "KBO 폭염으로 경기 중단…",
            "summary": "프로야구 경기가 폭염 영향으로 중단됐다.",
            "event_type": "SPORTS_INTERRUPTION",
            "source_count": 2,
            "concrete_fact_count": 2,
            "topic_id": "kbo",
            "why_selected": ["CONCRETE_EVENT"],
            "event_signature": "SPORTS_INTERRUPTION|폭염|KBO",
        }
        payload = {"selected_stories": [story, dict(story, headline="KBO 폭염으로 경기 중단")]} 
        path = root / "live-acceptance.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        errors = validate_live_acceptance(path)
        self.assertTrue(any("truncated source copy" in error for error in errors))
        self.assertTrue(any("duplicate event signatures" in error for error in errors))

    def test_live_acceptance_rejects_low_value_selected_events(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="insight-desk-low-value-qa-"))
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        story = {
            "rank": 1,
            "headline": "금주 금융당국 주요일정 8월10일 개최",
            "summary": "금주 일정이 8월10일 개최될 예정이다.",
            "event_type": "ROUTINE_SCHEDULE",
            "source_count": 1,
            "concrete_fact_count": 2,
            "topic_id": "economy",
            "why_selected": ["CONCRETE_EVENT"],
            "event_signature": "ROUTINE_SCHEDULE|금융당국|8월10일",
        }
        path = root / "live-acceptance.json"
        path.write_text(json.dumps({"selected_stories": [story]}, ensure_ascii=False), encoding="utf-8")
        errors = validate_live_acceptance(path)
        self.assertTrue(any("low-value event type" in error for error in errors))

    def test_live_acceptance_rejects_audit_synthesis_mismatch(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="insight-desk-audit-contract-"))
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        story = {
            "rank": 1,
            "headline": "박진영 컴백",
            "summary": "박진영이 컴백 활동을 마쳤다.",
            "event_type": "SCHEDULED_EVENT",
            "source_count": 1,
            "concrete_fact_count": 2,
            "topic_id": "kpop",
            "why_selected": ["CONCRETE_EVENT"],
            "event_signature": "SCHEDULED_EVENT|박진영|컴백",
            "facts": {"event_type": "ENTERTAINMENT_EVENT"},
            "trend_relationship": "검색 관심 · 둔화",
        }
        path = root / "live-acceptance.json"
        path.write_text(json.dumps({"selected_stories": [story]}, ensure_ascii=False), encoding="utf-8")
        errors = validate_live_acceptance(path)
        self.assertTrue(any("event type disagrees" in error for error in errors))
        self.assertTrue(any("trend label without matched trend groups" in error for error in errors))

        story["trend_matches"] = []
        path.write_text(json.dumps({"selected_stories": [story]}, ensure_ascii=False), encoding="utf-8")
        errors = validate_live_acceptance(path)
        self.assertTrue(any("trend label without matched trend groups" in error for error in errors))
