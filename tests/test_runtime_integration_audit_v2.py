from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

from insight_desk.runtime_integration_audit_v2 import (
    IntegrationProbeSpec,
    DECLARED_PRODUCTION_API_HOSTS,
    build_runtime_integration_specs,
    evaluate_integration_probes,
)


ROOT = Path(__file__).resolve().parents[1]


class RuntimeIntegrationAuditTests(unittest.TestCase):
    def test_configured_operational_routes_are_live_probed_once(self) -> None:
        calls: list[str] = []
        payload = evaluate_integration_probes(
            (
                IntegrationProbeSpec(
                    "required",
                    role="discovery",
                    scope="required_runtime",
                    configured=True,
                    active=True,
                    required=True,
                    probe=lambda: calls.append("required"),
                ),
                IntegrationProbeSpec(
                    "optional",
                    role="enrichment",
                    scope="conditional_runtime",
                    configured=True,
                    active=True,
                    probe=lambda: calls.append("optional"),
                ),
            )
        )

        self.assertEqual(calls, ["required", "optional"])
        self.assertEqual(payload["status"], "PASS")
        self.assertTrue(payload["all_configured_operational_routes_passed"])
        integrations = payload["integrations"]
        assert isinstance(integrations, dict)
        self.assertEqual(integrations["required"]["calls"], 1)
        self.assertEqual(integrations["optional"]["status"], "PASS")

    def test_failure_audit_records_only_exception_class_not_sensitive_detail(self) -> None:
        def fail() -> None:
            raise RuntimeError("credential=must-never-be-logged")

        payload = evaluate_integration_probes(
            (
                IntegrationProbeSpec(
                    "configured_optional",
                    role="enrichment",
                    scope="conditional_runtime",
                    configured=True,
                    active=True,
                    probe=fail,
                ),
            )
        )
        rendered = json.dumps(payload, ensure_ascii=False)
        self.assertEqual(payload["status"], "FAIL")
        self.assertNotIn("must-never-be-logged", rendered)
        self.assertIn('"error_kind": "RuntimeError"', rendered)

    def test_inactive_provider_is_not_probed_even_when_credential_exists(self) -> None:
        payload = evaluate_integration_probes(
            (
                IntegrationProbeSpec(
                    "external_semantic",
                    role="provider",
                    scope="inactive_visible_path",
                    configured=True,
                    active=False,
                    inactive_status="NOT_ON_VISIBLE_PATH",
                    probe=None,
                ),
            )
        )
        integrations = payload["integrations"]
        assert isinstance(integrations, dict)
        record = integrations["external_semantic"]
        self.assertEqual(record["status"], "NOT_ON_VISIBLE_PATH")
        self.assertFalse(record["attempted"])
        self.assertEqual(record["calls"], 0)

    def test_unconfigured_enabled_enrichment_is_explicit_but_not_a_core_failure(self) -> None:
        payload = evaluate_integration_probes(
            (
                IntegrationProbeSpec(
                    "ecos",
                    role="enrichment",
                    scope="conditional_runtime",
                    configured=False,
                    active=True,
                ),
            )
        )
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["unconfigured_optional_routes"], ["ecos"])

    def test_current_inventory_marks_gdelt_and_external_semantics_inactive_by_default(self) -> None:
        specs = build_runtime_integration_specs(
            env={},
            config_path=ROOT / "config" / "authoritative_sources.json",
        )
        by_id = {spec.integration_id: spec for spec in specs}
        self.assertTrue(by_id["bing_news_rss"].required)
        self.assertFalse(by_id["gdelt_doc"].active)
        self.assertFalse(by_id["groq_generation"].active)
        self.assertFalse(by_id["cloudflare_workers_ai"].active)
        self.assertFalse(by_id["gemini_interactions"].active)
        self.assertFalse(by_id["naver_search_trend"].active)
        self.assertFalse(by_id["configured_public_source_sites"].active)

    def test_partial_cloudflare_configuration_fails_before_any_probe(self) -> None:
        with self.assertRaisesRegex(ValueError, "Cloudflare"):
            build_runtime_integration_specs(
                env={"CLOUDFLARE_ACCOUNT_ID": "account-only"},
                config_path=ROOT / "config" / "authoritative_sources.json",
            )

    def test_every_code_declared_production_api_host_is_in_the_inventory(self) -> None:
        paths = (
            "insight_desk/acquisition/discovery.py",
            "insight_desk/api/naver.py",
            "insight_desk/api/ecos.py",
            "insight_desk/api/kosis.py",
            "insight_desk/api/opendart.py",
            "insight_desk/providers/groq.py",
            "insight_desk/providers/cloudflare.py",
            "insight_desk/providers/gemini.py",
        )
        discovered: set[str] = set()
        for relative in paths:
            source = (ROOT / relative).read_text(encoding="utf-8")
            discovered.update(re.findall(r"https://([A-Za-z0-9.-]+)", source))
        self.assertEqual(discovered, set(DECLARED_PRODUCTION_API_HOSTS))

    def test_production_workflow_runs_strict_audit_only_inside_live_build(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "insight-desk-production.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("scripts.audit_runtime_integrations", workflow)
        self.assertIn("--strict-configured", workflow)
        self.assertIn("build/runtime-integration-audit.json", workflow)
        self.assertIn('GDELT_DISCOVERY_ENABLED: "false"', workflow)

    def test_production_audit_names_exact_source_instead_of_external_provider_as_visible_owner(self) -> None:
        production = (ROOT / "scripts" / "phase11_daily_production_core.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"visible_generation_authority": "exact_canonical_source_proposition"', production)
        self.assertIn('"visible_verification_authority": "evidence-substring-v1"', production)
        self.assertIn('"active_visible_path": False', production)
        self.assertNotIn('"generation": GROQ_20B', production)


if __name__ == "__main__":
    unittest.main()
