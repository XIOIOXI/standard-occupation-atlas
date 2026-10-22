"""Build a deterministic, browser-readable job-search index.

The index is a read-only projection of already persisted recruitment records,
atomic-job evidence, governed directory placements, and completed update
batches.  It never calls an LLM and never changes source data.
"""
from __future__ import annotations

import json
import hashlib
import re
import sqlite3
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DISPLAY_DIR = ROOT / "data/processed/record_role_classification_v1/full_drafts/sno_v31_reasonable_primary_v4_display"
PROJECTION_PATH = DISPLAY_DIR / "display_projection_v31_full_draft.json"
EVIDENCE_PATH = DISPLAY_DIR / "sno_atomic_evidence_index_v1.json"
UPDATES_PATH = DISPLAY_DIR / "update_batches.json"
SNAPSHOTS_PATH = ROOT / "data/processed/recruitment_snapshots.sqlite"
OUTPUT_PATH = DISPLAY_DIR / "job_search_index_v1.json"
META_PATH = DISPLAY_DIR / "job_search_index_v1.meta.json"
FACETS_PATH = DISPLAY_DIR / "job_search_facets_v1.json"
GEOJSON_DIR = ROOT / "frontend/node_modules/china-geojson/src/geojson"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as output:
        json.dump(value, output, ensure_ascii=False, indent=2)
        output.write("\n")
        temporary = Path(output.name)
    temporary.replace(path)


def category_items(projection: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for bucket in projection.get("category_bubbles", {}).values():
        rows.extend((bucket["category"], item) for item in bucket.get("occupations", []))
    for bucket in projection.get("level2_direct_buckets", {}).values():
        rows.extend((bucket["category"], item) for item in bucket.get("occupations", []))
    return rows


def category_path(category: dict[str, Any]) -> dict[str, str | None]:
    return {
        "category_id": category.get("category_id"),
        "level_1": category.get("level_1"),
        "level_2": category.get("display_level_2") or category.get("level_2"),
        "level_3": category.get("level_3") or None,
    }


def snapshot_records() -> dict[str, dict[str, Any]]:
    with sqlite3.connect(SNAPSHOTS_PATH) as connection:
        connection.row_factory = sqlite3.Row
        snapshot = connection.execute("SELECT snapshot_id FROM dataset_snapshots ORDER BY imported_at DESC LIMIT 1").fetchone()
        if not snapshot:
            raise RuntimeError("Recruitment snapshot is unavailable; search index was not changed.")
        rows = connection.execute(
            """SELECT record_id, company_name, company_type, industry_category, location,
                      recruitment_session, recruitment_batch, updated_at, deadline,
                      education_requirement, major_requirement, recruitment_url, announcement_url
                 FROM recruitment_records
                WHERE snapshot_id = ?""",
            (snapshot["snapshot_id"],),
        ).fetchall()
    return {row["record_id"]: dict(row) for row in rows}


def append_path(paths: dict[str, list[dict[str, str | None]]], atomic_id: str, path: dict[str, str | None]) -> None:
    if atomic_id and path not in paths[atomic_id]:
        paths[atomic_id].append(path)


def baseline_paths(projection: dict[str, Any]) -> tuple[dict[str, list[dict[str, str | None]]], set[str]]:
    paths: dict[str, list[dict[str, str | None]]] = defaultdict(list)
    pending: set[str] = set()
    for category, occupation in category_items(projection):
        for atomic_id in occupation.get("source_atomic_unit_ids", []):
            append_path(paths, atomic_id, category_path(category))
    for occupation in projection.get("unplaced", []):
        pending.update(occupation.get("source_atomic_unit_ids", []))
    return paths, pending


def build_baseline_items(projection: dict[str, Any], evidence: dict[str, Any], records: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    paths, pending = baseline_paths(projection)
    atomic_units = evidence.get("atomic_units", {})
    items: list[dict[str, Any]] = []
    for atomic_id in sorted(set(paths) | pending):
        source = atomic_units.get(atomic_id)
        if not source:
            continue
        record = records.get(source.get("source_record_id"), {})
        item_paths = paths.get(atomic_id, [])
        items.append({
            "search_item_id": f"BASE:{atomic_id}",
            "source_atomic_unit_id": atomic_id,
            "source_record_id": source.get("source_record_id"),
            "title_unit": source.get("job_title_unit"),
            "raw_job_title": source.get("raw_job_title"),
            "company_name": source.get("company_name") or record.get("company_name"),
            "company_type": source.get("company_type") or record.get("company_type"),
            "location": source.get("location") or record.get("location"),
            "industry_category": record.get("industry_category"),
            "recruitment_session": record.get("recruitment_session"),
            "recruitment_batch": record.get("recruitment_batch"),
            "source_updated_at": record.get("updated_at"),
            "deadline": record.get("deadline"),
            "education_requirement": source.get("education_requirement") or record.get("education_requirement"),
            "major_requirement": record.get("major_requirement"),
            "recruitment_url": source.get("recruitment_url") or record.get("recruitment_url"),
            "announcement_url": source.get("announcement_url") or record.get("announcement_url"),
            "result_status": "classified" if item_paths else "pending",
            "category_paths": item_paths,
            "reason": None if item_paths else "现有目录中待确认的岗位",
            "source_kind": "baseline",
        })
    return items


def build_update_items(updates: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for batch in updates.get("batches", []):
        if batch.get("status") not in {"completed", "completed_with_failures"}:
            continue
        for item in batch.get("items", []):
            if item.get("result_status") not in {"classified", "pending"}:
                continue
            path = {
                "category_id": item.get("category_id"), "level_1": item.get("level_1"),
                "level_2": item.get("level_2"), "level_3": item.get("level_3") or None,
            }
            items.append({
                "search_item_id": f"UPDATE:{batch['batch_id']}:{item['atomic_key']}",
                "source_atomic_unit_id": item.get("atomic_key"),
                "source_record_id": item.get("source_record_id"),
                "title_unit": item.get("title_unit"), "raw_job_title": item.get("raw_job_title"),
                "company_name": item.get("company_name"), "company_type": item.get("company_type"),
                "location": item.get("location"), "industry_category": item.get("industry_category"),
                "recruitment_session": item.get("recruitment_session"), "recruitment_batch": item.get("recruitment_batch"),
                "source_updated_at": item.get("source_updated_at"), "deadline": item.get("deadline"),
                "education_requirement": item.get("education_requirement"), "major_requirement": item.get("major_requirement"),
                "recruitment_url": item.get("recruitment_url"), "announcement_url": item.get("announcement_url"),
                "result_status": item.get("result_status"),
                "category_paths": [path] if item.get("result_status") == "classified" and path["category_id"] else [],
                "reason": item.get("reason"), "source_kind": "update",
            })
    return items


def build_taxonomy(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    levels: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for item in items:
        for path in item.get("category_paths", []):
            level_1, level_2, level_3 = path.get("level_1"), path.get("level_2"), path.get("level_3")
            if level_1 and level_2 and level_3:
                levels[level_1][level_2].add(level_3)
            elif level_1 and level_2:
                levels[level_1][level_2]
    return [
        {"level1": level_1, "groups": [{"label": level_2, "roles": sorted(roles)} for level_2, roles in sorted(groups.items())]}
        for level_1, groups in sorted(levels.items())
    ]


def verified_china_localities() -> set[str]:
    localities: set[str] = set()
    if not GEOJSON_DIR.exists():
        return localities
    for path in GEOJSON_DIR.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        for feature in data.get("features", []):
            name = str(feature.get("properties", {}).get("name") or "")
            if name:
                localities.add(name)
                localities.add(re.sub(r"[市地区盟州县]$", "", name))
    return localities


def build_location_facets(items: list[dict[str, Any]]) -> dict[str, list[str]]:
    verified = verified_china_localities()
    locations = sorted({str(item.get("location") or "").strip() for item in items if str(item.get("location") or "").strip()})
    cities: set[str] = set()
    for location in locations:
        for token in re.split(r"[，,、/;；\s]+", location):
            if re.fullmatch(r"[\u4e00-\u9fff]{2,8}", token) and token in verified:
                cities.add(token)
    return {"location_values": locations, "city_options": sorted(cities)}


def main() -> None:
    projection = json.loads(PROJECTION_PATH.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    updates = json.loads(UPDATES_PATH.read_text(encoding="utf-8")) if UPDATES_PATH.exists() else {"batches": []}
    items = build_baseline_items(projection, evidence, snapshot_records()) + build_update_items(updates)
    items.sort(key=lambda item: (item.get("source_updated_at") or "", item["search_item_id"]), reverse=True)
    output = {
        "schema_version": "job-search-index-v1",
        "notes": [
            "Built deterministically from persisted recruitment records and governed display placements.",
            "Search results preserve source fields and never infer recruitment facts.",
        ],
        "statistics": {
            "items": len(items), "baseline_items": sum(item["source_kind"] == "baseline" for item in items),
            "update_items": sum(item["source_kind"] == "update" for item in items),
            "by_status": dict(Counter(item["result_status"] for item in items)),
        },
        "items": items,
    }
    canonical = json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    content_hash = hashlib.sha256(canonical).hexdigest()
    write_json(OUTPUT_PATH, output)
    write_json(META_PATH, {
        "schema_version": "job-search-index-meta-v1",
        "content_hash": content_hash,
        "statistics": output["statistics"],
    })
    write_json(FACETS_PATH, {
        "schema_version": "job-search-facets-v1",
        "content_hash": content_hash,
        "taxonomy": build_taxonomy(items),
        **build_location_facets(items),
    })
    print(json.dumps(output["statistics"], ensure_ascii=False))


if __name__ == "__main__":
    main()
