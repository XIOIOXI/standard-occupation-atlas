import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from process_recruitment_update import evidence_is_sufficient


class EvidenceGateTests(unittest.TestCase):
    def setUp(self):
        self.categories = {"x": {"level_1": "IT", "level_2": "AI", "level_3": "预测与统计学习"}, "y": {"level_1": "IT", "level_2": "软件", "level_3": ""}}
        self.item = {"title_unit": "量子算法工程师", "industry_category": "互联网"}
        self.mapping = {"status": "mapped", "target_category_id": "x", "target_level": "level_3", "title_evidence": "量子算法工程师", "level_3_evidence": "预测与统计学习", "_reuse_source": {"source_title": "量子算法工程师", "industry_category": "互联网"}}

    def test_quantum_is_not_predictive_learning(self):
        self.assertFalse(evidence_is_sufficient(self.item, self.mapping, self.categories))
        self.assertFalse(evidence_is_sufficient(self.item, self.mapping, self.categories, reuse=True))
        self.mapping["level_3_evidence"] = "量子算法工程师"
        self.assertFalse(evidence_is_sufficient(self.item, self.mapping, self.categories))

    def test_reuse_requires_context_and_prior_evidence(self):
        self.mapping.update(target_category_id="y", target_level="level_2")
        self.assertTrue(evidence_is_sufficient(self.item, self.mapping, self.categories, reuse=True))
        self.mapping["_reuse_source"]["industry_category"] = "金融"
        self.assertFalse(evidence_is_sufficient(self.item, self.mapping, self.categories, reuse=True))
        self.mapping["_reuse_source"]["industry_category"] = "互联网"
        self.mapping["title_evidence"] = "无关证据"
        self.assertFalse(evidence_is_sufficient(self.item, self.mapping, self.categories, reuse=True))

    def test_generic_never_reused(self):
        self.item["title_unit"] = "产品经理"
        self.mapping.update(target_category_id="y", target_level="level_2", title_evidence="产品经理", _reuse_source={"source_title": "产品经理", "industry_category": "互联网"})
        self.assertFalse(evidence_is_sufficient(self.item, self.mapping, self.categories, reuse=True))

if __name__ == "__main__":
    unittest.main()
