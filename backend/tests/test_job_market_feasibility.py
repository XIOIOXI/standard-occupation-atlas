import unittest
from app.domain.job_market.feasibility import build_comparison_candidates, build_occupation_inventory


class JobMarketFeasibilityTests(unittest.TestCase):
    def group(self, gid, title, context, canonical=None):
        return {"job_group_id": gid, "representative_title": title, "prepared_inference_input": {"canonical_occupation_id": canonical, "canonical_occupation_title": title if canonical else None, "industry_domain_context": context, "context_quality": "high", "source_recruitment_record_ids": [gid]}}

    def result(self, gid, skills):
        return {"job_group_id": gid, "inference_status": "completed", "hard_skills": [{"normalized_skill_name": x, "skill_type": "hard", "skill_scope": "occupation_core"} for x in skills], "soft_skills": []}

    def test_inventory_preserves_mapped_and_unmapped(self):
        groups = [self.group("a", "Engineer", "tech", "O1"), self.group("b", "Candidate", "finance")]
        inv = build_occupation_inventory(groups, {"a": self.result("a", ["Python"]), "b": self.result("b", ["Excel"])})
        self.assertEqual(inv["mapped_occupation_count"], 1); self.assertEqual(inv["unmapped_occupation_count"], 1)

    def test_comparison_requires_shared_and_distinctive_structure(self):
        groups = [self.group("a", "Engineer", "tech", "O1"), self.group("b", "Engineer", "finance", "O1")]
        results = {"a": self.result("a", ["Python", "Data", "Shared"]), "b": self.result("b", ["Python", "Finance", "Shared"])}
        comparison = build_comparison_candidates(build_occupation_inventory(groups, results))
        self.assertEqual(comparison["eligible_count"], 1)
        self.assertEqual(comparison["candidates"][0]["shared_skills"], ["Python", "Shared"])
