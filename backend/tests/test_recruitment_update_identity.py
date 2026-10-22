from __future__ import annotations

import importlib.util
import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("recruitment_update", ROOT / "scripts" / "process_recruitment_update.py")
assert SPEC and SPEC.loader
update = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(update)


class RecruitmentUpdateIdentityTests(unittest.TestCase):
    def test_shared_budget_records_usage_and_stops_overspending(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            budget = update.SharedModelBudget(0.001, Path(directory) / "ledger.json")
            response = {"usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}}
            request = {"model": "deepseek-flash", "messages": [], "max_tokens": 10}
            with patch.object(update, "api_post", return_value=response):
                with self.assertRaisesRegex(RuntimeError, "budget_stop"):
                    budget.call("decision", "https://example.invalid", "unused", request)
            self.assertEqual(len(budget.entries), 0)
            budget = update.SharedModelBudget(0.02, Path(directory) / "ledger2.json")
            with patch.object(update, "api_post", return_value=response):
                budget.call("decision", "https://example.invalid", "unused", request)
            self.assertEqual(budget.entries[0]["usage"]["total_tokens"], 120)
            self.assertLess(budget.committed, 0.02)

    def test_unknown_request_cost_stops_further_calls(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            budget = update.SharedModelBudget(0.02, Path(directory) / "ledger.json")
            request = {"model": "deepseek-flash", "messages": [], "max_tokens": 10}
            with patch.object(update, "api_post", side_effect=TimeoutError()):
                with self.assertRaises(TimeoutError): budget.call("decision", "https://example.invalid", "unused", request)
                with self.assertRaisesRegex(RuntimeError, "uncertain"): budget.call("classification", "https://example.invalid", "unused", request)
            self.assertTrue(budget.uncertain)

    def test_mapping_contract_rejects_unknown_retired_and_missing_l3_evidence(self) -> None:
        from sno_v31_mapping_contract import validate
        base = {"sample_id": "UP-test", "status": "mapped", "target_category_id": "L2", "candidate_category_ids": [], "target_level": "level_2", "reason": "evidence", "level_3_evidence": None}
        levels = {"L2": "level_2", "L3": "level_3", "OLD": "level_2"}
        self.assertTrue(validate(base, levels, {"OLD"}))
        for invalid in ({**base, "target_category_id": "UNKNOWN"}, {**base, "target_category_id": "OLD"}, {**base, "target_category_id": "L3", "target_level": "level_3"}):
            with self.assertRaises(ValueError): validate(invalid, levels, {"OLD"})
    def test_record_and_atomic_keys_ignore_links_and_row_position(self) -> None:
        original = {
            "company_name": "示例科技", "job_title": "前端工程师、后端工程师",
            "recruitment_session": "2027届", "recruitment_batch": "秋招", "location": "上海",
            "recruitment_url": "https://example.com/old", "announcement_url": "https://example.com/a", "row_number": 2,
        }
        changed_link = {**original, "recruitment_url": "https://example.com/new", "announcement_url": "https://example.com/b", "row_number": 999}
        self.assertEqual(update.record_key(original), update.record_key(changed_link))
        self.assertEqual(update.atomic_key(original, "前端工程师"), update.atomic_key(changed_link, "前端工程师"))

    def test_distinct_job_and_appended_atomic_job_remain_distinct(self) -> None:
        record = {"company_name": "示例科技", "recruitment_session": "2027届", "recruitment_batch": "秋招", "location": "上海"}
        frontend = update.atomic_key(record, "前端工程师")
        backend = update.atomic_key(record, "后端工程师")
        self.assertNotEqual(frontend, backend)


if __name__ == "__main__":
    unittest.main()
