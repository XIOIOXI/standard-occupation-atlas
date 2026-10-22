"""Build display-only holding groups and direct atomic-role evidence for SNO.

This does not alter the frozen reference taxonomy or any name-level mapping.
It gives genuinely unplaced entries a clearly labelled, root-level presentation
bucket and indexes recruitment evidence by the stable atomic-role ID.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data/processed/record_role_classification_v1/targeted_name_repairs/name_only_targeted_repair_v1"
PROJECTION_IN = DATA_DIR / "display_projection_v2.json"
MEMBERS_IN = ROOT / "data/processed/job_groups_v2/job_group_members.jsonl"
PROJECTION_OUT = DATA_DIR / "display_projection_v3.json"
EVIDENCE_OUT = DATA_DIR / "sno_atomic_evidence_index_v1.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_exclusive(path: Path, payload) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def classify_holding_bucket(row: dict) -> tuple[str, str, str]:
    """Return a UI-only root bucket, applying explicit priority rules.

    These labels are deliberately not taxonomy labels.  They preserve the
    mapping status and give users a useful, reversible way to reach sources.
    """
    name = row["label"].strip()
    folded = name.casefold()
    status = row["status"]

    if status == "multi_role":
        return ("holding:multi-role", "多职业待拆分", "模型已识别为多个独立职业，展示层暂不拆分原子岗位。")
    if status == "taxonomy_gap":
        return ("holding:taxonomy-gap", "目录缺口", "职业名称可读，但冻结目录暂无适合承接类别。")

    if re.search(r"管培|管理培训|培训生|储备(?:生|干部|人才|库)?|\b(?:mt|gmt|trainee)\b", folded, re.I):
        return ("holding:management-trainee", "管理培训与储备岗位", "名称明确表达培养或储备计划，但未确认具体职业方向。")

    if re.match(r"^(本次|此次|具体招聘|分两个批次|招聘涉及|计划招录|按照岗位|以上岗位|招聘岗位)", name) or name in {"博士研究生", "实习生", "此次招聘涉及"}:
        return ("holding:non-role-text", "招聘文本片段与身份说明", "名称不是可独立展示的职业，保留来源供后续清洗或拆分。")

    if re.search(r"研发|开发|工程|技术|设计|软件|硬件|算法|系统|实验|研究|科学|制造|生产|设备|工艺", name):
        return ("holding:general-technology", "通用研发与技术岗位", "名称可判断为技术或研发工作，但不足以安全进入正式职业方向。")

    if re.search(r"运营|产品|项目|市场|销售|客户|人力|行政|财务|法务|审计|风控|采购|供应|贸易|咨询|战略|管理|业务|服务", name):
        return ("holding:general-business", "综合职能与业务岗位", "名称表达业务或职能工作，但不足以安全进入正式职业方向。")

    return ("holding:unresolved", "其他待明确职业", "名称信息不足，尚不能确认正式职业方向。")


def build_holding_bubbles(unplaced: list[dict]) -> dict[str, dict]:
    buckets: dict[str, dict] = {}
    for row in unplaced:
        bucket_id, label, note = classify_holding_bucket(row)
        bucket = buckets.setdefault(bucket_id, {
            "bucket_id": bucket_id,
            "label": label,
            "display_only": True,
            "parent_level": "root",
            "holding_note": note,
            "occupations": [],
        })
        bucket["occupations"].append(row)
    for bucket in buckets.values():
        bucket["occupations"].sort(key=lambda item: (item["label"], item["standard_occupation_id"]))
        bucket["status_counts"] = dict(sorted(Counter(item["status"] for item in bucket["occupations"]).items()))
    return dict(sorted(buckets.items()))


def build_atomic_evidence() -> dict:
    atomic_units = {}
    for line in MEMBERS_IN.read_text(encoding="utf-8").splitlines():
        member = json.loads(line)
        atomic_id = member["source_atomic_unit_id"]
        if atomic_id in atomic_units:
            raise ValueError(f"duplicate atomic source in job-group members: {atomic_id}")
        atomic_units[atomic_id] = {
            "source_record_id": member["source_record_id"],
            "raw_job_title": member["raw_job_title"],
            "job_title_unit": member["job_title_unit"],
            "company_name": member["company_name"],
            "location": member["location"],
            "education_requirement": member.get("education_requirement"),
            "job_group_id": member["job_group_id"],
        }
    return {
        "schema_version": "sno-atomic-evidence-index-v1",
        "source": "data/processed/job_groups_v2/job_group_members.jsonl",
        "link_method": "source_atomic_unit_id_exact",
        "atomic_units": atomic_units,
    }


def main() -> None:
    if PROJECTION_OUT.exists() or EVIDENCE_OUT.exists():
        raise FileExistsError("Refusing to overwrite v3 display projection or atomic evidence index")
    projection = read_json(PROJECTION_IN)
    holding_bubbles = build_holding_bubbles(projection["unplaced"])
    evidence = build_atomic_evidence()

    all_projection_atomic = {
        atomic_id
        for category in projection["category_bubbles"].values()
        for row in category["occupations"]
        for atomic_id in row["source_atomic_unit_ids"]
    }
    all_projection_atomic |= {
        atomic_id
        for bucket in projection["other_bubbles"].values()
        for row in bucket["occupations"]
        for atomic_id in row["source_atomic_unit_ids"]
    }
    all_projection_atomic |= {
        atomic_id
        for row in projection["unplaced"]
        for atomic_id in row["source_atomic_unit_ids"]
    }
    indexed_atomic = set(evidence["atomic_units"])
    missing = all_projection_atomic - indexed_atomic
    if missing:
        raise ValueError(f"direct evidence missing {len(missing)} projection atomic IDs")

    validation = dict(projection["validation"])
    validation.update({
        "direct_atomic_evidence_count": len(indexed_atomic),
        "direct_atomic_evidence_missing_count": len(missing),
        "display_holding_group_count": len(holding_bubbles),
        "display_holding_entry_count": sum(len(bucket["occupations"]) for bucket in holding_bubbles.values()),
        "display_only_notice": "holding_bubbles are UI-only grouping nodes and are not Reference Taxonomy categories.",
    })
    result = dict(projection)
    result.update({
        "schema_version": "name-only-display-projection-v3",
        "source_projection": str(PROJECTION_IN.relative_to(ROOT)).replace("\\", "/"),
        "holding_bubbles": holding_bubbles,
        "validation": validation,
    })
    write_exclusive(EVIDENCE_OUT, evidence)
    write_exclusive(PROJECTION_OUT, result)
    print(json.dumps({
        "display_projection": str(PROJECTION_OUT),
        "atomic_evidence_index": str(EVIDENCE_OUT),
        "holding_bubbles": {key: len(value["occupations"]) for key, value in holding_bubbles.items()},
        "validation": validation,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
