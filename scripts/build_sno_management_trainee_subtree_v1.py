"""Create display-only L2 bubbles below the management-trainee holding group.

The frozen Reference Taxonomy and the existing name-level mapping are left
unchanged.  This only partitions a root holding bubble using explicit career
direction terms already present in the displayed occupation name.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data/processed/record_role_classification_v1/targeted_name_repairs/name_only_targeted_repair_v1"
SOURCE = DATA_DIR / "display_projection_v4.json"
OUTPUT = DATA_DIR / "display_projection_v5.json"
PARENT_ID = "holding:management-trainee"
PARENT_LABEL = "管理培训与储备岗位"


GROUPS = (
    ("technology", "技术研发与工程培训生", r"研发|技术|工程|开发|软件|信息|数字化|数据|\bai\b|智能|编程|实验|科技"),
    ("supply", "供应链制造与现场运营培训生", r"供应链|采购|仓储|物流|工厂|制造|生产|设备|工艺|基地"),
    ("business", "业务市场与产品培训生", r"业务|商务|销售|市场|客户|商业|电商|运营|产品|企划|服务|交付|拓展|品牌|消费"),
    ("functional", "职能管理与战略培训生", r"职能|战略|人力|财务|法务|行政|审计|风控|总部|中台|后备干部|总裁办|党群|企业管理"),
    ("professional", "专业培养岗位", r"飞行|客舱|博士|校长|学术|艺术创作|影像|农化|安全类"),
)


def write_exclusive(path: Path, payload: dict) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def group_for_name(name: str) -> tuple[str, str]:
    """Return one direction only when the name itself contains its evidence."""
    folded = name.casefold()
    for key, label, expression in GROUPS:
        if re.search(expression, folded, flags=re.IGNORECASE):
            return key, label
    return "general", "通用与未明确方向培训生"


def atomic_ids(rows: list[dict]) -> set[str]:
    return {atomic_id for row in rows for atomic_id in row["source_atomic_unit_ids"]}


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    projection = json.loads(SOURCE.read_text(encoding="utf-8"))
    parent = projection["holding_bubbles"].get(PARENT_ID)
    if not parent:
        raise KeyError(f"missing holding bubble {PARENT_ID}")

    partitions: dict[str, dict] = {}
    for row in parent["occupations"]:
        key, label = group_for_name(row["label"])
        bucket = partitions.setdefault(key, {
            "bucket_id": f"holding:level_1:{PARENT_LABEL}:{key}",
            "label": label,
            "display_only": True,
            "parent_level": "level_1",
            "parent_id": PARENT_LABEL,
            "level_1": PARENT_LABEL,
            "holding_note": "展示层按岗位名称中明确出现的培养方向划分；不改变正式职业目录或岗位映射状态。",
            "occupations": [],
        })
        bucket["occupations"].append(row)

    for bucket in partitions.values():
        bucket["occupations"].sort(key=lambda row: (row["label"], row["standard_occupation_id"]))
        bucket["status_counts"] = dict(sorted(Counter(row["status"] for row in bucket["occupations"]).items()))

    children = list(partitions.values())
    input_ids = {row["standard_occupation_id"] for row in parent["occupations"]}
    output_ids = {row["standard_occupation_id"] for bucket in children for row in bucket["occupations"]}
    if input_ids != output_ids:
        raise ValueError("management-trainee standard-occupation coverage is not exact")
    if sum(len(bucket["occupations"]) for bucket in children) != len(output_ids):
        raise ValueError("management-trainee standard occupations appear in more than one L2 bubble")
    if atomic_ids(parent["occupations"]) != atomic_ids([row for bucket in children for row in bucket["occupations"]]):
        raise ValueError("management-trainee atomic-role coverage is not exact")

    level1_holding = dict(projection.get("level1_holding_bubbles", {}))
    for bucket in children:
        if bucket["bucket_id"] in level1_holding:
            raise ValueError(f"duplicate level-1 holding bucket {bucket['bucket_id']}")
        level1_holding[bucket["bucket_id"]] = bucket

    projection["level1_holding_bubbles"] = dict(sorted(level1_holding.items()))
    projection["schema_version"] = "name-only-display-projection-v5"
    projection["source_projection"] = str(SOURCE.relative_to(ROOT)).replace("\\", "/")
    projection["validation"] = {
        **projection["validation"],
        "management_trainee_l2_display_group_count": len(children),
        "management_trainee_l2_display_entry_count": len(input_ids),
        "management_trainee_l2_atomic_role_count": len(atomic_ids(parent["occupations"])),
        "management_trainee_l2_display_only_notice": "These are UI-only L2 holding groups; they do not modify the frozen Reference Taxonomy.",
    }
    write_exclusive(OUTPUT, projection)
    print(json.dumps({
        "output": str(OUTPUT),
        "groups": [{"label": bucket["label"], "standard_name_count": len(bucket["occupations"]), "atomic_role_count": len(atomic_ids(bucket["occupations"]))} for bucket in children],
        "coverage": {"standard_occupations": len(input_ids), "atomic_roles": len(atomic_ids(parent["occupations"]))},
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
