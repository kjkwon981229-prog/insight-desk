from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import unittest

from insight_desk.core import RenderMode, RenderedBriefing, RenderedEntry, VerifiedPublication
from insight_desk.publication_identity_v2 import PublicationIdentityManifest
from insight_desk.ui import build_briefing_view_model, render_briefing_html


NOW = datetime(2026, 8, 27, 3, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]


def publication(
    *,
    publication_id: str = "publication-1",
    parent_event_id: str | None = "parent-1",
    authoritative_fact_ids: tuple[str, ...] = ("authority-1",),
) -> VerifiedPublication:
    return VerifiedPublication(
        publication_id=publication_id,
        event_id="event-1",
        topic="economy",
        headline="한국은행이 기준금리를 결정했다",
        summary="금융통화위원회가 기준금리 결정을 발표했다.",
        source_ids=("source-document:article-1",),
        primary_source_url="https://example.com/article-1",
        claim_ids=("claim-headline", "claim-summary"),
        verification_check_ids=("check-cf", "check-local"),
        verified_at=NOW,
        render_mode=RenderMode.GENERATED,
        event_time="2026-08-27",
        publication_time=NOW,
        parent_event_id=parent_event_id,
        authoritative_fact_ids=authoritative_fact_ids,
    )


def briefing() -> RenderedBriefing:
    return RenderedBriefing(
        briefing_id="daily-20260827T120000+0900",
        generated_at=NOW,
        entries=(
            RenderedEntry(
                event_id="event-1",
                headline="한국은행이 기준금리를 결정했다",
                summary="금융통화위원회가 기준금리 결정을 발표했다.",
                claim_ids=("claim-headline", "claim-summary"),
                render_mode=RenderMode.GENERATED,
            ),
        ),
    )


class PublicationProjectionTests(unittest.TestCase):
    def test_manifest_preserves_verified_identity_without_duplicate_visible_prose(self) -> None:
        item = publication()
        manifest = PublicationIdentityManifest.from_verified("briefing-1", (item,))
        payload = manifest.as_dict()
        record = payload["publications"][0]
        self.assertEqual(record["publication_id"], item.publication_id)
        self.assertEqual(record["event_id"], item.event_id)
        self.assertEqual(record["source_ids"], list(item.source_ids))
        self.assertEqual(record["claim_ids"], list(item.claim_ids))
        self.assertEqual(record["verification_check_ids"], list(item.verification_check_ids))
        self.assertEqual(record["parent_event_id"], item.parent_event_id)
        self.assertEqual(record["authoritative_fact_ids"], list(item.authoritative_fact_ids))
        rendered = manifest.canonical_json()
        self.assertNotIn(item.headline, rendered)
        self.assertNotIn(item.summary, rendered)
        self.assertRegex(manifest.sha256, r"^[0-9a-f]{64}$")

    def test_identity_digest_changes_when_canonical_relationship_changes(self) -> None:
        first = PublicationIdentityManifest.from_verified(
            "briefing-1",
            (publication(parent_event_id="parent-a"),),
        )
        second = PublicationIdentityManifest.from_verified(
            "briefing-1",
            (publication(parent_event_id="parent-b"),),
        )
        self.assertNotEqual(first.sha256, second.sha256)

    def test_v2_pwa_embeds_exact_manifest_and_digest_as_inert_json(self) -> None:
        item = publication()
        view = build_briefing_view_model(
            briefing(),
            topic_by_event={"event-1": "경제·투자"},
            source_by_event={"event-1": item.primary_source_url},
            publication_by_event={"event-1": item},
        )
        self.assertIsNotNone(view.publication_manifest)
        manifest = view.publication_manifest
        assert manifest is not None
        html = render_briefing_html(view)
        match = re.search(
            r'<script id="insight-desk-publication-contract" type="application/json" '
            r'data-publication-digest="([0-9a-f]{64})">(.*?)</script>',
            html,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.group(1), manifest.sha256)
        payload = json.loads(match.group(2))
        self.assertEqual(payload, manifest.as_dict())
        self.assertEqual(payload["briefing_id"], briefing().briefing_id)
        self.assertEqual(payload["publications"][0]["publication_id"], item.publication_id)

    def test_legacy_view_without_verified_publications_does_not_forge_manifest(self) -> None:
        view = build_briefing_view_model(briefing())
        self.assertIsNone(view.publication_manifest)
        self.assertNotIn("insight-desk-publication-contract", render_briefing_html(view))

    def test_manifest_requires_every_rendered_event_to_have_verified_publication(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing VerifiedPublication"):
            build_briefing_view_model(briefing(), publication_by_event={})

    def test_production_state_and_audit_share_manifest_digest_contract(self) -> None:
        mechanical = (ROOT / "insight_desk" / "production_orchestrator_compat_v2.py").read_text(
            encoding="utf-8"
        )
        facade = (ROOT / "insight_desk" / "production_orchestrator_v2.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"publication_digest": publication_manifest.sha256', mechanical)
        self.assertIn('"sha256": publication_manifest.sha256', mechanical)
        self.assertIn("publication_by_event=registry.publications_by_event", mechanical)
        self.assertIn('"rendering": "pwa_renderer"', mechanical)
        self.assertIn("_compat.install_production_orchestration(core_module)", facade)


if __name__ == "__main__":
    unittest.main()
