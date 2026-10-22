"""Save a second-pass review of the fixed 300-item name-only audit.

The original audit is retained untouched.  This pass reconsiders every sample
under the clarified rule that reasonable core-duty inference is allowed, while
recording the specific conclusions changed in the second pass.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("data/processed/record_role_classification_v1")
AUDIT_DIR = ROOT / "quality_audits" / "name_only_stratified_v1"
INPUT_PATH = AUDIT_DIR / "audit_results.json"
OUTPUT_PATH = AUDIT_DIR / "audit_results_rereview_v2.json"

REVISIONS = {
    "AQ-27f40412965497b804f7": {
        "audit_conclusion": "insufficient_name",
        "suggested_category_id": None,
        "audit_reason": "名称只表明翻译职责，未表明英语；不能以泛称翻译确认英语翻译/口译三级，应保留可确认上级并 review。",
        "rereview_note": "纠正首次审查对未注明语言翻译的过度宽容。",
    },
    "AQ-a3d3f3e583277f2c1eba": {
        "audit_conclusion": "reasonable",
        "suggested_category_id": "生活服务/零售/service-therapy/wellness-health",
        "audit_reason": "健康顾问的核心职责与健康管理、保健服务相符；不因名称未列具体服务对象而否定这一合理归属。",
        "rereview_note": "按澄清后的合理职业推断标准修正。",
    },
    "AQ-04f6aa9d0475984365fc": {
        "audit_conclusion": "reasonable",
        "suggested_category_id": "互联网/AI/internet-sales-support/presales-customer",
        "audit_reason": "FAE 即现场应用/客户技术支持，当前客户技术支持类三级与核心职责相符；不因未写产品领域而要求退回上级。",
        "rereview_note": "按 FAE 示例复核。",
    },
    "AQ-43e37ae07b5ade05eabb": {
        "audit_conclusion": "insufficient_name",
        "suggested_category_id": None,
        "audit_reason": "总裁助理明确行政协同，但名称未必以文档与档案为核心；当前三级可能缩窄职责，应保留上级并 review。",
        "rereview_note": "重新检查行政助理与文档文员的边界。",
    },
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def exclusive_json(path: Path, payload) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> None:
    if OUTPUT_PATH.exists():
        raise FileExistsError(f"Refusing to overwrite: {OUTPUT_PATH}")
    source = read_json(INPUT_PATH)
    rows = []
    seen_ids = set()
    changed_ids = set()
    for row in source["items"]:
        item = dict(row)
        occupation_id = item["standard_occupation_id"]
        seen_ids.add(occupation_id)
        revision = REVISIONS.get(item["audit_item_id"])
        item["first_pass_audit_conclusion"] = item["audit_conclusion"]
        if revision:
            item.update(revision)
            item["rereview_changed"] = True
            changed_ids.add(occupation_id)
        else:
            item["rereview_changed"] = False
            item["rereview_note"] = "Second pass confirmed the name-only conclusion; no automatic default was applied."
        rows.append(item)
    unknown = set(REVISIONS) - {row["audit_item_id"] for row in rows}
    if unknown or len(rows) != 300 or len(seen_ids) != 300:
        raise ValueError(f"Rereview completeness failure: rows={len(rows)}, unknown_revision_ids={sorted(unknown)}")
    by_status = defaultdict(Counter)
    for row in rows:
        by_status[row["current_status"]][row["audit_conclusion"]] += 1
    mapped = by_status["mapped"]
    payload = {
        "schema_version": "name-only-mapping-quality-audit-rereview-v2",
        "input_audit_path": str(INPUT_PATH),
        "rereview_scope": "All 300 sampled names, their aliases, current placement and taxonomy boundary were reconsidered; no company, industry, description, skill or model confidence was used.",
        "sample_count": len(rows),
        "changed_conclusion_count": len(changed_ids),
        "items": rows,
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
        "interpretation": "Stratified sample only; it is not a full-draft accuracy estimate.",
    }
    exclusive_json(OUTPUT_PATH, payload)
    print(json.dumps({"output": str(OUTPUT_PATH), "changed_conclusion_count": len(changed_ids), "status_result_counts": payload["status_result_counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
