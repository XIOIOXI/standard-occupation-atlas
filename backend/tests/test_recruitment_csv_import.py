from __future__ import annotations

import csv
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from app.domain.recruitment.csv_import import (
    create_snapshot,
    normalise_row,
    preview_csv,
    validate_csv_schema,
)
from app.infrastructure.sqlite_snapshot_repository import SqliteSnapshotRepository


HEADERS = [
    "更新时间", "公司", "企业类型", "招聘届次", "批次（暑期实习）", "行业类别", "工作地点", "招聘岗位",
    "截止时间", "简历投递链接", "公告链接", "学历要求", "专业要求", "备注",
]
VALID_ROW = [
    "2026/09/18", "示例科技", "民营企业", "2027届", "秋招", "互联网", "上海", "Software Engineer",
    "2026/10/31", "https://example.com/apply", "https://example.com/notice", "本科", "计算机科学", "保留字段",
]


class RecruitmentCsvImportTests(unittest.TestCase):
    def _csv(self, rows: list[list[str]], headers: list[str] = HEADERS) -> Path:
        handle = tempfile.NamedTemporaryFile("w", encoding="utf-8-sig", newline="", suffix=".csv", delete=False)
        with handle:
            writer = csv.writer(handle)
            writer.writerow(headers)
            writer.writerows(rows)
        self.addCleanup(Path(handle.name).unlink)
        return Path(handle.name)

    def test_schema_maps_actual_source_headers(self) -> None:
        report = validate_csv_schema(self._csv([VALID_ROW]))
        self.assertTrue(report.valid)
        self.assertEqual(report.field_mapping["recruitment_batch"], "批次（暑期实习）")
        self.assertEqual(report.field_mapping["recruitment_url"], "简历投递链接")
        self.assertIn("备注", report.unknown_headers)

    def test_preview_is_bounded_and_normalises_fields(self) -> None:
        path = self._csv([VALID_ROW, VALID_ROW])
        result = preview_csv(path, limit=1)
        self.assertEqual(result.returned_rows, 1)
        self.assertEqual(result.schema_report.field_mapping["company_name"], "公司")
        self.assertEqual(result.records[0].normalized_job_title, "software engineer")
        self.assertEqual(str(result.records[0].updated_at), "2026-09-18")
        self.assertEqual(result.records[0].record_status, "valid")

    def test_invalid_url_marks_row_invalid(self) -> None:
        row = VALID_ROW.copy()
        row[9] = "not-a-url"
        report = validate_csv_schema(self._csv([row]))
        raw = dict(zip(HEADERS, row, strict=True))
        record = normalise_row(raw, row_number=2, mapping=report.field_mapping)
        self.assertEqual(record.record_status, "valid")
        self.assertTrue(record.eligible_for_market_analysis)
        self.assertTrue(any(issue.code == "invalid_url" for issue in record.validation_issues))

    def test_missing_industry_limits_only_industry_analysis(self) -> None:
        row = VALID_ROW.copy()
        row[5] = ""
        report = validate_csv_schema(self._csv([row]))
        raw = dict(zip(HEADERS, row, strict=True))
        record = normalise_row(raw, row_number=2, mapping=report.field_mapping)
        self.assertEqual(record.record_status, "valid")
        self.assertTrue(record.eligible_for_market_analysis)
        self.assertFalse(record.eligible_for_industry_analysis)

    def test_missing_company_or_title_is_not_eligible_for_analysis(self) -> None:
        row = VALID_ROW.copy()
        row[1] = ""
        report = validate_csv_schema(self._csv([row]))
        raw = dict(zip(HEADERS, row, strict=True))
        record = normalise_row(raw, row_number=2, mapping=report.field_mapping)
        self.assertEqual(record.record_status, "invalid")
        self.assertFalse(record.eligible_for_market_analysis)

    def test_snapshot_is_deterministic_for_a_small_explicit_input(self) -> None:
        snapshot = create_snapshot(self._csv([VALID_ROW]))
        self.assertEqual(snapshot.record_count, 1)
        self.assertEqual(snapshot.valid_record_count, 1)
        self.assertEqual(snapshot.source_updated_at.isoformat(), "2026-09-18")
        self.assertEqual(len(snapshot.source_checksum), 64)

    def test_snapshot_marks_repeated_stable_records_as_duplicates(self) -> None:
        snapshot = create_snapshot(self._csv([VALID_ROW, VALID_ROW]))
        self.assertEqual(snapshot.valid_record_count, 1)
        self.assertEqual(snapshot.validation_summary["duplicate"], 1)
        self.assertEqual(snapshot.records[1].record_status, "duplicate")

    def test_repository_persists_raw_payload_and_normalised_records(self) -> None:
        snapshot = create_snapshot(self._csv([VALID_ROW]))
        descriptor, database_name = tempfile.mkstemp(suffix=".sqlite")
        os.close(descriptor)
        database = Path(database_name)
        self.addCleanup(database.unlink)
        repository = SqliteSnapshotRepository(database)
        repository.save(snapshot)
        self.assertEqual(repository.summary(snapshot.snapshot_id), {"valid": 1})

    def test_xlsx_uses_the_same_schema_and_normalisation_path(self) -> None:
        """XLSX is read into raw rows before the existing CSV mapper runs."""

        handle = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        workbook = Path(handle.name)
        handle.close()
        self.addCleanup(workbook.unlink)
        rows = [HEADERS, VALID_ROW]
        shared = [value for row in rows for value in row]
        unique = list(dict.fromkeys(shared))
        index = {value: position for position, value in enumerate(unique)}
        def column(position: int) -> str:
            return chr(ord("A") + position)
        worksheet_rows = "".join(
            f'<row r="{row_number}">' + "".join(
                f'<c r="{column(position)}{row_number}" t="s"><v>{index[value]}</v></c>'
                for position, value in enumerate(row)
            ) + "</row>"
            for row_number, row in enumerate(rows, start=1)
        )
        shared_xml = "".join(f"<si><t>{value}</t></si>" for value in unique)
        with zipfile.ZipFile(workbook, "w") as archive:
            archive.writestr("xl/sharedStrings.xml", f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">{shared_xml}</sst>')
            archive.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{worksheet_rows}</sheetData></worksheet>')
        report = validate_csv_schema(workbook)
        snapshot = create_snapshot(workbook)
        self.assertTrue(report.valid)
        self.assertEqual(snapshot.source_format, "xlsx")
        self.assertEqual(snapshot.records[0].company_name, "示例科技")
        self.assertEqual(snapshot.records[0].normalized_job_title, "software engineer")


if __name__ == "__main__":
    unittest.main()
