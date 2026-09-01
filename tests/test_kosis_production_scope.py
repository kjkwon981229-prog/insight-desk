from __future__ import annotations

import json
from pathlib import Path
import unittest

from insight_desk.runtime_integration_audit_v2 import (
    build_runtime_integration_specs,
    evaluate_integration_probes,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "authoritative_sources.json"


class KosisProductionScopeTests(unittest.TestCase):
    def test_kosis_is_explicitly_disabled_in_current_production_scope(self) -> None:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.assertIs(config["kosis"]["enabled"], False)
        self.assertTrue(config["kosis"]["datasets"])

    def test_configured_secret_does_not_reactivate_disabled_kosis_route(self) -> None:
        specs = build_runtime_integration_specs(
            env={"KOSIS_API_KEY": "configured-but-disabled"},
            config_path=CONFIG,
        )
        by_id = {spec.integration_id: spec for spec in specs}
        kosis = by_id["kosis"]
        self.assertTrue(kosis.configured)
        self.assertFalse(kosis.active)
        self.assertEqual(kosis.inactive_status, "DISABLED")

        payload = evaluate_integration_probes(specs)
        record = payload["integrations"]["kosis"]
        self.assertEqual(record["status"], "DISABLED")
        self.assertFalse(record["attempted"])
        self.assertEqual(record["calls"], 0)
        self.assertNotIn("kosis", payload["configured_failures"])


if __name__ == "__main__":
    unittest.main()
