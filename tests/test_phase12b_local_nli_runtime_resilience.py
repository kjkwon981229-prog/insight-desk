from __future__ import annotations

import unittest
from unittest.mock import patch

from insight_desk.providers.local_nli import LocalNliVerifier


class Phase12BLocalNliRuntimeResilienceTests(unittest.TestCase):
    def test_default_local_verifier_defers_model_load_and_reports_runtime_failure_item_locally(self) -> None:
        with patch(
            "insight_desk.providers.local_nli._transformers_predictor",
            side_effect=RuntimeError("synthetic model load failure"),
        ):
            verifier = LocalNliVerifier.transformers_default()
            check = verifier.verify(
                check_id="local:load-failure",
                claim_text="주장이 있다.",
                evidence_text="근거가 있다.",
                evidence_ids=("ev:local",),
            )

        self.assertIsNone(check.entailed)
        self.assertEqual(check.error_code, "local_model_error:runtimeerror")
        self.assertEqual(check.verifier_id, "local-nli")
        self.assertTrue(check.zero_cost)


if __name__ == "__main__":
    unittest.main()
