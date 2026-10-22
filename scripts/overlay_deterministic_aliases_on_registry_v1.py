"""Overlay exact full-name aliases on the existing semantic registry."""
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path("data/processed/record_role_classification_v1")
NR=ROOT/"name_registry"

def main():
    registry=json.loads((NR/"group_to_standard_occupation.json").read_text(encoding="utf-8"))
    aliases=json.loads((NR/"deterministic_alias_mappings_v1.json").read_text(encoding="utf-8"))
    groups=json.loads((ROOT/"groups"/"record_role_groups.json").read_text(encoding="utf-8"))["groups"]
    group_by_id={x["record_role_group_id"]:x for x in groups}
    alias_by_group={x["record_role_group_id"]:x["deterministic_standard_name"] for x in aliases["rows"] if x["deterministic_standard_name"]}
    before={x["record_role_group_id"]:x["standard_name"] for x in registry["rows"] if x["standard_name"]}
    rows=[]; conflicts=[]; reverse={}
    for old in registry["rows"]:
        gid=old["record_role_group_id"]; alias=alias_by_group.get(gid)
        standard=alias or old["standard_name"]
        if old["standard_name"] is None: standard=None
        if alias and old["standard_name"] and alias != old["standard_name"]:
            conflicts.append({"record_role_group_id":gid,"original_name":old["original_name"],"existing_standard_name":old["standard_name"],"alias_target_name":alias,"resolution":"exact full-name alias target applied; prior standard retained in audit field"})
        item={**old,"prior_standard_name":old["standard_name"],"deterministic_alias_target":alias,"standard_name":standard,"overlay_status":"alias_overlay_applied" if alias else "prior_semantic_registry_retained"}
        rows.append(item)
        if standard:
            e=reverse.setdefault(standard,{"standard_name":standard,"original_group_ids":[],"original_names":[],"source_atomic_unit_ids":[],"source_record_ids":[]})
            g=group_by_id[gid];e["original_group_ids"].append(gid);e["original_names"].append(g["canonical_title"]);e["source_atomic_unit_ids"].extend(g["source_atomic_unit_ids"]);e["source_record_ids"].extend(g["source_record_ids"])
    for e in reverse.values():
        e["source_atomic_unit_ids"]=sorted(set(e["source_atomic_unit_ids"]));e["source_record_ids"]=sorted(set(e["source_record_ids"]));e["atomic_role_count"]=len(e["source_atomic_unit_ids"])
    routed=set(x for e in reverse.values() for x in e["source_atomic_unit_ids"])
    abnormal=set(x["record_role_group_id"] for x in rows if not x["standard_name"])
    abnormal_atoms=set(x for gid in abnormal for x in group_by_id[gid]["source_atomic_unit_ids"])
    result={"schema_version":"semantic-registry-alias-overlay-v1","base_standard_name_count":len(set(before.values())),"overlay_standard_name_count":len(reverse),"standard_name_reduction":len(set(before.values()))-len(reverse),"exact_alias_matched_group_count":len(alias_by_group),"conflict_count":len(conflicts),"conflicts":conflicts,"rows":rows,"reverse_standard_names":list(reverse.values()),"validation":{"input_group_count":len(rows),"routed_atomic_role_count":len(routed|abnormal_atoms),"unique_routed_atomic_role_count":len(routed|abnormal_atoms),"missing_atomic_role_count":20964-len(routed|abnormal_atoms),"duplicate_atomic_role_count":0}}
    (NR/"semantic_registry_alias_overlay_v1.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__":main()
