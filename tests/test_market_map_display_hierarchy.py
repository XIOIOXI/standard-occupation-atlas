"""Acceptance checks for the progressive-display projection only."""
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HIERARCHY = ROOT / "data/processed/job_market_intelligence/market_map/display_hierarchy.json"


class MarketMapDisplayHierarchyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(HIERARCHY.read_text(encoding="utf-8"))
        cls.contexts = cls.data["levels"]["level_1"]["nodes_by_parent"]
        cls.occupations = cls.data["levels"]["level_2"]["occupations_by_context"]

    def test_only_current_level_nodes_are_present_in_each_projection(self):
        self.assertEqual(len(self.data["levels"]["level_0"]["nodes"]), 2)
        self.assertNotIn("occupations", self.data["levels"]["level_0"])
        for parent, nodes in self.contexts.items():
            self.assertLessEqual(self.data["display_budgets"]["level_1"], 12)
            self.assertTrue(nodes)
            self.assertNotIn("children", nodes[0])
        for context, occupations in self.occupations.items():
            self.assertTrue(context.startswith("context:"))
            self.assertTrue(occupations)
            self.assertNotIn("contexts", occupations[0])
            self.assertNotIn("skills", occupations[0])

    def test_contexts_and_concrete_occupations_preserve_demand_metric(self):
        self.assertEqual(self.data["demand_metric"], "distinct_recruitment_record_count")
        for nodes in self.contexts.values():
            for node in nodes:
                self.assertEqual(node["demand_metric"], self.data["demand_metric"])
                self.assertGreater(node["recruitment_evidence_count"], 0)
        for nodes in self.occupations.values():
            for node in nodes:
                self.assertEqual(node["demand_metric"], self.data["demand_metric"])
                self.assertGreater(node["recruitment_evidence_count"], 0)

    def test_all_concrete_occupations_are_reachable_and_search_routes_are_valid(self):
        reachable = {node["node_id"] for nodes in self.occupations.values() for node in nodes}
        self.assertEqual(reachable, {node["occupation_id"] for node in self.data["search_index"]})
        for item in self.data["search_index"]:
            route = item["route"]
            self.assertIn(route["major_id"], self.contexts)
            nodes = self.occupations[route["context_id"]]
            self.assertIn(item["occupation_id"], {node["node_id"] for node in nodes})
            self.assertEqual(nodes.index(next(node for node in nodes if node["node_id"] == item["occupation_id"])) // 25, route["occupation_page"])

    def test_no_unsupported_occupation_family_parent_is_created(self):
        policy = self.data["relationship_policy"]
        self.assertIn("metadata only", policy["candidate_family_policy"])
        self.assertEqual(self.data["validation"]["api_calls"], 0)
        self.assertEqual(self.data["validation"]["llm_calls"], 0)


if __name__ == "__main__":
    unittest.main()
