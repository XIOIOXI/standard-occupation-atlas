from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
ROOT=Path('data/processed/record_role_classification_v1')
BASE=ROOT/'api_trials'/'deepseek_name_classification_trial_full_v1'/'full_name_only_mapping_draft_v1.json'
TAX=ROOT/'catalog_mappings'/'taxonomy_embedding_texts_v1.json'
DIR=ROOT/'targeted_name_repairs'/'name_only_targeted_repair_v1'
BATCH=DIR/'deepseek_review_batches'
OUT=DIR/'full_name_only_mapping_repaired_v1.json'; CHANGES=DIR/'repair_decision_log_v1.json'
def r(p): return json.loads(p.read_text(encoding='utf-8'))
def x(p,v):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as h: json.dump(v,h,ensure_ascii=False,indent=2);h.write('\n')
def main():
 if OUT.exists() or CHANGES.exists(): raise FileExistsError('refusing overwrite')
 base=r(BASE); tax=r(TAX); ids={z['category_id'] for z in tax['rows']};ids|={z['level_1'] for z in tax['rows']};ids|={z['category_id'].rsplit('/',1)[0] for z in tax['rows']}
 decisions=[q for p in sorted(BATCH.glob('batch_*_reviewed.json')) for q in r(p)['results']]
 by={q['occupation_id']:q for q in decisions}
 if len(by)!=981: raise ValueError(f'expected 981 unique reviews, got {len(by)}')
 changes=[]
 for row in base['results']:
  d=by.get(row['standard_occupation_id'])
  if not d: continue
  before={'status':row['status'],'target_category_id':row['target_category_id']}; dec=d['decision']; target=d['target_category_id']
  if target is not None and target not in ids: raise ValueError('bad target')
  if dec=='reclassify': row['target_category_id']=target; row['status']='mapped' if target in {z['category_id'] for z in tax['rows']} else 'review'
  elif dec=='fallback_review': row['target_category_id']=target; row['status']='review'
  elif dec in {'multi_role','taxonomy_gap'}: row['target_category_id']=None; row['status']=dec
  row['targeted_repair']={'decision':dec,'reason':d['reason'],'processing_method':'deepseek_api_name_only_targeted_repair'}
  after={'status':row['status'],'target_category_id':row['target_category_id']}
  changes.append({'standard_occupation_id':row['standard_occupation_id'],'standard_name':row['standard_name'],'before':before,'after':after,'decision':dec,'reason':d['reason'],'changed':before!=after})
 allids=[z['standard_occupation_id'] for z in base['results']]
 if len(allids)!=10998 or len(set(allids))!=10998: raise ValueError('occupation coverage invalid')
 if any(z['target_category_id'] is not None and z['target_category_id'] not in ids for z in base['results']): raise ValueError('invalid category remains')
 base['schema_version']='deepseek-name-only-full-mapping-repaired-v1';base['base_draft_path']=str(BASE);base['targeted_repair_scope']='981 screened name-only risks reviewed by DeepSeek; unscreened rows retain draft result.';base['repair_summary']={'reviewed_count':len(decisions),'decision_counts':dict(Counter(q['decision'] for q in decisions)),'changed_count':sum(q['changed'] for q in changes),'final_status_counts':dict(Counter(q['status'] for q in base['results']))}
 x(CHANGES,{'schema_version':'targeted-name-repair-log-v1','base_path':str(BASE),'reviewed_count':len(decisions),'decision_counts':dict(Counter(q['decision'] for q in decisions)),'changes':changes})
 x(OUT,base)
 print(json.dumps({'output':str(OUT),'log':str(CHANGES),'summary':base['repair_summary'],'atomic_validation':base['source_linkage_validation']},ensure_ascii=False))
if __name__=='__main__':main()
