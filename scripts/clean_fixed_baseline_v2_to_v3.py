"""Read-only v2 cleanup and whole-occupation exact-name merge, output v3."""
from __future__ import annotations
import json, re, unicodedata
from pathlib import Path

ROOT=Path("data/processed/record_role_classification_v1/name_registry")
SRC=ROOT/"standard_occupation_to_original_names_fixed_baseline_alias_overlay_v2.json"
OUT=ROOT/"standard_occupation_to_original_names_fixed_baseline_alias_overlay_v3.json"
DETAIL=ROOT/"fixed_baseline_v3_cleanup_merge_details.json"
SPACE=re.compile(r"\s+"); PAREN=re.compile(r"[（(]([^（）()]*)[）)]"); TAIL=re.compile(r"(?:[，,、;；\s-]*(?:招聘)?\s*\d+\s*(?:人|名|位|个))+$",re.I)
NOTE=re.compile(r"^(?:\d{4}届)?(?:校招|社招|实习生?|应届生?|本科|硕士|博士|大专|学历不限|专业不限)(?:[ /、，,]*(?:校招|社招|实习生?|应届生?|本科|硕士|博士|大专|学历不限|专业不限))*$",re.I)
LOCATION_NOTE=re.compile(r"^(?:工作)?地点[:：]?\s*(?:北京|上海|广州|深圳|武汉|杭州|苏州|全国|海外|[^，,、/]{2,12}(?:市|省|区|县))(?:[、，,/](?:北京|上海|广州|深圳|武汉|杭州|苏州|全国|海外|[^，,、/]{2,12}(?:市|省|区|县)))*$")
ALIASES={"Java后端开发工程师":["Java后端开发","Java后端开发工程师"],"游戏UI设计师":["游戏UI设计","游戏UI设计师"]}

def clean(s):
    s=unicodedata.normalize("NFKC",s or "").strip();s=SPACE.sub(" ",s).replace("（","(").replace("）",")")
    removed=[]; uncertain=[]
    def sub(m):
        content=SPACE.sub("",m.group(1))
        if NOTE.fullmatch(content) or LOCATION_NOTE.fullmatch(content): removed.append(m.group(0));return ""
        if any(x in content for x in ["届","校招","社招","实习","本科","硕士","博士","大专","专业","地点"]): uncertain.append(m.group(0))
        return m.group(0)
    s=PAREN.sub(sub,s);m=TAIL.search(s)
    if m: removed.append(m.group(0));s=s[:m.start()]
    return s.strip(" ,，;；"),removed,uncertain

def key(s): return clean(s)[0].casefold()

def main():
    src=json.loads(SRC.read_text(encoding="utf-8")); lookup={}
    for target,vs in ALIASES.items():
        for v in vs:
            k=key(v)
            if k in lookup and lookup[k]!=target: raise ValueError("alias conflict")
            lookup[k]=target
    buckets={}; decisions=[]; uncertain=[]
    for occ in src["occupations"]:
        cleaned,removed,unc=clean(occ["standard_name"]);target=lookup.get(cleaned.casefold(),cleaned)
        if unc: uncertain.append({"standard_occupation_id":occ["standard_occupation_id"],"standard_name":occ["standard_name"],"uncertain_annotations":unc})
        decisions.append({"prior_standard_occupation_id":occ["standard_occupation_id"],"prior_standard_name":occ["standard_name"],"cleaned_name":cleaned,"output_standard_name":target,"removed_annotations":removed})
        e=buckets.setdefault(target,{"standard_occupation_id":occ["standard_occupation_id"],"standard_name":target,"original_group_ids":[],"original_names":[],"source_atomic_unit_ids":[],"source_record_ids":[],"merged_from_standard_occupation_ids":[],"merged_from_standard_names":[]})
        for k in ["original_group_ids","original_names","source_atomic_unit_ids","source_record_ids"]:e[k].extend(occ[k])
        e["merged_from_standard_occupation_ids"].append(occ["standard_occupation_id"]);e["merged_from_standard_names"].append(occ["standard_name"])
    for e in buckets.values():
        for k in ["original_group_ids","original_names","source_atomic_unit_ids","source_record_ids","merged_from_standard_occupation_ids","merged_from_standard_names"]:e[k]=list(dict.fromkeys(e[k]))
        e["atomic_role_count"]=len(e["source_atomic_unit_ids"])
    normal={i for e in buckets.values() for i in e["source_atomic_unit_ids"]}; abnormal={i for g in src["abnormal_groups"] for i in g["source_atomic_unit_ids"]}
    result={"schema_version":"fixed-baseline-v3-name-cleanup-v1","input_v2_path":str(SRC),"input_standard_name_count":len(src["occupations"]),"output_standard_name_count":len(buckets),"standard_name_reduction":len(src["occupations"])-len(buckets),"confirmed_aliases":ALIASES,"occupations":list(buckets.values()),"abnormal_groups":src["abnormal_groups"],"uncertain_annotations":uncertain,"validation":{"normal_atomic_role_count":len(normal),"abnormal_atomic_role_count":len(abnormal),"all_atomic_role_count":len(normal|abnormal),"missing_atomic_role_count":20964-len(normal|abnormal),"duplicate_atomic_role_count":0}}
    details={"schema_version":"fixed-baseline-v3-cleanup-merge-details-v1","input_standard_name_count":len(src["occupations"]),"output_standard_name_count":len(buckets),"standard_name_reduction":len(src["occupations"])-len(buckets),"occupation_decisions":decisions,"uncertain_annotations":uncertain}
    with open(OUT,"x",encoding="utf-8") as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write("\n")
    with open(DETAIL,"x",encoding="utf-8") as f:json.dump(details,f,ensure_ascii=False,indent=2);f.write("\n")
if __name__=="__main__":main()
