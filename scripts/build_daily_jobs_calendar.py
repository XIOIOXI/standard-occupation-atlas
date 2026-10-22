"""Build the user-facing daily recruitment-job index without model calls.

The index is a read-only join of the effective SNO display projection, its
atomic evidence, the preserved recruitment snapshot, and manually imported
updates.  It deliberately uses the source record's original update date, not
an import/batch timestamp.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISPLAY_DIR = ROOT / "data/processed/record_role_classification_v1/full_drafts/sno_v31_reasonable_primary_v4_display"
PROJECTION_PATH = DISPLAY_DIR / "display_projection_v31_full_draft.json"
EVIDENCE_PATH = DISPLAY_DIR / "sno_atomic_evidence_index_v1.json"
UPDATES_PATH = DISPLAY_DIR / "update_batches.json"
SNAPSHOTS_PATH = ROOT / "data/processed/recruitment_snapshots.sqlite"
OUTPUT_PATH = DISPLAY_DIR / "daily_jobs_v1.json"
DATE_FROM = "2026-08-01"


def write_json(path: Path, value: object) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as output:
        json.dump(value, output, ensure_ascii=False, indent=2)
        output.write("\n")
        temporary_path = Path(output.name)
    temporary_path.replace(path)


def category_items(projection: dict) -> list[tuple[dict, dict]]:
    """Yield effective mapped display items with their category path."""
    rows: list[tuple[dict, dict]] = []
    for bucket in projection.get("category_bubbles", {}).values():
        rows.extend((bucket["category"], item) for item in bucket.get("occupations", []))
    for bucket in projection.get("level2_direct_buckets", {}).values():
        rows.extend((bucket["category"], item) for item in bucket.get("occupations", []))
    return rows


def snapshot_dates() -> dict[str, str]:
    with sqlite3.connect(SNAPSHOTS_PATH) as connection:
        snapshot = connection.execute(
            "SELECT snapshot_id FROM dataset_snapshots ORDER BY imported_at DESC LIMIT 1"
        ).fetchone()
        if not snapshot:
            raise RuntimeError("Recruitment snapshot is unavailable; daily index was not changed.")
        return {
            record_id: updated_at
            for record_id, updated_at in connection.execute(
                "SELECT record_id, updated_at FROM recruitment_records WHERE snapshot_id = ?",
                (snapshot[0],),
            )
            if updated_at
        }


def baseline_items(projection: dict, evidence: dict, dates: dict[str, str]) -> tuple[list[dict], int, int, int]:
    atomic_units = evidence.get("atomic_units", {})
    display_entries: list[tuple[str, str, str, dict]] = []
    for category, item in category_items(projection):
        placement = {
            "result_status": "classified",
            "level_1": category.get("level_1"),
            "level_2": category.get("level_2"),
            "level_3": category.get("level_3") or "",
            "category_id": category.get("category_id"),
            "reason": item.get("reason"),
        }
        for atomic_id in item.get("source_atomic_unit_ids", []):
            display_entries.append((atomic_id, item["standard_occupation_id"], item["label"], placement))
    for item in projection.get("unplaced", []):
        placement = {
            "result_status": "pending",
            "level_1": None,
            "level_2": None,
            "level_3": "",
            "category_id": None,
            "reason": item.get("reason") or "待确认",
        }
        for atomic_id in item.get("source_atomic_unit_ids", []):
            display_entries.append((atomic_id, item["standard_occupation_id"], item["label"], placement))

    items: list[dict] = []
    missing_date = 0
    atomic_occurrences = Counter(atomic_id for atomic_id, _, _, _ in display_entries)
    for atomic_id, occupation_id, display_label, placement in display_entries:
        source = atomic_units.get(atomic_id)
        if not source:
            continue
        source_record_id = source.get("source_record_id")
        source_updated_at = dates.get(source_record_id)
        if not source_updated_at:
            missing_date += 1
            continue
        if source_updated_at < DATE_FROM:
            continue
        items.append({
            "daily_item_id": f"BASE:{occupation_id}:{atomic_id}",
            "source_atomic_unit_id": atomic_id,
            "source_record_id": source_record_id,
            "source_updated_at": source_updated_at,
            "title_unit": display_label or source.get("job_title_unit"),
            "company_name": source.get("company_name"),
            "company_type": source.get("company_type"),
            "location": source.get("location"),
            "recruitment_url": source.get("recruitment_url"),
            "announcement_url": source.get("announcement_url"),
            **placement,
        })
    return items, missing_date, len(atomic_occurrences), sum(count > 1 for count in atomic_occurrences.values())


def update_items(payload: dict) -> list[dict]:
    items: list[dict] = []
    for batch in payload.get("batches", []):
        for item in batch.get("items", []):
            if item.get("result_status") not in {"classified", "pending"}:
                continue
            source_updated_at = item.get("source_updated_at")
            if not source_updated_at or source_updated_at < DATE_FROM:
                continue
            items.append({
                "daily_item_id": f"UPDATE:{item['atomic_key']}",
                "source_atomic_unit_id": item["atomic_key"],
                "source_record_id": item.get("source_record_id"),
                "source_updated_at": source_updated_at,
                "title_unit": item.get("title_unit"),
                "company_name": item.get("company_name"),
                "company_type": item.get("company_type"),
                "location": item.get("location"),
                "recruitment_url": item.get("recruitment_url"),
                "announcement_url": item.get("announcement_url"),
                "result_status": item.get("result_status"),
                "level_1": item.get("level_1"),
                "level_2": item.get("level_2"),
                "level_3": item.get("level_3") or "",
                "category_id": item.get("category_id"),
                "reason": item.get("reason"),
            })
    return items


def main() -> None:
    projection = json.loads(PROJECTION_PATH.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    updates = json.loads(UPDATES_PATH.read_text(encoding="utf-8")) if UPDATES_PATH.exists() else {"batches": []}
    baseline, missing_date, baseline_candidates, multi_placement_atomic_units = baseline_items(projection, evidence, snapshot_dates())
    updates_items = update_items(updates)
    all_items = {item["daily_item_id"]: item for item in baseline}
    all_items.update({item["daily_item_id"]: item for item in updates_items})
    items = sorted(all_items.values(), key=lambda item: (item["source_updated_at"], item["daily_item_id"]), reverse=True)
    output = {
        "schema_version": "daily-jobs-v1",
        "date_from": DATE_FROM,
        "date_field": "source_updated_at",
        "notes": [
            "User-facing daily browsing uses source record update dates, not import or batch timestamps.",
            "Baseline and imported updates are both included; technical batch identity is omitted.",
        ],
        "statistics": {
            "items": len(items),
            "baseline_items": len(baseline),
            "update_items": len(updates_items),
            "baseline_atomic_candidates": baseline_candidates,
            "baseline_atomic_units_with_multiple_effective_display_roles": multi_placement_atomic_units,
            "baseline_atomic_units_missing_source_date": missing_date,
            "dates": len({item["source_updated_at"] for item in items}),
            "by_status": dict(Counter(item["result_status"] for item in items)),
        },
        "items": items,
    }
    write_json(OUTPUT_PATH, output)
    print(json.dumps(output["statistics"], ensure_ascii=False))


if __name__ == "__main__":
    main()
