"""Add display-only names for redundant SNO hierarchy labels.

This preserves frozen taxonomy names and IDs.  The added ``display_level_2``
field is consumed only by the SNO UI.
"""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data/processed/record_role_classification_v1/targeted_name_repairs/name_only_targeted_repair_v1"
SOURCE = DATA_DIR / "display_projection_v8.json"
OUTPUT = DATA_DIR / "display_projection_v9.json"
CHANGE_LOG = DATA_DIR / "display_projection_v9_display_name_aliases.json"

SALES_GENERAL = "销售/sales-general"
DISPLAY_NAME = "销售业务"


def write_exclusive(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> None:
    if OUTPUT.exists() or CHANGE_LOG.exists():
        raise FileExistsError("Refusing to overwrite existing v9 display alias artifacts")
    projection = json.loads(SOURCE.read_text(encoding="utf-8"))
    changed = []
    for category_id, bubble in projection["category_bubbles"].items():
        if category_id.rsplit("/", 1)[0] != SALES_GENERAL:
            continue
        category = bubble["category"]
        if category["level_1"] != "销售" or category["level_2"] != "销售":
            raise ValueError(f"unexpected sales-general source label at {category_id}")
        category["display_level_2"] = DISPLAY_NAME
        changed.append({"kind": "level_3_category", "id": category_id, "canonical_level_2": "销售", "display_level_2": DISPLAY_NAME})
    other_id = f"other:level_2:{SALES_GENERAL}"
    other = projection.get("other_bubbles", {}).get(other_id)
    if not other or other.get("level_2") != "销售":
        raise ValueError("missing sales-general L2 other bucket")
    other["display_level_2"] = DISPLAY_NAME
    changed.append({"kind": "level_2_other_bucket", "id": other_id, "canonical_level_2": "销售", "display_level_2": DISPLAY_NAME})
    if len(changed) != 3:
        raise ValueError(f"expected exactly two categories plus one other bucket; changed {len(changed)}")
    projection["schema_version"] = "name-only-display-projection-v9"
    projection["source_projection"] = str(SOURCE.relative_to(ROOT)).replace("\\", "/")
    projection["validation"] = {
        **projection["validation"],
        "v9_display_name_alias_count": len(changed),
        "v9_display_name_notice": "Display aliases only; frozen taxonomy IDs and canonical names are unchanged.",
    }
    write_exclusive(OUTPUT, projection)
    write_exclusive(CHANGE_LOG, {
        "source_projection": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "output_projection": str(OUTPUT.relative_to(ROOT)).replace("\\", "/"),
        "changes": changed,
    })
    print(json.dumps({"output": str(OUTPUT), "change_log": str(CHANGE_LOG), "changed": changed}, ensure_ascii=False))


if __name__ == "__main__":
    main()
