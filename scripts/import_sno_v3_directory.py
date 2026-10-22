"""Import and validate the user-approved SNO v3 directory design.

This creates a *directory-only* taxonomy snapshot.  It deliberately does not
reclassify recruitment records or migrate prior OCC/SNO placements: v3 changes
the governing classification rule, so an old placement is at most review
context, never a valid automatic migration.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(r"C:\Users\25223\Downloads\SNO职业目录一二三级_v3.md")
DESTINATION = ROOT / "data" / "taxonomy" / "sno_v3"
SNAPSHOT = DESTINATION / "SNO职业目录一二三级_v3.md"
CATALOG = DESTINATION / "sno_occupation_catalog_v3.json"
MIGRATION_POLICY = DESTINATION / "migration_policy_v3.json"

L1_PATTERN = re.compile(r"^### (L\d{2}) (.+)$")
L2_PATTERN = re.compile(r"^#### (L\d{2}-\d{2}) (.+)$")
L3_PATTERN = re.compile(r"^\| (L\d{2}-\d{2}-\d{2}) \| (.+?) \| (.+?) \|$")


def fail(message: str) -> None:
    raise ValueError(f"Invalid SNO v3 directory: {message}")


def parse(source: str) -> list[dict]:
    level_1: list[dict] = []
    current_l1: dict | None = None
    current_l2: dict | None = None
    pending_scope = False

    for raw_line in source.splitlines():
        line = raw_line.strip()
        l1 = L1_PATTERN.match(line)
        if l1:
            current_l1 = {"level_1_id": l1.group(1), "name": l1.group(2), "level_2": []}
            level_1.append(current_l1)
            current_l2 = None
            continue
        l2 = L2_PATTERN.match(line)
        if l2:
            if current_l1 is None:
                fail(f"{l2.group(1)} appears before a level 1 node")
            if not l2.group(1).startswith(f"{current_l1['level_1_id']}-"):
                fail(f"{l2.group(1)} is not a child of {current_l1['level_1_id']}")
            current_l2 = {"level_2_id": l2.group(1), "name": l2.group(2), "scope": None, "level_3": []}
            current_l1["level_2"].append(current_l2)
            pending_scope = False
            continue
        if line.startswith("二级范围："):
            if current_l2 is None:
                fail("a level-2 scope has no level-2 node")
            current_l2["scope"] = line.removeprefix("二级范围：")
            pending_scope = True
            continue
        l3 = L3_PATTERN.match(line)
        if l3:
            if current_l2 is None:
                fail(f"{l3.group(1)} appears before a level 2 node")
            if not l3.group(1).startswith(f"{current_l2['level_2_id']}-"):
                fail(f"{l3.group(1)} is not a child of {current_l2['level_2_id']}")
            current_l2["level_3"].append({"level_3_id": l3.group(1), "name": l3.group(2), "scope": l3.group(3)})

    if not level_1:
        fail("no formal level-1 nodes were parsed")
    for l1 in level_1:
        if not l1["level_2"]:
            fail(f"{l1['level_1_id']} has no level-2 nodes")
        for l2 in l1["level_2"]:
            if not l2["scope"]:
                fail(f"{l2['level_2_id']} has no scope")
    return level_1


def assert_unique(nodes: list[dict]) -> None:
    ids = [node["level_1_id"] for node in nodes]
    ids += [node["level_2_id"] for l1 in nodes for node in l1["level_2"]]
    ids += [node["level_3_id"] for l1 in nodes for l2 in l1["level_2"] for node in l2["level_3"]]
    duplicates = sorted(identifier for identifier, count in Counter(ids).items() if count > 1)
    if duplicates:
        fail(f"duplicate directory IDs: {duplicates}")


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(f"The supplied v3 directory is unavailable: {SOURCE}")
    if any(path.exists() for path in (SNAPSHOT, CATALOG, MIGRATION_POLICY)):
        raise FileExistsError("Refusing to overwrite an existing SNO v3 taxonomy snapshot")
    text = SOURCE.read_text(encoding="utf-8")
    taxonomy = parse(text)
    assert_unique(taxonomy)
    level_2_count = sum(len(node["level_2"]) for node in taxonomy)
    level_3_count = sum(len(node["level_3"]) for node in taxonomy for node in node["level_2"])
    DESTINATION.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE, SNAPSHOT)
    source_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    catalog = {
        "schema_version": "sno-occupation-catalog-v3",
        "taxonomy_version": "sno-v3-directory-design",
        "status": "directory_design_pending_data_validation",
        "source": {"file": "SNO职业目录一二三级_v3.md", "sha256": source_hash},
        "counts": {"level_1": len(taxonomy), "level_2": level_2_count, "level_3": level_3_count, "level_2_direct_only": level_2_count - sum(bool(node["level_3"]) for l1 in taxonomy for node in l1["level_2"])},
        "classification_contract": {
            "one_primary_level_2_per_atomic_role": True,
            "level_1_is_derived_from_level_2": True,
            "level_3_is_optional": True,
            "industry_technology_and_seniority_are_tags_not_directory_nodes": True,
            "unconfirmed_roles_remain_reviewable_not_forced_into_a_category": True,
        },
        "taxonomy": taxonomy,
    }
    policy = {
        "schema_version": "sno-v3-migration-policy-v1",
        "new_taxonomy_version": catalog["taxonomy_version"],
        "old_occ_sno_placements": "deprecated_for_display_and_not_auto_migratable",
        "why": "V3 replaces the placement principle. Old groups may mix roles that v3 intentionally separates by core responsibility.",
        "required_reclassification_unit": "atomic_role_with_original_record_evidence",
        "preserve": ["original_record_id", "atomic_role_id", "original_title", "legacy_placement_as_review_context"],
        "do_not_do": ["bulk_copy_old_category", "duplicate_role_into_multiple_primary_bubbles", "infer_primary_category_from_industry_or_technology_tag"],
    }
    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    MIGRATION_POLICY.write_text(json.dumps(policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"catalog": str(CATALOG.relative_to(ROOT)), "counts": catalog["counts"], "source_sha256": source_hash}, ensure_ascii=False))


if __name__ == "__main__":
    main()
