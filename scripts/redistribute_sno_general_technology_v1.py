"""Remove the root-level generic R&D holding bubble from the SNO UI.

Only the display projection changes.  Explicit name evidence places a subset
under existing primary-domain bubbles.  The remaining broad R&D titles are
kept reachable through ``其他职业 -> 研发与工程其他岗位`` rather than being
misrepresented as Internet/AI, manufacturing, or hardware work.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data/processed/record_role_classification_v1/targeted_name_repairs/name_only_targeted_repair_v1"
SOURCE = DATA_DIR / "display_projection_v6.json"
OUTPUT = DATA_DIR / "display_projection_v7.json"
PARENT_ID = "holding:general-technology"


DESTINATIONS = (
    ("互联网/AI", "软件与数字技术", "software-digital", r"软件|程序|开发|信息|数据|数字化|算法|\bai\b|智能|网络|系统|云|it|计算机|代码"),
    ("电子/电气/通信", "电子电气与硬件技术", "hardware", r"电子|电气|硬件|通信|集成电路|芯片|光电|射频|嵌入式|自动化"),
    ("生产制造", "机械制造与工艺工程", "manufacturing", r"机械|制造|设备|工艺|生产|装备|模具|机电|车辆"),
    ("房地产/建筑", "建筑基础设施与环境工程", "infrastructure", r"建筑|土木|测量|勘察|市政|水利|环境|暖通|结构"),
    ("其他职业", "研发与工程其他岗位", "other-rnd", None),
)


def write_exclusive(path: Path, payload: dict) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def atomic_ids(rows: list[dict]) -> set[str]:
    return {atomic_id for row in rows for atomic_id in row["source_atomic_unit_ids"]}


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    projection = json.loads(SOURCE.read_text(encoding="utf-8"))
    parent = projection["holding_bubbles"].get(PARENT_ID)
    if not parent:
        raise KeyError(f"missing root holding group {PARENT_ID}")

    buckets: dict[str, dict] = {}
    for row in parent["occupations"]:
        folded = row["label"].casefold()
        primary, label, suffix, expression = next(
            (item for item in DESTINATIONS if item[3] is None or re.search(item[3], folded, flags=re.IGNORECASE))
        )
        bucket = buckets.setdefault(suffix, {
            "bucket_id": f"holding:level_1:{primary}:{suffix}",
            "label": label,
            "display_only": True,
            "parent_level": "level_1",
            "parent_id": primary,
            "level_1": primary,
            "holding_note": "原一级暂存组已移除。展示层仅按名称中明确可辨的方向迁入现有一级；其余保留在“其他职业”，不强行归类。",
            "occupations": [],
        })
        bucket["occupations"].append(row)

    result_buckets = list(buckets.values())
    for bucket in result_buckets:
        bucket["occupations"].sort(key=lambda row: (row["label"], row["standard_occupation_id"]))
        bucket["status_counts"] = dict(sorted(Counter(row["status"] for row in bucket["occupations"]).items()))

    before_standard_ids = {row["standard_occupation_id"] for row in parent["occupations"]}
    output_rows = [row for bucket in result_buckets for row in bucket["occupations"]]
    after_standard_ids = {row["standard_occupation_id"] for row in output_rows}
    if before_standard_ids != after_standard_ids or len(output_rows) != len(after_standard_ids):
        raise ValueError("general-technology standard-occupation coverage is not exact")
    if atomic_ids(parent["occupations"]) != atomic_ids(output_rows):
        raise ValueError("general-technology atomic-role coverage is not exact")

    holding = dict(projection["holding_bubbles"])
    del holding[PARENT_ID]
    # v6 had temporary children below the group being removed.  Replace them
    # with the new children below existing primary domains.
    level1_holding = {
        key: value for key, value in projection.get("level1_holding_bubbles", {}).items()
        if value.get("parent_id") != parent["label"]
    }
    for bucket in result_buckets:
        if bucket["bucket_id"] in level1_holding:
            raise ValueError(f"duplicate destination holding bucket {bucket['bucket_id']}")
        level1_holding[bucket["bucket_id"]] = bucket

    projection["holding_bubbles"] = dict(sorted(holding.items()))
    projection["level1_holding_bubbles"] = dict(sorted(level1_holding.items()))
    projection["schema_version"] = "name-only-display-projection-v7"
    projection["source_projection"] = str(SOURCE.relative_to(ROOT)).replace("\\", "/")
    projection["validation"] = {
        **projection["validation"],
        "general_technology_root_holding_removed": True,
        "general_technology_redistributed_standard_name_count": len(before_standard_ids),
        "general_technology_redistributed_atomic_role_count": len(atomic_ids(parent["occupations"])),
        "general_technology_redistribution_notice": "This is a display-only redistribution; broad titles remain under 其他职业 instead of being force-mapped to a formal domain.",
    }
    write_exclusive(OUTPUT, projection)
    print(json.dumps({
        "output": str(OUTPUT),
        "removed_root_label": parent["label"],
        "destinations": [{"level_1": bucket["level_1"], "level_2": bucket["label"], "standard_name_count": len(bucket["occupations"]), "atomic_role_count": len(atomic_ids(bucket["occupations"]))} for bucket in result_buckets],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
