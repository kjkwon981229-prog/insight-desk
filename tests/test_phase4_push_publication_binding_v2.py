from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import unittest

from insight_desk.core import RenderMode, VerifiedPublication
from insight_desk.publication_identity_v2 import PublicationIdentityManifest
from scripts.validate_publication_identity import validate_identity


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 8, 27, 4, 0, tzinfo=timezone.utc)


def publication() -> VerifiedPublication:
    return VerifiedPublication(
        publication_id="publication-v2",
        event_id="event-v2",
        topic="economy",
        headline="검증된 제목",
        summary="검증된 요약이다.",
        source_ids=("source-v2",),
        primary_source_url="https://example.com/v2",
        claim_ids=("claim-h", "claim-s"),
        verification_check_ids=("check-cf", "check-local"),
        verified_at=NOW,
        render_mode=RenderMode.GENERATED,
        event_time="2026-08-27",
        publication_time=NOW,
        parent_event_id="parent-v2",
        authoritative_fact_ids=("authority-v2",),
    )


def contract_fixture() -> tuple[str, dict[str, object], dict[str, object], str]:
    manifest = PublicationIdentityManifest.from_verified("daily-20260827T130000+0900", (publication(),))
    digest = manifest.sha256
    html = (
        '<!doctype html><html><body>'
        '<script id="insight-desk-publication-contract" type="application/json" '
        f'data-publication-digest="{digest}">{manifest.canonical_json()}</script>'
        '</body></html>'
    )
    state: dict[str, object] = {
        "status": "SUCCESS",
        "publish": True,
        "briefing_id": manifest.briefing_id,
        "published_entries": 1,
        "publication_contract_version": 2,
        "publication_digest": digest,
        "publication_ids": list(manifest.publication_ids),
    }
    audit: dict[str, object] = {
        "publish": True,
        "publication_contract_version": 2,
        "publication_identity": {
            "briefing_id": manifest.briefing_id,
            "sha256": digest,
            "publication_ids": list(manifest.publication_ids),
        },
        "canonical_contract": {
            "verified_publications": 1,
            "validated": True,
        },
    }
    return html, state, audit, digest


class PublicationBindingValidatorTests(unittest.TestCase):
    def test_validator_binds_pwa_state_and_audit_to_one_exact_digest(self) -> None:
        html, state, audit, digest = contract_fixture()
        result = validate_identity(html=html, state=state, audit=audit)
        self.assertEqual(result["publication_digest"], digest)
        self.assertEqual(result["briefing_id"], "daily-20260827T130000+0900")
        self.assertEqual(result["publication_count"], 1)
        self.assertEqual(result["publication_ids"], ["publication-v2"])

    def test_validator_rejects_state_digest_that_differs_from_pwa(self) -> None:
        html, state, audit, _ = contract_fixture()
        state["publication_digest"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "STATE_DIGEST_MISMATCH"):
            validate_identity(html=html, state=state, audit=audit)

    def test_validator_recomputes_digest_instead_of_trusting_html_attribute(self) -> None:
        html, state, audit, digest = contract_fixture()
        wrong = "f" * 64 if digest != "f" * 64 else "e" * 64
        html = html.replace(f'data-publication-digest="{digest}"', f'data-publication-digest="{wrong}"')
        with self.assertRaisesRegex(ValueError, "HTML_DIGEST_MISMATCH"):
            validate_identity(html=html, state=state, audit=audit)

    def test_manifest_digest_is_sha256_of_canonical_machine_identity_only(self) -> None:
        item = publication()
        manifest = PublicationIdentityManifest.from_verified("briefing-v2", (item,))
        expected = hashlib.sha256(manifest.canonical_json().encode("utf-8")).hexdigest()
        self.assertEqual(manifest.sha256, expected)
        payload = json.loads(manifest.canonical_json())
        self.assertNotIn("headline", payload["publications"][0])
        self.assertNotIn("summary", payload["publications"][0])


class ProductionPushWiringTests(unittest.TestCase):
    def test_wrangler_routes_public_worker_through_publication_gateway(self) -> None:
        wrangler = (ROOT / "push-worker" / "wrangler.jsonc").read_text(encoding="utf-8")
        self.assertIn('"main": "src/publication_gateway.js"', wrangler)

    def test_workflow_validates_identity_before_deploy_and_binds_ready_payload(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "insight-desk-production.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("scripts/validate_publication_identity.py", workflow)
        self.assertIn("production-audit-${{ github.run_id }}", workflow)
        self.assertIn("publication_binding_version", workflow)
        self.assertIn("publication_digest", workflow)
        self.assertIn("briefing_id", workflow)
        self.assertIn('notification_source="schedule"', workflow)
        self.assertIn('notification_source="manual"', workflow)
        self.assertIn("PUBLICATION_DIGEST", workflow)
        self.assertIn("BRIEFING_ID", workflow)

    def test_workflow_runtime_path_covers_new_structural_validator(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "insight-desk-production.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn('      - "scripts/**"', workflow)


if __name__ == "__main__":
    unittest.main()
