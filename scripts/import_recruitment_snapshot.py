"""Explicit one-time/import-on-demand recruitment CSV snapshot command."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from app.domain.recruitment.csv_import import create_snapshot, validate_csv_schema
from app.infrastructure.sqlite_snapshot_repository import SqliteSnapshotRepository


def _issues_by_field(snapshot) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for record in snapshot.records:
        counts.update(issue.field for issue in record.validation_issues)
    return dict(sorted(counts.items()))


def _issues_by_severity(snapshot) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for record in snapshot.records:
        counts.update(issue.severity for issue in record.validation_issues)
    return dict(sorted(counts.items()))


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a CSV as a persisted DatasetSnapshot.")
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--source-name", default="2026 recruitment dataset")
    arguments = parser.parse_args()

    schema = validate_csv_schema(arguments.csv_path)
    if not schema.valid:
        raise SystemExit(
            "CSV schema validation failed: " + ", ".join(schema.missing_required_fields)
        )

    snapshot = create_snapshot(arguments.csv_path, source_name=arguments.source_name)
    repository = SqliteSnapshotRepository(arguments.database)
    repository.save(snapshot)

    persisted_statuses = repository.summary(snapshot.snapshot_id)
    summary = {
        "snapshot_id": snapshot.snapshot_id,
        "source_file": snapshot.source_file_name,
        "source_checksum": snapshot.source_checksum,
        "source_updated_at": snapshot.source_updated_at.isoformat() if snapshot.source_updated_at else None,
        "total_rows": snapshot.record_count,
        "valid_records": snapshot.valid_record_count,
        "invalid_records": snapshot.invalid_record_count,
        "duplicate_records": snapshot.validation_summary["duplicate"],
        "eligible_for_market_analysis": sum(
            record.eligible_for_market_analysis for record in snapshot.records
        ),
        "eligible_for_industry_analysis": sum(
            record.eligible_for_industry_analysis for record in snapshot.records
        ),
        "missing_required_fields": schema.missing_required_fields,
        "validation_errors_by_field": _issues_by_field(snapshot),
        "validation_issues_by_severity": _issues_by_severity(snapshot),
        "persisted_status_counts": persisted_statuses,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
