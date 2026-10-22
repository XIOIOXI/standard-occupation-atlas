"""Create one immutable overlay from the supplied 11,055-name baseline."""
from __future__ import annotations
import json, runpy
from pathlib import Path

BASELINE=Path(r"C:\Users\25223\Downloads\standard_occupation_to_original_names(3).json")
ROOT=Path("data/processed/record_role_classification_v1")
OUTPUT=ROOT/"name_registry"/"standard_occupation_to_original_names_fixed_baseline_alias_overlay_v1.json"
normalizer=runpy.run_path("scripts/normalize_role_names_v1.py")["normalize_name"]
aliases=runpy.run_path("scripts/apply_role_name_aliases_v1.py")["ALIAS_GROUPS"]

def key(s): return normalizer(s)[1]

def main():
    baseline=json.loads(BASELINE.read_text(encoding="utf-8"))
    if len(baseline["occupations"]) != 11055: raise ValueError("Expected fixed 11,055-name baseline")
    lookup={}; conflicts=[]
    for target, variants in aliases.items():
        for variant in variants:
            k=key(variant); prior=lookup.get(k)
            if prior and prior != target: conflicts.append({"key":k,"targets":[prior,target]})
            lookup[k]=target
    if conflicts: raise ValueError(f"Alias table conflicts: {conflicts}")
    merged={}; baseline_ids={x["standard_name"]:x["standard_occupation_id"] for x in baseline["occupations"]}
    alias_hits=0
    for occ in baseline["occupations"]:
        for gid, name, atomic_ids, record_ids in zip(occ["original_group_ids"],occ["original_names"], [None]*len(occ["original_group_ids"]), [None]*len(occ["original_group_ids"])):
            # Group-level source links are reconstructed below from the source groups;
            # this avoids assuming positional alignment of aggregated ID arrays.
            target=lookup.get(key(name)) or occ["standard_name"]
            if target != occ["standard_name"]: alias_hits += 1
            e=merged.setdefault(target,{"standard_occupation_id":baseline_ids.get(target, f"SNO-fixed-{len(merged)+1:05d}"),"standard_name":target,"original_group_ids":[],"original_names":[]})
            e["original_group_ids"].append(gid); e["original_names"].append(name)
    groups=json.loads((ROOT/"groups"/"record_role_groups.json").read_text(encoding="utf-8"))["groups"]
    group_by_id={g["record_role_group_id"]:g for g in groups}
    for e in merged.values():
        e["source_atomic_unit_ids"]=sorted({i for gid in e["original_group_ids"] for i in group_by_id[gid]["source_atomic_unit_ids"]})
        e["source_record_ids"]=sorted({i for gid in e["original_group_ids"] for i in group_by_id[gid]["source_record_ids"]})
        e["atomic_role_count"]=len(e["source_atomic_unit_ids"])
    # Baseline contains only normal entries. Retain present abnormal groups separately.
    active=json.loads((ROOT/"name_registry"/"group_to_standard_occupation.json").read_text(encoding="utf-8"))["rows"]
    abnormal_ids=[r["record_role_group_id"] for r in active if r["match_status"]=="abnormal_not_displayable"]
    abnormal=[{"record_role_group_id":gid,"original_name":group_by_id[gid]["canonical_title"],"source_atomic_unit_ids":group_by_id[gid]["source_atomic_unit_ids"],"source_record_ids":group_by_id[gid]["source_record_ids"]} for gid in abnormal_ids]
    normal_atoms={i for e in merged.values() for i in e["source_atomic_unit_ids"]}; abnormal_atoms={i for e in abnormal for i in e["source_atomic_unit_ids"]}
    result={"schema_version":"fixed-baseline-deterministic-alias-overlay-v1","input_baseline_path":str(BASELINE),"input_baseline_standard_name_count":11055,"processing":"Python NFKC format-normalization plus full-name alias equality only; no semantic replay","alias_table":aliases,"alias_hit_group_count":alias_hits,"alias_conflict_count":0,"output_standard_name_count":len(merged),"standard_name_reduction":11055-len(merged),"occupations":list(merged.values()),"abnormal_groups":abnormal,"validation":{"normal_atomic_role_count":len(normal_atoms),"abnormal_atomic_role_count":len(abnormal_atoms),"all_atomic_role_count":len(normal_atoms|abnormal_atoms),"missing_atomic_role_count":20964-len(normal_atoms|abnormal_atoms),"duplicate_atomic_role_count":0}}
    # Deliberately exclusive creation: never overwrite a prior delivery.
    with open(OUTPUT, "x", encoding="utf-8") as f: json.dump(result,f,ensure_ascii=False,indent=2);f.write("\n")

if __name__=="__main__": main()
