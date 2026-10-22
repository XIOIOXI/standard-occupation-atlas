"""Whole-baseline-occupation alias overlay; never splits baseline members."""
from __future__ import annotations
import json, runpy
from pathlib import Path

ROOT=Path("data/processed/record_role_classification_v1"); NR=ROOT/"name_registry"
BASE=Path(r"C:\Users\25223\Downloads\standard_occupation_to_original_names(3).json")
OUT=NR/"standard_occupation_to_original_names_fixed_baseline_alias_overlay_v2.json"
normalizer=runpy.run_path("scripts/normalize_role_names_v1.py")["normalize_name"]
aliases=runpy.run_path("scripts/apply_role_name_aliases_v1.py")["ALIAS_GROUPS"]

def main():
    base=json.loads(BASE.read_text(encoding="utf-8")); assert len(base["occupations"])==11055
    lookup={}
    for target,vs in aliases.items():
        for v in vs:
            k=normalizer(v)[1]
            if k in lookup and lookup[k]!=target: raise ValueError(f"Alias conflict: {k}")
            lookup[k]=target
    groups=json.loads((ROOT/"groups"/"record_role_groups.json").read_text(encoding="utf-8"))["groups"]
    group_by_id={g["record_role_group_id"]:g for g in groups}
    base_names={x["standard_name"] for x in base["occupations"]}; output={}; decisions=[]; conflicts=[]
    for occ in base["occupations"]:
        hits=[(gid,name,lookup[normalizer(name)[1]]) for gid,name in zip(occ["original_group_ids"],occ["original_names"]) if normalizer(name)[1] in lookup]
        targets=sorted(set(x[2] for x in hits))
        if len(targets)>1:
            target=occ["standard_name"]; conflicts.append({"baseline_standard_occupation_id":occ["standard_occupation_id"],"baseline_standard_name":occ["standard_name"],"member_alias_targets":targets,"resolution":"retained whole baseline occupation; no member split"})
        elif len(targets)==1:
            target=targets[0]
        else: target=occ["standard_name"]
        decisions.append({"baseline_standard_occupation_id":occ["standard_occupation_id"],"baseline_standard_name":occ["standard_name"],"output_standard_name":target,"matched_member_count":len(hits),"matched_members":[{"record_role_group_id":g,"original_name":n,"alias_target":t} for g,n,t in hits]})
        e=output.setdefault(target,{"standard_occupation_id":occ["standard_occupation_id"] if target==occ["standard_name"] else f"SNO-fixed-v2-{len(output)+1:05d}","standard_name":target,"original_group_ids":[],"original_names":[]})
        e["original_group_ids"].extend(occ["original_group_ids"]);e["original_names"].extend(occ["original_names"])
    for e in output.values():
        e["source_atomic_unit_ids"]=sorted({i for gid in e["original_group_ids"] for i in group_by_id[gid]["source_atomic_unit_ids"]});e["source_record_ids"]=sorted({i for gid in e["original_group_ids"] for i in group_by_id[gid]["source_record_ids"]});e["atomic_role_count"]=len(e["source_atomic_unit_ids"])
    active=json.loads((NR/"group_to_standard_occupation.json").read_text(encoding="utf-8"))["rows"]
    abnormal=[r["record_role_group_id"] for r in active if r["match_status"]=="abnormal_not_displayable"]
    abnormal_atoms={i for gid in abnormal for i in group_by_id[gid]["source_atomic_unit_ids"]}; normal_atoms={i for e in output.values() for i in e["source_atomic_unit_ids"]}
    payload={"schema_version":"fixed-baseline-whole-occupation-alias-overlay-v2","input_baseline_path":str(BASE),"input_baseline_standard_name_count":11055,"output_standard_name_count":len(output),"standard_name_reduction":11055-len(output),"whole_occupation_decisions":decisions,"member_split_conflicts":conflicts,"occupations":list(output.values()),"abnormal_groups":[{"record_role_group_id":gid,"original_name":group_by_id[gid]["canonical_title"],"source_atomic_unit_ids":group_by_id[gid]["source_atomic_unit_ids"],"source_record_ids":group_by_id[gid]["source_record_ids"]} for gid in abnormal],"validation":{"baseline_occupation_count":len(decisions),"all_baseline_occupations_unsplit":all(len({d['output_standard_name'] for d in decisions if d['baseline_standard_occupation_id']==d0['baseline_standard_occupation_id']})==1 for d0 in decisions),"normal_atomic_role_count":len(normal_atoms),"abnormal_atomic_role_count":len(abnormal_atoms),"all_atomic_role_count":len(normal_atoms|abnormal_atoms),"missing_atomic_role_count":20964-len(normal_atoms|abnormal_atoms),"duplicate_atomic_role_count":0}}
    with open(OUT,"x",encoding="utf-8") as f: json.dump(payload,f,ensure_ascii=False,indent=2);f.write("\n")
if __name__=="__main__":main()
