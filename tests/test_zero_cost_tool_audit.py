from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ZeroCostToolAuditTests(unittest.TestCase):
    def test_machine_audit_accepts_only_narrow_runtime_helpers(self) -> None:
        audit = json.loads(
            (ROOT / "config" / "zero_cost_tool_audit_v1.json").read_text(encoding="utf-8")
        )
        self.assertEqual(audit["operating_cost_requirement_krw"], 0)
        accepted = {item["tool"]: item for item in audit["adopted_runtime_optional"]}
        self.assertEqual(set(accepted), {"kiwipiepy", "RapidFuzz"})
        self.assertEqual(
            accepted["kiwipiepy"]["authority"], "korean_morphology_and_source_offsets_only"
        )
        self.assertEqual(
            accepted["RapidFuzz"]["authority"], "alias_string_candidate_retrieval_only"
        )
        self.assertTrue(all(not item["paid_path"] for item in accepted.values()))
        self.assertTrue(all(not item["secret_required"] for item in accepted.values()))

    def test_rejected_dateparser_cannot_reenter_optional_dependencies(self) -> None:
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8").casefold()
        self.assertNotIn("dateparser", pyproject)
        audit = json.loads(
            (ROOT / "config" / "zero_cost_tool_audit_v1.json").read_text(encoding="utf-8")
        )
        rejected = {item["tool"] for item in audit["rejected"]}
        self.assertIn("dateparser", rejected)
        self.assertIn("GLiNER-ko", rejected)

    def test_label_studio_is_annotation_only_not_runtime_dependency(self) -> None:
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8").casefold()
        self.assertNotIn("label-studio", pyproject)
        audit = json.loads(
            (ROOT / "config" / "zero_cost_tool_audit_v1.json").read_text(encoding="utf-8")
        )
        annotation = audit["adopted_human_annotation_only"][0]
        self.assertEqual(annotation["tool"], "Label Studio OSS")
        self.assertEqual(annotation["deployment"], "local_self_hosted_only")
        self.assertFalse(annotation["cloud_product_allowed"])
        self.assertFalse(annotation["runtime_dependency"])

    def test_semantic_local_workflow_uses_only_standard_runner_and_no_secrets(self) -> None:
        workflow = (
            ROOT / ".github" / "workflows" / "semantic-local-tools.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("runs-on: ubuntu-24.04", workflow)
        self.assertNotIn("secrets.", workflow)
        self.assertNotIn("larger", workflow.casefold())
        self.assertNotIn("dateparser", workflow.casefold())


if __name__ == "__main__":
    unittest.main()
