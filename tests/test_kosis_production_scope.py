from __future__ import annotations

import json
from pathlib import Path
import unittest

from insight_desk.runtime_integration_audit_v2 import (
    IntegrationProbeSpec,
    build_runtime_integration_specs,
    evaluate_integration_probes,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "authoritative_sources.json"


class KosisProductionScopeTests(unittest.TestCase):
    def test_kosis_is_active_in_current_production_scope(self) -> None:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.assertIs(config["kosis"]["enabled"], True)
        self.assertTrue(config["kosis"]["datasets"])

    def test_configured_secret_keeps_kosis_active_for_live_preflight(self) -> None:
        specs = build_runtime_integration_specs(
            env={"KOSIS_API_KEY": "configured"},
            config_path=CONFIG,
        )
        by_id = {spec.integration_id: spec for spec in specs}
        kosis = by_id["kosis"]
        self.assertTrue(kosis.configured)
        self.assertTrue(kosis.active)
        self.assertIsNotNone(kosis.probe)

    def test_active_configured_kosis_failure_remains_fail_closed(self) -> None:
        def fail() -> None:
            raise TimeoutError("synthetic timeout")

        payload = evaluate_integration_probes(
            (
                IntegrationProbeSpec(
                    "kosis",
                    role="authoritative_enrichment",
                    scope="conditional_runtime",
                    configured=True,
                    active=True,
                    probe=fail,
                ),
            )
        )
        record = payload["integrations"]["kosis"]
        self.assertEqual(record["status"], "FAIL")
        self.assertTrue(record["attempted"])
        self.assertEqual(record["calls"], 1)
        self.assertIn("kosis", payload["configured_failures"])
        self.assertFalse(payload["all_configured_operational_routes_passed"])


if __name__ == "__main__":
    unittest.main()
