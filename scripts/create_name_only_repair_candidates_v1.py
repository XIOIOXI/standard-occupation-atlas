"""Select name-only mapping rows that warrant semantic repair review.

Rules in this file are *screening-only*: no mapping is changed here.
"""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path

ROOT = Path("data/processed/record_role_classification_v1")
MAPPING = ROOT / "api_trials" / "deepseek_name_classification_trial_full_v1" / "full_name_only_mapping_draft_v1.json"
TAXONOMY = ROOT / "catalog_mappings" / "taxonomy_embedding_texts_v1.json"
AUDIT = ROOT / "quality_audits" / "name_only_stratified_v1" / "audit_results_rereview_v2.json"
OUT = ROOT / "targeted_name_repairs" / "name_only_targeted_repair_v1" / "risk_candidates.json"

LANGUAGE_MARKERS = ("英语", "英文", "english", "法语", "法文", "french", "日语", "日文", "japanese", "韩语", "韩文", "korean", "俄语", "俄文", "russian", "西班牙", "spanish", "阿拉伯", "德语", "德文", "german", "葡萄牙", "portuguese", "泰语", "越南语", "哈萨克")
NARROW_TECH = {
    "java": ("java",), "python": ("python",), "cpp": ("c++", "cpp",),
    "frontend-mobile": ("移动", "安卓", "android", "ios", "前端", "web", "客户端"),
    "backend": ("后端", "服务端", "server", "backend"),
    "algorithm": ("算法", "algorithm", "强化学习", "机器学习", "深度学习"),
}

def read_json(path: Path): return json.loads(path.read_text(encoding="utf-8"))
def exclusive_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as h:
        json.dump(value, h, ensure_ascii=False, indent=2); h.write("\n")

def has_any(text: str, markers) -> bool: return any(marker in text for marker in markers)

def main() -> None:
    if OUT.exists(): raise FileExistsError(f"Refusing to overwrite {OUT}")
    mapping, taxonomy, audit = read_json(MAPPING), read_json(TAXONOMY), read_json(AUDIT)
    v4 = read_json(Path(mapping["input_v4_path"]))
    aliases_by_id = {row["standard_occupation_id"]: row["original_names"] for row in v4["occupations"]}
    categories = {r["category_id"]: r for r in taxonomy["rows"]}
    audit_risk_ids = {r["standard_occupation_id"] for r in audit["items"] if r["audit_conclusion"] in {"obvious_error", "insufficient_name", "not_multi_role", "not_demonstrated_gap"}}
    candidates = []
    for row in mapping["results"]:
        title = row["standard_name"]
        aliases = aliases_by_id[row["standard_occupation_id"]]
        text = (title + " " + " ".join(aliases)).lower()
        category_id = row["target_category_id"]
        cat = categories.get(category_id)
        risks = []
        if row["standard_occupation_id"] in audit_risk_ids: risks.append("audit_rereview_flag")
        if row["status"] == "multi_role": risks.append("all_multi_role_recheck")
        if row["status"] == "taxonomy_gap": risks.append("all_taxonomy_gap_recheck")
        if cat:
            cid = category_id.lower()
            if "translation" in cid and not has_any(text, LANGUAGE_MARKERS): risks.append("language_unspecified_translation")
            for fragment, evidence in NARROW_TECH.items():
                if fragment in cid and not has_any(text, evidence): risks.append(f"narrow_tech_without_name_evidence:{fragment}")
            if ("care-worker" in cid or "elderly" in cid) and has_any(text, ("运营", "管理", "机构", "项目")): risks.append("operations_vs_frontline_care")
            if "tourism-service-guide" in cid and has_any(text, ("运营", "管理", "策划", "开发")): risks.append("tourism_operations_vs_guide")
            if "restaurant-manager" in cid and has_any(text, ("店长", "门店", "运营")) and not has_any(text, ("餐", "茶", "咖啡", "烘焙", "酒", "饭")): risks.append("store_management_vs_restaurant")
            if "internet-" in cid and has_any(text, ("售后", "设备", "工程项目")) and not has_any(text, ("软件", "互联网", "数据", "算法", "前端", "后端")): risks.append("internet_domain_without_name_evidence")
        if risks:
            candidates.append({
                "standard_occupation_id": row["standard_occupation_id"], "standard_name": title,
                "original_names": aliases, "current_status": row["status"],
                "current_category_id": category_id,
                "current_category_path": ({"level_1": cat["level_1"], "level_2": cat["level_2"], "level_3": cat["level_3"], "boundary": cat["matching_text"]} if cat else None),
                "current_reason": row["reason"], "risk_rules": sorted(set(risks)),
            })
    ids = [r["standard_occupation_id"] for r in candidates]
    if len(ids) != len(set(ids)): raise ValueError("Duplicate repair candidate")
    payload = {"schema_version": "name-only-targeted-repair-candidates-v1", "source_mapping_path": str(MAPPING), "source_audit_rereview_path": str(AUDIT), "taxonomy_path": str(TAXONOMY), "candidate_count": len(candidates), "risk_rule_counts": dict(Counter(rule for row in candidates for rule in row["risk_rules"])), "screening_note": "Risk rules only select rows for LLM review; they do not change classification.", "candidates": candidates}
    exclusive_json(OUT, payload)
    print(json.dumps({"output": str(OUT), "candidate_count": len(candidates), "risk_rule_counts": payload["risk_rule_counts"]}, ensure_ascii=False))
if __name__ == "__main__": main()
