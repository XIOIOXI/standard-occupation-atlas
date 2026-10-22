"""Merge remap batches into a new, display-only SNO projection.

The frozen taxonomy remains unchanged.  ``other_bubbles`` are UI fallback
nodes, not taxonomy categories; every entry retains its status and raw links.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path("data/processed/record_role_classification_v1")
BASE = ROOT / "targeted_name_repairs/name_only_targeted_repair_v1/full_name_only_mapping_repaired_v1.json"
TAXONOMY = ROOT / "catalog_mappings/taxonomy_embedding_texts_v1.json"
BATCH_DIR = ROOT / "targeted_name_repairs/name_only_targeted_repair_v1/deepseek_nonmapped_remap_v3"
OUT_DIR = ROOT / "targeted_name_repairs/name_only_targeted_repair_v1"
MAPPING_OUT = OUT_DIR / "full_name_only_mapping_remapped_v2.json"
DISPLAY_OUT = OUT_DIR / "display_projection_v2.json"


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_exclusive(path: Path, payload):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def public_item(row):
    return {
        "standard_occupation_id": row["standard_occupation_id"],
        "label": row["standard_name"],
        "original_group_ids": row["original_group_ids"],
        "source_atomic_unit_ids": row["source_atomic_unit_ids"],
        "source_record_ids": row["source_record_ids"],
        "status": row["status"],
        "reason": row.get("reason"),
    }


def abnormal_item(row):
    return {
        "standard_occupation_id": row["entry_id"],
        "label": row["standard_name"],
        "original_group_ids": row["original_group_ids"],
        "source_atomic_unit_ids": row["source_atomic_unit_ids"],
        "source_record_ids": row["source_record_ids"],
        "status": row["status"],
        "reason": row.get("reason"),
        "abnormal_source_group": True,
    }


def main():
    if MAPPING_OUT.exists() or DISPLAY_OUT.exists():
        raise FileExistsError("v2 mapping or display projection already exists")
    base, taxonomy = read(BASE), read(TAXONOMY)
    tax_by_l3 = {row["category_id"]: row for row in taxonomy["rows"]}
    l2_to_row = {row["category_id"].rsplit("/", 1)[0]: row for row in taxonomy["rows"]}
    l1_to_row = {row["level_1"]: row for row in taxonomy["rows"]}
    decisions = [row for path in sorted(BATCH_DIR.glob("batch_*_reviewed.json")) for row in read(path)["results"]]
    decisions_by_id = {row["entry_id"]: row for row in decisions}
    if len(decisions) != len(decisions_by_id):
        raise ValueError("duplicate remap decisions")
    expected = {row["standard_occupation_id"] for row in base["results"] if row["status"] != "mapped"}
    expected |= {f"ABNORMAL:{row['record_role_group_id']}" for row in base["unclassified_abnormal_groups"]}
    if set(decisions_by_id) != expected:
        raise ValueError(f"remap coverage mismatch: missing={len(expected-set(decisions_by_id))}, unexpected={len(set(decisions_by_id)-expected)}")

    results = []
    for row in base["results"]:
        item = dict(row)
        decision = decisions_by_id.get(row["standard_occupation_id"])
        if decision:
            item.update({
                "status": decision["status"],
                "target_category_id": decision["target_category_id"],
                "reason": decision["reason"],
                "processing_method": "deepseek_api_name_only_nonmapped_remap",
            })
        results.append(item)
    abnormal_results = []
    for group in base["unclassified_abnormal_groups"]:
        entry_id = f"ABNORMAL:{group['record_role_group_id']}"
        decision = decisions_by_id[entry_id]
        abnormal_results.append({
            "entry_id": entry_id,
            "standard_name": group["original_name"],
            "original_group_ids": [group["record_role_group_id"]],
            "source_atomic_unit_ids": group["source_atomic_unit_ids"],
            "source_record_ids": group["source_record_ids"],
            "status": decision["status"],
            "target_category_id": decision["target_category_id"],
            "reason": decision["reason"],
            "processing_method": "deepseek_api_name_only_nonmapped_remap",
        })

    mapped_by_category = defaultdict(list)
    other_by_parent = defaultdict(list)
    unplaced = []

    def add_for_display(row, item, category_field="target_category_id"):
        target = row.get(category_field)
        if row["status"] == "mapped" and target in tax_by_l3:
            mapped_by_category[target].append(item)
            return
        # A non-confirmed L3 result is intentionally demoted to its confirmed
        # level-2 parent: it remains an Other entry rather than a fake mapping.
        if target in tax_by_l3:
            parent = target.rsplit("/", 1)[0]
            parent_row = tax_by_l3[target]
            key = ("level_2", parent)
            other_by_parent[key].append((parent_row, item))
        elif target in l2_to_row:
            key = ("level_2", target)
            other_by_parent[key].append((l2_to_row[target], item))
        elif target in l1_to_row:
            key = ("level_1", target)
            other_by_parent[key].append((l1_to_row[target], item))
        else:
            unplaced.append(item)

    for row in results:
        add_for_display(row, public_item(row))
    for row in abnormal_results:
        add_for_display({**row, "standard_occupation_id": row["entry_id"]}, abnormal_item({**row, "entry_id": row["entry_id"]}))

    other_bubbles = {}
    for (level, parent_id), pairs in other_by_parent.items():
        parent_row = pairs[0][0]
        bucket_id = f"other:{level}:{parent_id}"
        other_bubbles[bucket_id] = {
            "bucket_id": bucket_id,
            "label": "其他岗位",
            "parent_level": level,
            "parent_id": parent_id,
            "level_1": parent_row["level_1"],
            "level_2": parent_row["level_2"] if level == "level_2" else None,
            "occupations": [item for _, item in pairs],
        }

    normal_atomic = [identifier for row in results for identifier in row["source_atomic_unit_ids"]]
    abnormal_atomic = [identifier for row in abnormal_results for identifier in row["source_atomic_unit_ids"]]
    all_atomic = normal_atomic + abnormal_atomic
    validation = {
        "standard_occupation_count": len(results),
        "remapped_nonconfirmed_entry_count": len(decisions),
        "normal_atomic_role_count": len(set(normal_atomic)),
        "abnormal_atomic_role_count": len(set(abnormal_atomic)),
        "all_atomic_role_count": len(set(all_atomic)),
        "expected_all_atomic_role_count": 20964,
        "atomic_role_missing_count": 20964 - len(set(all_atomic)),
        "atomic_role_duplicate_count": len(all_atomic) - len(set(all_atomic)),
        "category_id_validation": all(row["target_category_id"] is None or row["target_category_id"] in set(tax_by_l3) | set(l2_to_row) | set(l1_to_row) for row in results + abnormal_results),
    }
    if validation["atomic_role_missing_count"] or validation["atomic_role_duplicate_count"] or not validation["category_id_validation"]:
        raise ValueError(f"source linkage validation failed: {validation}")

    mapping_payload = {
        "schema_version": "name-only-remapped-mapping-v2",
        "base_mapping": str(BASE),
        "remap_batch_directory": str(BATCH_DIR),
        "classification_scope": "Name-only DeepSeek remap against the frozen taxonomy; source IDs were retained locally and not supplied to the API.",
        "results": results,
        "abnormal_results": abnormal_results,
        "status_counts": dict(Counter(row["status"] for row in results + abnormal_results)),
        "validation": validation,
    }
    projection = {
        "schema_version": "name-only-display-projection-v2",
        "source_mapping": str(MAPPING_OUT),
        "category_bubbles": {category_id: {"category": tax_by_l3[category_id], "occupations": items} for category_id, items in mapped_by_category.items()},
        "other_bubbles": other_bubbles,
        "unplaced": unplaced,
        "validation": validation,
    }
    write_exclusive(MAPPING_OUT, mapping_payload)
    write_exclusive(DISPLAY_OUT, projection)
    print(json.dumps({
        "mapping_output": str(MAPPING_OUT),
        "display_output": str(DISPLAY_OUT),
        "mapped_level_3": sum(len(items) for items in mapped_by_category.values()),
        "other_bubble_count": len(other_bubbles),
        "other_entry_count": sum(len(item["occupations"]) for item in other_bubbles.values()),
        "unplaced_entry_count": len(unplaced),
        "status_counts": mapping_payload["status_counts"],
        "validation": validation,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
