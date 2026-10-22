"""Apply the user-governed full-name role alias table deterministically."""
from __future__ import annotations
import json
import runpy
from pathlib import Path

ROOT = Path("data/processed/record_role_classification_v1")
NAME_ROOT = ROOT / "name_registry"
normalizer = runpy.run_path("scripts/normalize_role_names_v1.py")["normalize_name"]

ALIAS_GROUPS = {
    "Java开发工程师": ["Java开发工程师","JAVA开发工程师","java开发工程师","Java开发","JAVA开发","Java软件开发工程师","JAVA软件开发工程师","软件开发工程师(Java)","软件开发工程师(JAVA)","软件开发工程师(Java方向)","软件开发工程师(JAVA方向)","软件开发(JAVA)"],
    "Web前端开发工程师": ["前端开发","前端开发工程师","Web前端开发","Web前端开发工程师","web前端开发工程师","Web前端工程师","前端开发工程师(Web)"],
    "人力资源专员": ["HR专员","人力资源专员","人力资源部专员"],
    "人力资源培训生": ["HRTrainee","HR Trainee","HRTrainee(HR培训生)","HR培训生","人力培训生","人力资源培训生"],
    "现场应用工程师(FAE)": ["FAE工程师","FAE(现场应用工程师)","现场应用工程师(FAE)","现场应用工程师"],
    "UI设计师": ["UI设计","UI设计师","uI设计师","UI界面设计师"],
    "用户体验设计师": ["UX设计","UX设计师","用户体验设计","用户体验设计师"],
    "管理培训生": ["管培生","管理培训生"],
    "软件开发工程师": ["软件开发","软件开发工程师"],
    "新媒体运营": ["新媒体运营","新媒体运营专员"],
}

def key(name: str) -> str:
    return normalizer(name)[1]

def main() -> None:
    formatted = json.loads((NAME_ROOT / "format_normalized_names.json").read_text(encoding="utf-8"))
    groups = json.loads((ROOT / "groups" / "record_role_groups.json").read_text(encoding="utf-8"))["groups"]
    by_group = {g["record_role_group_id"]: g for g in groups}
    lookup: dict[str, str] = {}
    conflicts: list[dict] = []
    used_table: dict[str, list[str]] = {}
    for target, variants in ALIAS_GROUPS.items():
        target_display = normalizer(target)[0]
        used_table[target_display] = variants
        for variant in variants:
            normalized_key = key(variant)
            prior = lookup.get(normalized_key)
            if prior and prior != target_display:
                conflicts.append({"format_match_key": normalized_key, "targets": [prior, target_display]})
            else:
                lookup[normalized_key] = target_display
    if conflicts:
        raise ValueError(f"Alias-table collision: {conflicts}")
    rows = []
    reverse: dict[str, dict] = {}
    for row in formatted["rows"]:
        target = lookup.get(row["format_match_key"])
        group = by_group[row["record_role_group_id"]]
        item = {
            "record_role_group_id": row["record_role_group_id"], "original_name": row["original_name"],
            "format_normalized_name": row["format_normalized_name"], "format_match_key": row["format_match_key"],
            "deterministic_standard_name": target, "match_status": "matched_full_name_alias" if target else "unmatched_preserved",
        }
        rows.append(item)
        # Non-matches are explicitly preserved under their format-normalized
        # full name; this is not a semantic alias decision.
        effective_standard = target or row["format_normalized_name"]
        entry = reverse.setdefault(effective_standard, {"standard_name": effective_standard, "original_group_ids": [], "original_names": [], "source_atomic_unit_ids": [], "source_record_ids": []})
        entry["original_group_ids"].append(group["record_role_group_id"])
        entry["original_names"].append(group["canonical_title"])
        entry["source_atomic_unit_ids"].extend(group["source_atomic_unit_ids"])
        entry["source_record_ids"].extend(group["source_record_ids"])
    for entry in reverse.values():
        entry["source_atomic_unit_ids"] = sorted(set(entry["source_atomic_unit_ids"]))
        entry["source_record_ids"] = sorted(set(entry["source_record_ids"]))
        entry["atomic_role_count"] = len(entry["source_atomic_unit_ids"])
    output = {"schema_version":"deterministic-full-name-alias-v1","matching":"format-normalized full-name equality only; no substring replacement","input_group_count":len(rows),"matched_group_count":sum(x["deterministic_standard_name"] is not None for x in rows),"unmatched_group_count":sum(x["deterministic_standard_name"] is None for x in rows),"deterministic_standard_name_count":len(reverse),"alias_conflict_count":len(conflicts),"alias_groups_used":used_table,"rows":rows,"reverse_standard_names":list(reverse.values())}
    (NAME_ROOT / "deterministic_alias_mappings_v1.json").write_text(json.dumps(output, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")

if __name__ == "__main__": main()
