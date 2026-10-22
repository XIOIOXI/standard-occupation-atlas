import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from run_deepseek_name_classification_trial_v1 import usage_summary,estimate_cost
O=ROOT/'data/processed/record_role_classification_v1/api_trials/deepseek_sno_v31_reasonable_primary_36'
OLD=ROOT/'data/processed/record_role_classification_v1/api_trials/deepseek_sno_v31_contract_200'
def load(p):return json.loads(p.read_text(encoding='utf8'))
def main():
 cmp=load(O/'review_to_reasonable_primary_comparison.json')['records']; merged=load(O/'merged_200_results.json')
 raws=[]
 for p in sorted(O.glob('*raw_response.json')): raws.append((p.name,load(p)))
 for p in sorted(O.glob('*invalid_model_output.json')): raws.append((p.name,load(p)['raw']))
 seen=set(); detail=[]
 for name,r in raws:
  if r.get('id') in seen:continue
  seen.add(r.get('id')); u=usage_summary(r); t=datetime.fromtimestamp(r['created'],timezone.utc) if isinstance(r.get('created'),(int,float)) else datetime.now(timezone.utc); detail.append({'artifact':name,'request_id':r.get('id'),'usage':u,'estimated_cost':estimate_cost(u,t)})
 # The review runner persisted parsed usage for batches 2-12 but, due to its
 # earlier artifact-writing bug, not their duplicate raw envelope. Count that
 # API-reported usage here rather than under-reporting cost.
 for p in sorted(O.glob('review_v3_*_parsed.json')):
  if p.name == 'review_v3_001_parsed.json': continue
  x=load(p); detail.append({'artifact':p.name,'request_id':None,'usage':x['usage'],'estimated_cost':x['cost'],'raw_envelope_missing':True})
 u=Counter();[u.update(x['usage']) for x in detail]; new=sum(x['estimated_cost']['estimated_usd'] for x in detail)
 old=load(OLD/'contract_200_final_report_adjudicated_v2.json')['cost']['cumulative_estimated_usd']
 report={'version':'sno-v3.1-reasonable-primary-v1','source_prior_review_count':36,'new_response_count':len(detail),'new_response_cost_detail':detail,'new_usage':dict(u),'new_estimated_usd':new,'prior_contract_run_estimated_usd':old,'cumulative_estimated_usd':new+old,'budget_for_this_supplement_usd':1,'supplement_within_budget':new<=1,'supplement_mapping_status_counts':dict(Counter(x['reasonable_primary']['status'] for x in cmp)),'ai_reasonableness_review_counts':dict(Counter(x['ai_reasonableness_review']['verdict'] for x in cmp)),'merged_200_status_counts':merged['status_counts'],'newly_mapped':[{'occupation_id':x['occupation_id'],'title':x['title'],'previous_status':x['previous']['status'],'target_category_id':x['reasonable_primary']['target_category_id'],'target_level':x['reasonable_primary']['target_level'],'reason':x['reasonable_primary']['reason']} for x in cmp if x['reasonable_primary']['status']=='mapped'],'still_review':[{'occupation_id':x['occupation_id'],'title':x['title'],'reason':x['reasonable_primary']['reason']} for x in cmp if x['reasonable_primary']['status']=='review'],'interpretation':'AI pass means current reasonable primary placement was not found clearly unreasonable; it is not true accuracy under a unique-answer standard.'}
 p=O/'final_report.json';p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'new_cost':new,'cumulative':new+old,'newly_mapped':len(report['newly_mapped']),'still_review':len(report['still_review'])},ensure_ascii=False))
if __name__=='__main__':main()
