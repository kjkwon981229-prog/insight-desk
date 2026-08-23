from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import unittest

from insight_desk.core import RenderMode, RenderedBriefing, RenderedEntry
from insight_desk.ui import PwaRuntimeConfig, build_briefing_view_model, render_briefing_html


def view():
    briefing = RenderedBriefing(
        briefing_id="briefing:pwa",
        generated_at=datetime(2026, 8, 23, 13, 19, tzinfo=timezone.utc),
        entries=(
            RenderedEntry(
                event_id="event:pwa",
                headline="검증된 제목",
                summary="검증된 요약",
                claim_ids=("claim:headline", "claim:summary"),
                render_mode=RenderMode.GENERATED,
            ),
        ),
    )
    return build_briefing_view_model(briefing)


class Phase8PwaPushWiringTests(unittest.TestCase):
    def test_manifest_is_always_linked_but_push_ui_is_hidden_without_worker_config(self) -> None:
        html = render_briefing_html(view())
        self.assertIn('rel="manifest" href="manifest.webmanifest"', html)
        self.assertNotIn("insight-desk-push-worker-url", html)
        self.assertNotIn("data-push-settings", html)
        self.assertNotIn("assets/js/push.js", html)
        self.assertNotIn("data-push-enable", html)

    def test_explicit_https_worker_config_enables_existing_push_assets(self) -> None:
        runtime = PwaRuntimeConfig(push_worker_url="https://push.example.workers.dev/")
        html = render_briefing_html(view(), runtime=runtime)
        self.assertEqual(runtime.push_worker_url, "https://push.example.workers.dev")
        self.assertIn(
            '<meta name="insight-desk-push-worker-url" content="https://push.example.workers.dev">',
            html,
        )
        self.assertIn("data-push-settings", html)
        self.assertIn('data-push-service-worker-url="push-sw.js"', html)
        self.assertIn("data-push-enable", html)
        self.assertIn("data-push-disable", html)
        self.assertIn('<script src="assets/js/push.js" defer></script>', html)

    def test_root_service_worker_matches_preserved_notification_worker(self) -> None:
        root_worker = Path("push-sw.js").read_text(encoding="utf-8")
        preserved_worker = Path("assets/push-sw.js").read_text(encoding="utf-8")
        self.assertEqual(root_worker, preserved_worker)
        self.assertNotIn('addEventListener("fetch"', root_worker)

    def test_push_ui_describes_only_ready_or_failure_status_not_article_content(self) -> None:
        html = render_briefing_html(
            view(),
            runtime=PwaRuntimeConfig(push_worker_url="https://push.example.workers.dev"),
        )
        self.assertIn("브리핑 준비 완료 또는 업데이트 실패 상태만 알립니다.", html)
        push_start = html.index('<section class="push-settings"')
        push_end = html.index("</section>", push_start)
        push_section = html[push_start:push_end]
        self.assertNotIn("검증된 제목", push_section)
        self.assertNotIn("검증된 요약", push_section)

    def test_non_https_or_credentialed_or_parameterized_worker_urls_fail_closed(self) -> None:
        invalid = (
            "http://push.example.workers.dev",
            "https://user:pass@push.example.workers.dev",
            "https://push.example.workers.dev?token=secret",
            "https://push.example.workers.dev#fragment",
            "not-a-url",
        )
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    PwaRuntimeConfig(push_worker_url=value)


if __name__ == "__main__":
    unittest.main()
