from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]


class AnnotationSeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_annotation_seed.py")],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_material_seed_is_blind_and_does_not_relabel_selection_tns(self) -> None:
        path = ROOT / "annotation" / "material_event" / "tasks_seed.json"
        tasks = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(tasks), 59)
        for task in tasks:
            self.assertEqual(set(task), {"id", "data"})
            data = task["data"]
            self.assertNotIn("gold", data)
            self.assertNotIn("label", data)
            self.assertNotIn("is_material", data)
            self.assertNotIn("source_ref", data)
            self.assertIn("UNCERTAIN", data["instruction"])

    def test_fact_seed_is_unlabeled_evidence_only_source_text(self) -> None:
        path = ROOT / "annotation" / "fact_extraction" / "tasks_seed.json"
        tasks = json.loads(path.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(tasks), 20)
        for task in tasks:
            data = task["data"]
            self.assertIn("text", data)
            self.assertNotIn("gold", data)
            self.assertNotIn("spans", data)
            self.assertNotIn("source_ref", data)

    def test_provenance_is_separate_from_label_studio_task_payload(self) -> None:
        for folder in ("material_event", "fact_extraction"):
            tasks = json.loads(
                (ROOT / "annotation" / folder / "tasks_seed.json").read_text(encoding="utf-8")
            )
            provenance = json.loads(
                (ROOT / "annotation" / folder / "seed_provenance.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual({task["id"] for task in tasks}, set(provenance))

    def test_label_studio_configs_are_well_formed_and_keep_tasks_separate(self) -> None:
        material = ElementTree.parse(
            ROOT / "annotation" / "material_event" / "label_config.xml"
        ).getroot()
        fact = ElementTree.parse(
            ROOT / "annotation" / "fact_extraction" / "label_config.xml"
        ).getroot()
        material_values = {node.attrib.get("value") for node in material.iter("Choice")}
        fact_values = {node.attrib.get("value") for node in fact.iter("Label")}
        self.assertTrue({"MATERIAL", "NOT_MATERIAL", "UNCERTAIN"}.issubset(material_values))
        self.assertTrue({"SUBJECT", "ACTION", "OBJECT", "DATE_TIME"}.issubset(fact_values))
        self.assertNotIn("MATERIAL", fact_values)


if __name__ == "__main__":
    unittest.main()
