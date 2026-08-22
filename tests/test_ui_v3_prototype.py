import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "design" / "prototype-v3"
HTML = (PROTOTYPE / "index.html").read_text(encoding="utf-8")
CSS = (PROTOTYPE / "prototype.css").read_text(encoding="utf-8")
JS = (PROTOTYPE / "prototype.js").read_text(encoding="utf-8")


class SoftGeometryV3PrototypeTests(unittest.TestCase):
    def test_prototype_is_isolated_from_production_stylesheet(self):
        self.assertIn('href="./prototype.css"', HTML)
        self.assertNotIn('assets/css/style.css', HTML)

    def test_multi_mode_architecture_is_present(self):
        for view in ("home", "ledger", "detail"):
            self.assertIn(f'data-view="{view}"', HTML)
        self.assertIn('class="mobile-focus"', HTML)
        self.assertIn("D3", CSS)
        self.assertIn("SIGNAL LEDGER", HTML)
        self.assertIn("SELECTED EVENT", HTML)

    def test_soft_geometry_radius_hierarchy_is_frozen(self):
        expected = {
            "--r-1: 14px",
            "--r-2: 20px",
            "--r-3: 28px",
            "--r-4: 36px",
            "--r-5: 44px",
        }
        for token in expected:
            self.assertIn(token, CSS)

    def test_pink_brand_tokens_are_retained(self):
        for value in ("#c35b78", "#943c59", "#efd7df", "#7d3049"):
            self.assertIn(value, CSS.lower())

    def test_responsive_contract_covers_mobile_and_tablet_breakpoints(self):
        self.assertIn("@media (max-width: 900px)", CSS)
        self.assertIn("@media (max-width: 640px)", CSS)
        self.assertIn("@media (max-width: 430px)", CSS)
        self.assertIn(".desktop-home { display: none; }", CSS)
        self.assertIn(".mobile-focus { display: block; }", CSS)

    def test_accessibility_and_reduced_motion_hooks_exist(self):
        self.assertIn("aria-label=", HTML)
        self.assertIn("aria-pressed=", HTML)
        self.assertIn(":focus-visible", CSS)
        self.assertIn("prefers-reduced-motion", CSS)
        self.assertIn("min-height: 44px", CSS)

    def test_state_and_failure_examples_are_explicit(self):
        self.assertIn("SUPPORTED", HTML)
        self.assertIn("PENDING", HTML)
        self.assertIn("CONTEXT ONLY", HTML)
        self.assertIn("부분 소스 실패 상태 예시", HTML)
        self.assertIn("발표 → 예정", HTML)

    def test_no_external_runtime_dependency_is_added(self):
        self.assertNotIn("https://", CSS)
        self.assertNotIn("http://", CSS)
        self.assertNotIn("fetch(", JS)
        self.assertNotIn("XMLHttpRequest", JS)


if __name__ == "__main__":
    unittest.main()
