import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_job_search_index import build_baseline_items, build_update_items


class JobSearchIndexTests(unittest.TestCase):
    def test_baseline_preserves_source_and_classification_path(self):
        projection = {
            "category_bubbles": {"L1": {"category": {"category_id": "L1", "level_1": "技术", "level_2": "软件", "level_3": "开发"}, "occupations": [{"source_atomic_unit_ids": ["a1"]}]}},
            "level2_direct_buckets": {}, "unplaced": [{"source_atomic_unit_ids": ["a2"]}],
        }
        evidence = {"atomic_units": {
            "a1": {"source_record_id": "r1", "job_title_unit": "后端工程师", "company_name": "甲公司"},
            "a2": {"source_record_id": "r2", "job_title_unit": "管培生", "company_name": "乙公司"},
        }}
        records = {"r1": {"industry_category": "互联网", "updated_at": "2026-10-01"}, "r2": {"updated_at": "2026-10-02"}}
        items = {item["source_atomic_unit_id"]: item for item in build_baseline_items(projection, evidence, records)}
        self.assertEqual(items["a1"]["result_status"], "classified")
        self.assertEqual(items["a1"]["category_paths"][0]["level_3"], "开发")
        self.assertEqual(items["a1"]["source_record_id"], "r1")
        self.assertEqual(items["a2"]["result_status"], "pending")

    def test_update_only_uses_completed_visible_items(self):
        updates = {"batches": [
            {"batch_id": "B1", "status": "completed", "items": [{"atomic_key": "u1", "result_status": "classified", "title_unit": "数据分析师", "category_id": "L2", "level_1": "技术", "level_2": "数据"}]},
            {"batch_id": "B2", "status": "running", "items": [{"atomic_key": "u2", "result_status": "classified"}]},
        ]}
        items = build_update_items(updates)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["search_item_id"], "UPDATE:B1:u1")
        self.assertEqual(items[0]["category_paths"][0]["category_id"], "L2")


if __name__ == "__main__":
    unittest.main()
