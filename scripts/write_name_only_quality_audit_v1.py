"""Persist the completed human name-only review of the fixed 300-row sample.

The verdict sequence is explicit for every sampled item.  This module does not
infer correctness, use model confidence, or create a default pass outcome.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("data/processed/record_role_classification_v1")
AUDIT_DIR = ROOT / "quality_audits" / "name_only_stratified_v1"
SAMPLE_PATH = AUDIT_DIR / "sample_manifest.json"
OUTPUT_PATH = AUDIT_DIR / "audit_results.json"

# Index-aligned, manually determined outcomes for all 300 items.  Codes:
# R reasonable mapped; I mapped but name insufficient for its L3; E obvious
# mapped error; A review appropriate; T true multi-role; F not multi-role;
# G genuine taxonomy gap; N not a demonstrated gap (keep review).
CODES = """
A R A R R R I R A R R R I A I R R R R G I A I R T R T R I R G R R E R T R I R R R R R T E R R A I I
E I A R I F G R R R R R R I T R R R R A R I T R T R G R E R E R A R A I R F R R G R R R R R I A I R
I T R A I R I R I A A A A E A R R R R R I T I T R R R T R F T A E A R R I R R R R T E R R F E A R R
G I A A R R R A I E R I I R R A I A R I A E R A A I I G R R G E R A R R R I R R I R G R R R E I A R
R I R R A R R N R E G A I A R G I R I I A R G T R A R R F I R G R R R I F I T G I R R R A R R R R R
A A A A G G R A E T A A R R I F T R R R A G A A R T T I R R T R I R G T A A I A R R I T A R G I T I
""".split()

ERROR_DETAILS = {
    33: ("名称是对外交流管理，未明确政府事务或政策职责；当前三级过窄。", "市场/公关/广告"),
    44: ("AI 软件开发工程师没有 Python 或数据方向证据，不能落入 Python 数据开发。", "互联网/AI"),
    50: ("船舶 ETO 船员是船舶电子电气岗位，不等同于工业电子维修。", "电子/电气/通信"),
    78: ("养老机构运营是机构运营，不等同于一线养老照护。", "医疗健康"),
    80: ("景区运营并不等同于导游服务，当前三级把运营职责改写成导游。", "酒店/旅游"),
    113: ("终端开发未说明移动端或前端，不能确认移动前端开发。", "互联网/AI"),
    132: ("制剂研发强调研发，当前药品制造工艺类别改变了核心职责。", "医疗健康"),
    142: ("信息科技教师是教师职业，不能归为 IT 基础设施培训。", "教育培训/edu-teacher/teacher-k12"),
    146: ("业务平台工程师未给出后端证据，不能默认后端平台开发。", "互联网/AI"),
    159: ("智能驾驶软件开发未表明算法职责，不能直接归为自动驾驶算法。", "互联网/AI"),
    171: ("CAD/CAM 软件开发未声明 C++ 或图形技术栈，当前三级过度推断。", "互联网/AI"),
    181: ("售后工程师未表明互联网运维支持，当前一级与名称明确职责不符。", None),
    196: ("文娱活动师未体现儿童服务，不能归为儿童活动引导。", "影视/传媒"),
    209: ("项目管理工程师没有互联网领域证据，不能归为互联网项目交付。", None),
    258: ("储备店长未说明餐饮场景，不能归为餐饮门店运营。", "生活服务/零售"),
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def exclusive_json(path: Path, payload) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def conclusion(item: dict, code: str, index: int) -> dict:
    name = item["standard_name"]
    target = item["current_level_3"] or item["current_level_2"] or item["current_level_1"]
    status = item["current_status"]
    if code == "R":
        return {"audit_conclusion": "reasonable", "suggested_category_id": item["current_category_id"], "audit_reason": f"名称“{name}”明确表达该职业核心职责；当前目录“{target}”处于可接受的职业边界内。"}
    if code == "I":
        return {"audit_conclusion": "insufficient_name", "suggested_category_id": None, "audit_reason": f"名称“{name}”未给出支撑当前三级“{target}”所需的技术、业务或服务对象方向；应保留可确认上级并标记 review。"}
    if code == "E":
        reason, suggestion = ERROR_DETAILS[index]
        return {"audit_conclusion": "obvious_error", "suggested_category_id": suggestion, "audit_reason": reason}
    if code == "A":
        return {"audit_conclusion": "review_appropriate", "suggested_category_id": None, "audit_reason": f"名称“{name}”不足以可靠确认三级职业方向；保留 review 合理。"}
    if code == "T":
        return {"audit_conclusion": "true_multi_role", "suggested_category_id": None, "audit_reason": f"名称“{name}”明确并列了多个可独立成立的职业或职责，multi_role 合理。"}
    if code == "F":
        return {"audit_conclusion": "not_multi_role", "suggested_category_id": None, "audit_reason": f"名称“{name}”是单一岗位的方向、培养范围或技能/专业要求组合，未明确列出多个独立职业；应改为 review。"}
    if code == "G":
        return {"audit_conclusion": "gap_valid", "suggested_category_id": None, "audit_reason": f"名称“{name}”职业主体清楚，但冻结目录没有足以承接的相邻三级类别；taxonomy_gap 合理。"}
    if code == "N":
        return {"audit_conclusion": "not_demonstrated_gap", "suggested_category_id": None, "audit_reason": f"名称“{name}”本身方向不足，不能据此证明目录缺口；应保留 review。"}
    raise ValueError(f"Unknown explicit audit code {code!r}")


def expected_codes(status: str) -> set[str]:
    return {
        "mapped": {"R", "I", "E"},
        "review": {"A"},
        "multi_role": {"T", "F"},
        "taxonomy_gap": {"G", "N"},
    }[status]


def main() -> None:
    if OUTPUT_PATH.exists():
        raise FileExistsError(f"Refusing to overwrite audit result: {OUTPUT_PATH}")
    sample = read_json(SAMPLE_PATH)
    items = sample["items"]
    if len(items) != 300 or len(CODES) != len(items):
        raise ValueError(f"Expected 300 explicit codes and items, got {len(CODES)} codes / {len(items)} items")
    results = []
    for index, (item, code) in enumerate(zip(items, CODES, strict=True)):
        if code not in expected_codes(item["current_status"]):
            raise ValueError(f"Audit code {code} invalid for {item['current_status']} at index {index}")
        result = dict(item)
        result["sample_index"] = index
        result["audit_scope"] = "name + original aliases + selected taxonomy boundary only"
        result.update(conclusion(item, code, index))
        results.append(result)

    by_status = defaultdict(Counter)
    for row in results:
        by_status[row["current_status"]][row["audit_conclusion"]] += 1
    mapped = by_status["mapped"]
    payload = {
        "schema_version": "name-only-mapping-quality-audit-v1",
        "sample_manifest_path": str(SAMPLE_PATH),
        "sampling_seed": sample["sampling_seed"],
        "audit_method": "Each sampled item was independently assessed from name, aliases, selected category and category boundary. No company, industry, recruitment prose, skills or model confidence was used.",
        "items": results,
        "status_result_counts": {status: dict(counts) for status, counts in by_status.items()},
        "mapped_quality": {
            "sample_size": sum(mapped.values()),
            "reasonable_count": mapped["reasonable"],
            "obvious_error_count": mapped["obvious_error"],
            "insufficient_name_count": mapped["insufficient_name"],
            "reasonable_rate": mapped["reasonable"] / sum(mapped.values()),
            "obvious_error_rate": mapped["obvious_error"] / sum(mapped.values()),
            "insufficient_name_rate": mapped["insufficient_name"] / sum(mapped.values()),
        },
        "interpretation": "This is a stratified quality sample, not an all-status pooled estimate of full-draft accuracy.",
    }
    exclusive_json(OUTPUT_PATH, payload)
    print(json.dumps({"output": str(OUTPUT_PATH), "status_result_counts": payload["status_result_counts"], "mapped_quality": payload["mapped_quality"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
