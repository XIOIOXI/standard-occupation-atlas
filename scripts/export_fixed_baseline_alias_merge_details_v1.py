"""Export auditable detail for every eliminated standard in the fixed-baseline overlay."""
from __future__ import annotations
import json, runpy
from pathlib import Path

ROOT=Path("data/processed/record_role_classification_v1")
BASE=Path(r"C:\Users\25223\Downloads\standard_occupation_to_original_names(3).json")
OVERLAY=ROOT/"name_registry"/"standard_occupation_to_original_names_fixed_baseline_alias_overlay_v1.json"
OUT=ROOT/"name_registry"/"fixed_baseline_alias_merge_details_v1.json"
normalizer=runpy.run_path("scripts/normalize_role_names_v1.py")["normalize_name"]

def main():
    base=json.loads(BASE.read_text(encoding="utf-8")); overlay=json.loads(OVERLAY.read_text(encoding="utf-8"))
    target_by_name={x["standard_name"]:x["standard_occupation_id"] for x in overlay["occupations"]}
    rules={}
    for target, variants in overlay["alias_table"].items():
        for v in variants: rules[normalizer(v)[1]]={"target_standard_name":target,"rule_variant":v}
    base_names={x["standard_name"] for x in base["occupations"]}
    eliminated=[]
    for old in base["occupations"]:
        if old["standard_name"] in target_by_name: continue
        hits=[]
        for gid,name in zip(old["original_group_ids"],old["original_names"]):
            rule=rules.get(normalizer(name)[1])
            if rule: hits.append({"record_role_group_id":gid,"original_name":name,"format_match_key":normalizer(name)[1],**rule})
        targets=sorted({x["target_standard_name"] for x in hits})
        item={"prior_standard_occupation_id":old["standard_occupation_id"],"prior_standard_name":old["standard_name"],"target_standard_names":targets,"target_standard_occupation_ids":[target_by_name[x] for x in targets],"matched_groups":hits,"reduction_reason":"all baseline members were reassigned through exact format-normalized alias rules"}
        eliminated.append(item)
    details=[]; canonical_renames=[]; seen_new_targets=set()
    for item in eliminated:
        target=item["target_standard_names"][0] if len(item["target_standard_names"])==1 else None
        if target and target not in base_names and target not in seen_new_targets:
            canonical_renames.append(item); seen_new_targets.add(target)
        else:
            details.append(item)
    payload={"schema_version":"fixed-baseline-alias-merge-details-v1","baseline_standard_name_count":11055,"overlay_standard_name_count":11028,"standard_name_reduction":27,"detail_count":len(details),"details":details,"non_reducing_canonical_rename_count":len(canonical_renames),"non_reducing_canonical_renames":canonical_renames}
    if len(details)!=27: raise ValueError(f"Expected 27 eliminated standards, got {len(details)}")
    with open(OUT,"x",encoding="utf-8") as f: json.dump(payload,f,ensure_ascii=False,indent=2);f.write("\n")
if __name__=="__main__":main()
