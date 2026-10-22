"""Export a compact, read-only SNO Level-1/Level-2 directory snapshot."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data/processed/record_role_classification_v1/targeted_name_repairs/name_only_targeted_repair_v1"
TAXONOMY = ROOT / "data/processed/record_role_classification_v1/catalog_mappings/taxonomy_embedding_texts_v1.json"
PROJECTION = DATA_DIR / "display_projection_v9.json"
OUTPUT = DATA_DIR / "sno_level_1_2_directory_v1.json"


def write_exclusive(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    taxonomy = json.loads(TAXONOMY.read_text(encoding="utf-8"))["rows"]
    projection = json.loads(PROJECTION.read_text(encoding="utf-8"))

    display_l2 = {}
    for item in projection["category_bubbles"].values():
        category = item["category"]
        if category.get("display_level_2"):
            display_l2[category["category_id"].rsplit("/", 1)[0]] = category["display_level_2"]
    for item in projection.get("other_bubbles", {}).values():
        if item.get("parent_level") == "level_2" and item.get("display_level_2"):
            display_l2[item["parent_id"]] = item["display_level_2"]

    directory: dict[str, dict] = {}
    for row in taxonomy:
        l1, l2 = row["level_1"], row["level_2"]
        l2_id = row["category_id"].rsplit("/", 1)[0]
        parent = directory.setdefault(l1, {"level_1_id": l1, "level_1_name": l1, "level_2": {}})
        child = parent["level_2"].setdefault(l2_id, {
            "level_2_id": l2_id,
            "canonical_name": l2,
            "display_name": display_l2.get(l2_id, l2),
            "level_3_category_count": 0,
        })
        child["level_3_category_count"] += 1

    formal = []
    for root in sorted(directory.values(), key=lambda item: item["level_1_name"]):
        level2 = sorted(root.pop("level_2").values(), key=lambda item: item["display_name"])
        formal.append({**root, "kind": "formal_taxonomy", "level_2": level2})

    holding_children: dict[str, list[dict]] = {}
    for bucket in projection.get("level1_holding_bubbles", {}).values():
        holding_children.setdefault(bucket["parent_id"], []).append({
            "level_2_id": bucket["bucket_id"], "display_name": bucket["label"],
            "kind": "display_only_holding", "note": bucket.get("holding_note"),
        })
    holding = []
    for bucket in projection.get("holding_bubbles", {}).values():
        holding.append({
            "level_1_id": bucket["bucket_id"], "level_1_name": bucket["label"], "kind": "display_only_holding",
            "note": bucket.get("holding_note"),
            "level_2": sorted(holding_children.get(bucket["label"], []), key=lambda item: item["display_name"]),
        })

    output = {
        "schema_version": "sno-level-1-2-directory-v1",
        "source_taxonomy": str(TAXONOMY.relative_to(ROOT)).replace("\\", "/"),
        "source_display_projection": str(PROJECTION.relative_to(ROOT)).replace("\\", "/"),
        "notice": "Formal taxonomy is frozen. Display-only holding groups are listed separately and do not alter formal Level-1/Level-2 categories.",
        "formal_taxonomy": formal,
        "display_only_holding_groups": sorted(holding, key=lambda item: item["level_1_name"]),
        "summary": {
            "formal_level_1_count": len(formal),
            "formal_level_2_count": sum(len(item["level_2"]) for item in formal),
            "display_only_level_1_group_count": len(holding),
            "display_only_level_2_group_count": sum(len(item["level_2"]) for item in holding),
        },
    }
    write_exclusive(OUTPUT, output)
    print(json.dumps({"output": str(OUTPUT), "summary": output["summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
