import json
import unittest
from pathlib import Path


class FrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path("frontend")
        cls.catalog = json.loads(Path("data/processed/job_market_intelligence/product/occupation_catalog.json").read_text(encoding="utf-8"))
        cls.demo = json.loads(Path("data/processed/job_market_intelligence/product/product_manager_demo.json").read_text(encoding="utf-8"))
        cls.js = (cls.root / "app.js").read_text(encoding="utf-8")

    def test_frontend_assets_exist(self):
        self.assertTrue((self.root / "index.html").exists())
        self.assertTrue((self.root / "styles.css").exists())
        self.assertTrue((self.root / "app.js").exists())

    def test_product_manager_is_loadable(self):
        self.assertTrue(any(x.get("canonical_id") == "OCC0289" for x in self.catalog["occupations"]))
        self.assertEqual(self.demo["occupation"]["occupation"]["canonical_id"], "OCC0289")

    def test_interactions_are_present(self):
        for marker in ("pointerdown", "wheel", "expanded", "showSkill", "context-select", "fit"):
            self.assertIn(marker, self.js)

    def test_unsupported_edges_are_not_rendered(self):
        for marker in ("prerequisite", "depends_on", "unlock"):
            self.assertNotIn(f'edge_type === "{marker}"', self.js)
