"""Repair missing original update dates without rerunning classification.

Only use for an already imported manual source whose XLSX date cells were
previously parsed as Excel serial values.  It never creates records, calls an
LLM, or changes classification fields.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from app.domain.recruitment.csv_import import create_snapshot  # noqa: E402
from process_recruitment_update import UPDATE_DB, UpdateRepository, display_catalogue, now  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="repair source update dates for an imported batch")
    parser.add_argument("batch_id")
    parser.add_argument("source", type=Path)
    args = parser.parse_args()

    snapshot = create_snapshot(args.source, source_name="date repair")
    dates = {record.record_id: record.updated_at.isoformat() for record in snapshot.records if record.updated_at}
    changed = 0
    with sqlite3.connect(UPDATE_DB) as connection:
        rows = connection.execute("SELECT atomic_key, item_json FROM recruitment_update_atomic_jobs WHERE batch_id = ?", (args.batch_id,)).fetchall()
        if not rows:
            raise RuntimeError("unknown batch")
        for atomic_key, raw in rows:
            item = json.loads(raw)
            source_date = dates.get(item.get("source_record_id"))
            if not source_date or item.get("source_updated_at") == source_date:
                continue
            item["source_updated_at"] = source_date
            connection.execute(
                "UPDATE recruitment_update_atomic_jobs SET item_json = ?, updated_at = ? WHERE batch_id = ? AND atomic_key = ?",
                (json.dumps(item, ensure_ascii=False, sort_keys=True), now(), args.batch_id, atomic_key),
            )
            changed += 1
    display_catalogue(UpdateRepository(UPDATE_DB))
    print(json.dumps({"batch_id": args.batch_id, "dates_found": len(dates), "items_repaired": changed}, ensure_ascii=False))


if __name__ == "__main__":
    main()
