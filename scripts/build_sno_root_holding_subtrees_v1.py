"""Add safe display-only L2 navigation below root SNO holding bubbles.

This is deliberately a presentation projection.  It never changes the frozen
Reference Taxonomy, the name-level mapping, or raw atomic job records.  A name
is placed only when it contains an explicit occupational theme; anything else
remains in that holding group's catch-all L2 bubble.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data/processed/record_role_classification_v1/targeted_name_repairs/name_only_targeted_repair_v1"
SOURCE = DATA_DIR / "display_projection_v5.json"
OUTPUT = DATA_DIR / "display_projection_v6.json"


# Each entry is (stable display suffix, L2 label, explicit-name regex).  The
# last group is a catch-all and therefore has a null regex.
SUBTREE_RULES = {
    "holding:general-technology": (
        ("digital", "软件数据与数字技术", r"软件|程序|开发|信息|数据|数字化|算法|\bai\b|智能|网络|系统|云|it|计算机|代码"),
        ("hardware", "电子电气与硬件技术", r"电子|电气|硬件|通信|集成电路|芯片|光电|射频|嵌入式|自动化"),
        ("manufacturing", "机械制造与工艺工程", r"机械|制造|设备|工艺|生产|装备|模具|机电|车辆"),
        ("science", "材料化学与科研", r"材料|化学|生物|科研|研究员|实验|仿真|博士后|科学"),
        ("infrastructure", "建筑基础设施与环境工程", r"建筑|土木|测量|勘察|市政|水利|环境|暖通|结构"),
        ("quality", "测试质量与技术支持", r"测试|质量|检验|可靠|售后|技术支持|应用工程"),
        ("general", "通用研发与工程岗位", None),
    ),
    "holding:general-business": (
        ("product_ops", "产品项目与运营岗位", r"产品|项目|运营|策划|企划"),
        ("market_sales", "市场销售与客户业务岗位", r"市场|销售|营销|客户|商务|品牌|公关|渠道"),
        ("functional", "职能管理与综合支持岗位", r"人力|行政|财务|法务|审计|风控|战略|管理|秘书|董秘|党建|保密|法规"),
        ("trade_supply", "贸易供应链与商业服务岗位", r"贸易|采购|供应链|物流|跟单|商业|服务|业务支持"),
        ("general", "通用业务与未明确方向岗位", None),
    ),
    "holding:taxonomy-gap": (
        ("frontier", "先进技术与科研岗位", r"新材料|量子|火箭|发射|能谱|防伪|电池|科研|研究员"),
        ("engineering", "工程设施与交通岗位", r"采矿|船舶|锅炉|暖通|适航|签派|空勤|机坪|工程师|设计"),
        ("public", "公共事务与社会服务岗位", r"党建|党工团|纪检|监察|民警|气象|社会工作|监管"),
        ("specialist", "文化与专业服务岗位", r"藏品|考古|认证|注册|董事会|核保"),
        ("general", "其他目录缺口岗位", None),
    ),
    "holding:unresolved": (
        ("technical", "技术与研究线索岗位", r"科技|技术|信息|科研|材料|工程|数字|数据|标准制定"),
        ("business", "业务市场与发展线索岗位", r"业务|产业|策划|策略|商团|发展|运营|应用"),
        ("functional", "管理与职能线索岗位", r"经理|管理|专员|助理|主任|部门|部[门专]|统筹"),
        ("general", "名称不完整或未明确岗位", None),
    ),
}


def write_exclusive(path: Path, payload: dict) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def atomic_ids(rows: list[dict]) -> set[str]:
    return {atomic_id for row in rows for atomic_id in row["source_atomic_unit_ids"]}


def split_parent(parent: dict, rules: tuple[tuple[str, str, str | None], ...]) -> list[dict]:
    children: dict[str, dict] = {}
    for row in parent["occupations"]:
        folded = row["label"].casefold()
        suffix, label = next(
            (key, title) for key, title, expression in rules
            if expression is None or re.search(expression, folded, flags=re.IGNORECASE)
        )
        bucket = children.setdefault(suffix, {
            "bucket_id": f"holding:level_1:{parent['label']}:{suffix}",
            "label": label,
            "display_only": True,
            "parent_level": "level_1",
            "parent_id": parent["label"],
            "level_1": parent["label"],
            "holding_note": "展示层仅按岗位名称中明确表达的主题分组；不改变正式职业目录、映射状态或原始岗位。",
            "occupations": [],
        })
        bucket["occupations"].append(row)
    result = list(children.values())
    for bucket in result:
        bucket["occupations"].sort(key=lambda row: (row["label"], row["standard_occupation_id"]))
        bucket["status_counts"] = dict(sorted(Counter(row["status"] for row in bucket["occupations"]).items()))
    return result


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    projection = json.loads(SOURCE.read_text(encoding="utf-8"))
    level1_holding = dict(projection.get("level1_holding_bubbles", {}))
    summary = []
    for parent_id, rules in SUBTREE_RULES.items():
        parent = projection["holding_bubbles"].get(parent_id)
        if not parent:
            raise KeyError(f"missing holding bubble {parent_id}")
        children = split_parent(parent, rules)
        input_standard_ids = {row["standard_occupation_id"] for row in parent["occupations"]}
        output_rows = [row for child in children for row in child["occupations"]]
        output_standard_ids = {row["standard_occupation_id"] for row in output_rows}
        if input_standard_ids != output_standard_ids or len(output_rows) != len(output_standard_ids):
            raise ValueError(f"{parent_id} standard-occupation coverage is not exact")
        if atomic_ids(parent["occupations"]) != atomic_ids(output_rows):
            raise ValueError(f"{parent_id} atomic-role coverage is not exact")
        for child in children:
            if child["bucket_id"] in level1_holding:
                raise ValueError(f"duplicate level-1 holding bucket {child['bucket_id']}")
            level1_holding[child["bucket_id"]] = child
        summary.append({
            "parent": parent["label"],
            "standard_name_count": len(input_standard_ids),
            "atomic_role_count": len(atomic_ids(parent["occupations"])),
            "children": [{"label": child["label"], "standard_name_count": len(child["occupations"]), "atomic_role_count": len(atomic_ids(child["occupations"]))} for child in children],
        })

    projection["level1_holding_bubbles"] = dict(sorted(level1_holding.items()))
    projection["schema_version"] = "name-only-display-projection-v6"
    projection["source_projection"] = str(SOURCE.relative_to(ROOT)).replace("\\", "/")
    projection["validation"] = {
        **projection["validation"],
        "root_holding_l2_subtree_parent_count": len(SUBTREE_RULES),
        "root_holding_l2_subtree_notice": "Multi-role entries and non-role text intentionally remain direct-access holding groups; splitting them would misrepresent their titles.",
        "root_holding_l2_display_only_notice": "These are UI-only L2 holding groups; they do not modify the frozen Reference Taxonomy.",
    }
    write_exclusive(OUTPUT, projection)
    print(json.dumps({"output": str(OUTPUT), "parents": summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
