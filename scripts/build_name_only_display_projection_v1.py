from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path
ROOT=Path('data/processed/record_role_classification_v1')
SRC=ROOT/'targeted_name_repairs'/'name_only_targeted_repair_v1'/'full_name_only_mapping_repaired_v1.json'
TAX=ROOT/'catalog_mappings'/'taxonomy_embedding_texts_v1.json'
OUT=ROOT/'targeted_name_repairs'/'name_only_targeted_repair_v1'/'display_projection_v1.json'
def r(p): return json.loads(p.read_text(encoding='utf-8'))
def main():
 if OUT.exists(): raise FileExistsError(OUT)
 s=r(SRC); rows={x['category_id']:x for x in r(TAX)['rows']}; nodes=defaultdict(list); waiting=[]; multi=[]; gaps=[]
 for x in s['results']:
  item={'standard_occupation_id':x['standard_occupation_id'],'label':x['standard_name'],'original_group_ids':x['original_group_ids'],'source_atomic_unit_ids':x['source_atomic_unit_ids'],'source_record_ids':x['source_record_ids'],'status':x['status'],'reason':x.get('reason')}
  cid=x['target_category_id']; cat=rows.get(cid)
  if x['status']=='mapped' and cat: nodes[cid].append(item)
  elif x['status']=='multi_role': multi.append(item)
  elif x['status']=='taxonomy_gap': gaps.append(item)
  else:
   # valid l1/l2 paths become their own Other bucket; null remains waiting.
   (nodes[(cid or 'pending')+'/other'].append(item) if cid else waiting.append(item))
 output={'schema_version':'name-only-display-projection-v1','source_mapping':str(SRC),'category_bubbles':{cid:{'category':rows[cid],'occupations':v} for cid,v in nodes.items() if cid in rows},'other_buckets':{cid:v for cid,v in nodes.items() if cid not in rows},'pending_classification':waiting,'multi_role_pending_split':multi,'taxonomy_gaps':gaps,'abnormal_groups':s['unclassified_abnormal_groups'],'validation':s['source_linkage_validation']}
 with OUT.open('x',encoding='utf-8') as f: json.dump(output,f,ensure_ascii=False,indent=2);f.write('\n')
 print(json.dumps({'output':str(OUT),'bubbles':len(output['category_bubbles']),'pending':len(waiting),'multi':len(multi),'gaps':len(gaps),'abnormal':len(output['abnormal_groups'])},ensure_ascii=False))
if __name__=='__main__':main()
