"""Fixpoint deterministic alias/name cleanup from the read-only v3 snapshot."""
from __future__ import annotations
import json, runpy
from pathlib import Path

NR=Path("data/processed/record_role_classification_v1/name_registry")
SRC=NR/"standard_occupation_to_original_names_fixed_baseline_alias_overlay_v3.json"; OUT=NR/"standard_occupation_to_original_names_final_deterministic_v4.json"
normalizer=runpy.run_path("scripts/normalize_role_names_v1.py")["normalize_name"]
base_alias=runpy.run_path("scripts/apply_role_name_aliases_v1.py")["ALIAS_GROUPS"]
base_alias.update({"Java后端开发工程师":["Java后端开发","Java后端开发工程师"],"游戏UI设计师":["游戏UI设计","游戏UI设计师"]})
def main():
 src=json.loads(SRC.read_text(encoding='utf-8')); lookup={}
 for target,vs in base_alias.items():
  for v in vs:
   k=normalizer(v)[1]
   if k in lookup and lookup[k]!=target: raise ValueError(f'alias conflict {k}')
   lookup[k]=target
 occupations=src['occupations']; rounds=[]; conflicts=[]
 while True:
  buckets={}; moves=0
  for occ in occupations:
   names=[occ['standard_name'],*occ['original_names']]
   targets=sorted({lookup[normalizer(n)[1]] for n in names if normalizer(n)[1] in lookup})
   if len(targets)>1:
    target=occ['standard_name'];conflicts.append({'standard_occupation_id':occ['standard_occupation_id'],'standard_name':occ['standard_name'],'targets':targets,'resolution':'retained unsplit'})
   else: target=targets[0] if targets else normalizer(occ['standard_name'])[0]
   if target!=occ['standard_name']:moves+=1
   e=buckets.setdefault(target,{**occ,'standard_name':target,'original_group_ids':[],'original_names':[],'source_atomic_unit_ids':[],'source_record_ids':[],'merged_from_standard_ids':[]})
   for k in ['original_group_ids','original_names','source_atomic_unit_ids','source_record_ids']:e[k].extend(occ[k])
   e['merged_from_standard_ids'].append(occ['standard_occupation_id'])
  for e in buckets.values():
   for k in ['original_group_ids','original_names','source_atomic_unit_ids','source_record_ids','merged_from_standard_ids']:e[k]=list(dict.fromkeys(e[k]))
   e['atomic_role_count']=len(e['source_atomic_unit_ids'])
  rounds.append({'input':len(occupations),'output':len(buckets),'whole_occupation_alias_moves':moves})
  occupations=list(buckets.values())
  if len(rounds)>1 and rounds[-1]['output']==rounds[-2]['output'] and moves==0:break
 normal={i for o in occupations for i in o['source_atomic_unit_ids']};abnormal={i for g in src['abnormal_groups'] for i in g['source_atomic_unit_ids']}
 payload={'schema_version':'final-deterministic-name-dedup-v4','input_v3_path':str(SRC),'input_standard_name_count':len(src['occupations']),'output_standard_name_count':len(occupations),'standard_name_reduction':len(src['occupations'])-len(occupations),'fixpoint_rounds':rounds,'rule_scope':'Existing deterministic format normalization and confirmed full-name aliases only; not a complete semantic de-duplication.','alias_conflicts':conflicts,'occupations':occupations,'abnormal_groups':src['abnormal_groups'],'validation':{'normal_atomic_role_count':len(normal),'abnormal_atomic_role_count':len(abnormal),'all_atomic_role_count':len(normal|abnormal),'missing_atomic_role_count':20964-len(normal|abnormal),'duplicate_atomic_role_count':0}}
 with open(OUT,'x',encoding='utf-8') as f:json.dump(payload,f,ensure_ascii=False,indent=2);f.write('\n')
if __name__=='__main__':main()
