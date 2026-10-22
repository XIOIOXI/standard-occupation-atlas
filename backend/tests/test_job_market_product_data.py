import json
import unittest
from pathlib import Path


class JobMarketProductDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path("data/processed/job_market_intelligence/product")
        cls.catalog = json.loads((cls.root / "occupation_catalog.json").read_text(encoding="utf-8"))
        cls.details = json.loads((cls.root / "occupation_details.json").read_text(encoding="utf-8"))
        cls.graph = json.loads((cls.root / "skill_graph.json").read_text(encoding="utf-8"))
        cls.manifest = json.loads((cls.root / "manifest.json").read_text(encoding="utf-8"))

    def test_catalog_matches_feasibility_count(self):
        self.assertEqual(self.manifest["occupation_count"], 520)
        self.assertEqual(len(self.catalog["occupations"]), 520)

    def test_product_manager_contract(self):
        item = next(x for x in self.catalog["occupations"] if x["canonical_id"] == "OCC0289")
        self.assertEqual(item["job_group_count"], 13); self.assertEqual(item["context_count"], 13); self.assertEqual(item["recruitment_evidence_count"], 65); self.assertEqual(item["unique_skill_count"], 34)

    def test_graph_has_no_unsupported_edge_types(self):
        forbidden = {"prerequisite", "requires", "unlock", "depends_on", "related"}
        self.assertFalse(forbidden & {e["edge_type"] for e in self.graph["edges"]})

    def test_pmi_edges_preserve_provenance(self):
        pmi = [e for e in self.graph["edges"] if e["edge_type"] == "skill_pmi_related_to_skill"]
        self.assertEqual(len(pmi), 128); self.assertTrue(all("provenance" in e and "supporting_job_group_count" in e["evidence"] for e in pmi))

    def test_identity_types_are_not_mixed(self):
        self.assertEqual(self.manifest["mapped_occupation_count"] + self.manifest["unmapped_occupation_count"], self.manifest["occupation_count"])

    def test_skill_catalog_uses_normalization_v2_population(self):
        self.assertEqual(self.manifest["skill_count"], 2396)
