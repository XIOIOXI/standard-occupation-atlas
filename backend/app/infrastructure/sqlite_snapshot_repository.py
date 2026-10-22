"""SQLite persistence for explicitly imported recruitment snapshots."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from app.domain.recruitment.models import DatasetSnapshot


class SqliteSnapshotRepository:
    """Persists import output without changing CSV import/normalisation behaviour."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)

    def initialise(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.executescript(
                """
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS dataset_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    source_format TEXT NOT NULL,
                    source_file_name TEXT NOT NULL,
                    source_checksum TEXT NOT NULL,
                    imported_at TEXT NOT NULL,
                    source_updated_at TEXT,
                    schema_version TEXT NOT NULL,
                    record_count INTEGER NOT NULL,
                    valid_record_count INTEGER NOT NULL,
                    invalid_record_count INTEGER NOT NULL,
                    validation_summary_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS recruitment_records (
                    snapshot_id TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    row_number INTEGER NOT NULL,
                    updated_at TEXT,
                    company_name TEXT,
                    company_type TEXT,
                    recruitment_session TEXT,
                    recruitment_batch TEXT,
                    industry_category TEXT,
                    location TEXT,
                    job_title TEXT,
                    normalized_job_title TEXT,
                    deadline TEXT,
                    deadline_raw TEXT,
                    education_requirement TEXT,
                    major_requirement TEXT,
                    normalized_major_requirement TEXT,
                    recruitment_url TEXT,
                    announcement_url TEXT,
                    record_status TEXT NOT NULL,
                    validation_issues_json TEXT NOT NULL,
                    raw_payload_json TEXT NOT NULL,
                    PRIMARY KEY (snapshot_id, row_number),
                    FOREIGN KEY (snapshot_id) REFERENCES dataset_snapshots(snapshot_id)
                );

                CREATE INDEX IF NOT EXISTS idx_recruitment_records_snapshot_status
                    ON recruitment_records (snapshot_id, record_status);
                CREATE INDEX IF NOT EXISTS idx_recruitment_records_snapshot_record
                    ON recruitment_records (snapshot_id, record_id);
                """
            )
            self._add_column_if_missing(
                connection,
                "recruitment_records",
                "eligible_for_market_analysis",
                "INTEGER NOT NULL DEFAULT 0",
            )
            self._add_column_if_missing(
                connection,
                "recruitment_records",
                "eligible_for_industry_analysis",
                "INTEGER NOT NULL DEFAULT 0",
            )
            self._add_column_if_missing(
                connection,
                "recruitment_records",
                "eligibility_reasons_json",
                "TEXT NOT NULL DEFAULT '[]'",
            )

    def save(self, snapshot: DatasetSnapshot) -> None:
        """Write an import atomically; duplicate snapshot IDs are rejected."""

        self.initialise()
        snapshot_data = snapshot.model_dump(mode="json")
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO dataset_snapshots (
                    snapshot_id, source_name, source_format, source_file_name,
                    source_checksum, imported_at, source_updated_at, schema_version,
                    record_count, valid_record_count, invalid_record_count,
                    validation_summary_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_data["snapshot_id"],
                    snapshot_data["source_name"],
                    snapshot_data["source_format"],
                    snapshot_data["source_file_name"],
                    snapshot_data["source_checksum"],
                    snapshot_data["imported_at"],
                    snapshot_data["source_updated_at"],
                    snapshot_data["schema_version"],
                    snapshot_data["record_count"],
                    snapshot_data["valid_record_count"],
                    snapshot_data["invalid_record_count"],
                    json.dumps(snapshot_data["validation_summary"], ensure_ascii=False, sort_keys=True),
                ),
            )
            connection.executemany(
                """
                INSERT INTO recruitment_records (
                    snapshot_id, record_id, row_number, updated_at, company_name,
                    company_type, recruitment_session, recruitment_batch, industry_category,
                    location, job_title, normalized_job_title, deadline, deadline_raw,
                    education_requirement, major_requirement, normalized_major_requirement,
                    recruitment_url, announcement_url, record_status,
                    eligible_for_market_analysis, eligible_for_industry_analysis,
                    eligibility_reasons_json, validation_issues_json, raw_payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        snapshot_data["snapshot_id"],
                        record["record_id"],
                        record["row_number"],
                        record["updated_at"],
                        record["company_name"],
                        record["company_type"],
                        record["recruitment_session"],
                        record["recruitment_batch"],
                        record["industry_category"],
                        record["location"],
                        record["job_title"],
                        record["normalized_job_title"],
                        record["deadline"],
                        record["deadline_raw"],
                        record["education_requirement"],
                        record["major_requirement"],
                        record["normalized_major_requirement"],
                        record["recruitment_url"],
                        record["announcement_url"],
                        record["record_status"],
                        int(record["eligible_for_market_analysis"]),
                        int(record["eligible_for_industry_analysis"]),
                        json.dumps(record["eligibility_reasons"], ensure_ascii=False),
                        json.dumps(record["validation_issues"], ensure_ascii=False),
                        json.dumps(record["raw_payload"], ensure_ascii=False, sort_keys=True),
                    )
                    for record in snapshot_data["records"]
                ],
            )

    def summary(self, snapshot_id: str) -> dict[str, int]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT record_status, COUNT(*) AS count
                FROM recruitment_records
                WHERE snapshot_id = ?
                GROUP BY record_status
                """,
                (snapshot_id,),
            ).fetchall()
        return {row["record_status"]: row["count"] for row in rows}

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _add_column_if_missing(
        connection: sqlite3.Connection, table: str, column: str, definition: str
    ) -> None:
        existing = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
