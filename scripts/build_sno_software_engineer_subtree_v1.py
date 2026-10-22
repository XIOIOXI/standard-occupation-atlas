"""Create a display-only Internet/AI -> Software Engineer grouping.

The frozen taxonomy is not changed: this is a transparent presentation layer
placement for generic software-development titles that cannot safely be split
into frontend, backend, client, test, or algorithm categories by name alone.
"""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data/processed/record_role_classification_v1/targeted_name_repairs/name_only_targeted_repair_v1"
SOURCE = DATA_DIR / "display_projection_v3.json"
OUTPUT = DATA_DIR / "display_projection_v4.json"

# Reviewed individually against their names.  IDs are used instead of a broad
# substring rule so degree requirements and compound/garbled titles are not
# silently pulled into the software-development display node.
SOFTWARE_OCCUPATION_IDS = {
    "SNO-4b91e485b275dd6b8414",  # 软件开发工程师（应用）
    "SNO-f26a75507c42865986c3",  # 初级软件工程师
    "SNO-73fbc359b92781f9660b",  # 平台软件工程师
    "SNO-8cabe38d46d6a45d1f8c",  # 软件工程师
    "SNO-f529d508a973a400a7d5",  # 软件开发工程师
    "SNO-4cd0c0b3acd26b891424",  # 软件开发工程师（通用/数据库方向）
    "SNO-cda5293603b05e57003e",  # 软件开发实习生
    "SNO-148abbbc5f1d7d01cc33",  # 软件设计工程师
    "SNO-4060b274415170aaa2ec",  # 系统软件助理工程师
    "SNO-f4afeed4efca2c54a5ae",  # 新能源软件开发助理工程师
    "SNO-a2b8de26514c068f59e5",  # 主任软件工程师
}


def write_exclusive(path: Path, payload) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    holding = source["holding_bubbles"]
    generic = holding["holding:general-technology"]
    by_id = {row["standard_occupation_id"]: row for row in generic["occupations"]}
    missing = SOFTWARE_OCCUPATION_IDS - set(by_id)
    if missing:
        raise ValueError(f"software candidates are not in the generic-technology holding group: {sorted(missing)}")

    selected = [row for row in generic["occupations"] if row["standard_occupation_id"] in SOFTWARE_OCCUPATION_IDS]
    generic["occupations"] = [row for row in generic["occupations"] if row["standard_occupation_id"] not in SOFTWARE_OCCUPATION_IDS]
    generic["status_counts"] = {"review": len(generic["occupations"])}
    selected.sort(key=lambda row: (row["label"], row["standard_occupation_id"]))

    source["level1_holding_bubbles"] = {
        "holding:level_1:互联网/AI:software-engineer": {
            "bucket_id": "holding:level_1:互联网/AI:software-engineer",
            "label": "软件工程师",
            "display_only": True,
            "parent_level": "level_1",
            "parent_id": "互联网/AI",
            "level_1": "互联网/AI",
            "holding_note": "名称明确属于通用软件开发，但未提供足以区分前端、后端、客户端或测试的方向证据。",
            "occupations": selected,
            "status_counts": {"review": len(selected)},
        }
    }
    source["schema_version"] = "name-only-display-projection-v4"
    source["source_projection"] = str(SOURCE.relative_to(ROOT)).replace("\\", "/")
    source["validation"] = {
        **source["validation"],
        "internet_ai_software_engineer_display_entry_count": len(selected),
        "internet_ai_software_engineer_display_only_notice": "This is a display-only L2 grouping, not a new Reference Taxonomy category.",
    }
    write_exclusive(OUTPUT, source)
    print(json.dumps({
        "output": str(OUTPUT),
        "moved_entry_count": len(selected),
        "labels": [row["label"] for row in selected],
        "remaining_general_technology_count": len(generic["occupations"]),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
