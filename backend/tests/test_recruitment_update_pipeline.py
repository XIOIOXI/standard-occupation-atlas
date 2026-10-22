from __future__ import annotations

import csv
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.domain.recruitment.csv_import import create_snapshot
from app.infrastructure.sqlite_snapshot_repository import SqliteSnapshotRepository

SPEC = importlib.util.spec_from_file_location("recruitment_update_pipeline", ROOT / "scripts" / "process_recruitment_update.py")
assert SPEC and SPEC.loader
update = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(update)

HEADERS = ["更新时间", "公司", "企业类型", "招聘届次", "批次（暑期实习）", "行业类别", "工作地点", "招聘岗位", "截止时间", "简历投递链接", "公告链接", "学历要求", "专业要求"]


class RecruitmentUpdatePipelineTests(unittest.TestCase):
    def write_csv(self, path: Path, rows: list[list[str]]) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(HEADERS)
            writer.writerows(rows)

    def test_appended_atomic_role_is_new_but_changed_link_and_repeat_are_not(self) -> None:
        temp_root = ROOT / "backend" / "tests" / ".tmp"
        temp_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_root) as directory:
            temp = Path(directory)
            baseline_csv, update_csv = temp / "baseline.csv", temp / "update.csv"
            baseline_row = ["2026/09/18", "示例科技", "民营", "2027届", "秋招", "互联网", "上海", "前端工程师", "", "https://example.com/old", "", "本科", "计算机"]
            update_row = ["2026/09/19", "示例科技", "民营", "2027届", "秋招", "互联网", "上海", "前端工程师、后端工程师", "", "https://example.com/new", "", "本科", "计算机"]
            self.write_csv(baseline_csv, [baseline_row])
            self.write_csv(update_csv, [update_row])
            baseline_db = temp / "baseline.sqlite"
            SqliteSnapshotRepository(baseline_db).save(create_snapshot(baseline_csv))

            old_root, old_catalogue, old_argv = update.ROOT, update.DISPLAY_CATALOGUE, sys.argv
            try:
                update.ROOT = temp
                update.DISPLAY_CATALOGUE = temp / "update_batches.json"
                sys.argv = ["process_recruitment_update.py", str(update_csv), "--baseline-database", str(baseline_db), "--update-database", str(temp / "updates.sqlite")]
                update.main()
                payload = json.loads(update.DISPLAY_CATALOGUE.read_text(encoding="utf-8"))
                self.assertEqual(len(payload["batches"]), 1)
                self.assertEqual(payload["batches"][0]["counts"]["new_atomic_jobs"], 1)
                self.assertEqual(payload["batches"][0]["items"][0]["title_unit"], "后端工程师")
                update.main()
                payload = json.loads(update.DISPLAY_CATALOGUE.read_text(encoding="utf-8"))
                self.assertEqual(len(payload["batches"]), 1)
            finally:
                update.ROOT, update.DISPLAY_CATALOGUE, sys.argv = old_root, old_catalogue, old_argv

    def test_link_only_change_does_not_create_an_empty_batch_or_notification(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            temp = Path(directory)
            baseline_csv, update_csv = temp / "baseline.csv", temp / "link-only.csv"
            baseline_row = ["2026/09/18", "示例科技", "民营", "2027届", "秋招", "互联网", "上海", "前端工程师", "", "https://example.com/old", "", "本科", "计算机"]
            link_only_row = ["2026/09/19", "示例科技", "民营", "2027届", "秋招", "互联网", "上海", "前端工程师", "", "https://example.com/new", "", "本科", "计算机"]
            self.write_csv(baseline_csv, [baseline_row])
            self.write_csv(update_csv, [link_only_row])
            baseline_db = temp / "baseline.sqlite"
            SqliteSnapshotRepository(baseline_db).save(create_snapshot(baseline_csv))
            old_root, old_catalogue, old_argv = update.ROOT, update.DISPLAY_CATALOGUE, sys.argv
            try:
                update.ROOT = temp
                update.DISPLAY_CATALOGUE = temp / "update_batches.json"
                sys.argv = ["process_recruitment_update.py", str(update_csv), "--baseline-database", str(baseline_db), "--update-database", str(temp / "updates.sqlite")]
                update.main()
                payload = json.loads(update.DISPLAY_CATALOGUE.read_text(encoding="utf-8"))
                self.assertEqual(payload["batches"], [])
            finally:
                update.ROOT, update.DISPLAY_CATALOGUE, sys.argv = old_root, old_catalogue, old_argv

    def test_all_persisted_snapshots_form_the_incremental_baseline(self) -> None:
        """A role from an older import must not be reintroduced after a newer import."""
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            temp = Path(directory)
            first, second, update_csv = temp / "first.csv", temp / "second.csv", temp / "update.csv"
            first_row = ["2026/09/18", "甲公司", "民营", "2027届", "秋招", "互联网", "上海", "前端工程师", "", "", "", "本科", "计算机"]
            second_row = ["2026/09/19", "乙公司", "民营", "2027届", "秋招", "互联网", "北京", "后端工程师", "", "", "", "本科", "计算机"]
            self.write_csv(first, [first_row])
            self.write_csv(second, [second_row])
            self.write_csv(update_csv, [first_row, second_row])
            baseline_db = temp / "baseline.sqlite"
            repository = SqliteSnapshotRepository(baseline_db)
            repository.save(create_snapshot(first))
            repository.save(create_snapshot(second))
            old_root, old_catalogue, old_argv = update.ROOT, update.DISPLAY_CATALOGUE, sys.argv
            try:
                update.ROOT = temp
                update.DISPLAY_CATALOGUE = temp / "update_batches.json"
                sys.argv = ["process_recruitment_update.py", str(update_csv), "--baseline-database", str(baseline_db), "--update-database", str(temp / "updates.sqlite")]
                update.main()
                self.assertEqual(json.loads(update.DISPLAY_CATALOGUE.read_text(encoding="utf-8"))["batches"], [])
            finally:
                update.ROOT, update.DISPLAY_CATALOGUE, sys.argv = old_root, old_catalogue, old_argv

    def test_model_mode_without_key_uses_bounded_hold_instead_of_import_failure(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            temp = Path(directory)
            baseline_csv, update_csv = temp / "baseline.csv", temp / "update.csv"
            baseline_row = ["2026/09/18", "示例科技", "民营", "2027届", "秋招", "互联网", "上海", "前端工程师", "", "", "", "本科", "计算机"]
            unknown_row = ["2026/09/19", "新公司", "民营", "2027届", "秋招", "互联网", "上海", "量子算法工程师", "", "", "", "本科", "计算机"]
            self.write_csv(baseline_csv, [baseline_row])
            self.write_csv(update_csv, [baseline_row, unknown_row])
            baseline_db = temp / "baseline.sqlite"
            SqliteSnapshotRepository(baseline_db).save(create_snapshot(baseline_csv))
            old_root, old_catalogue, old_argv = update.ROOT, update.DISPLAY_CATALOGUE, sys.argv
            old_key = os.environ.pop("DEEPSEEK_API_KEY", None)
            try:
                update.ROOT = temp
                update.DISPLAY_CATALOGUE = temp / "update_batches.json"
                sys.argv = ["process_recruitment_update.py", str(update_csv), "--mapping-mode", "model", "--budget-usd", "0.20", "--baseline-database", str(baseline_db), "--update-database", str(temp / "updates.sqlite")]
                update.main()
                item = json.loads(update.DISPLAY_CATALOGUE.read_text(encoding="utf-8"))["batches"][0]["items"][0]
                self.assertEqual(item["result_status"], "pending")
                self.assertEqual(item["agent_trace"][0]["action"], "hold")
            finally:
                if old_key is not None: os.environ["DEEPSEEK_API_KEY"] = old_key
                update.ROOT, update.DISPLAY_CATALOGUE, sys.argv = old_root, old_catalogue, old_argv


if __name__ == "__main__":
    unittest.main()
