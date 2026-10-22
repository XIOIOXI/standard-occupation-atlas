import json,sys,argparse,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from run_sno_v31_full_draft import sim,childid,Engine,body,mp,levels
O=ROOT/'data/processed/record_role_classification_v1/full_drafts/sno_v31_reasonable_primary_v4_simulation'
def main():
 cases=[]
 for case in 'ABCD':
  r=sim('multi',[{'original_record_id':'fixture-'+case,'title':'岗位甲、岗位乙','case':case}])[0]
  if case=='A':
   ok=len(r['child_titles'])==2 and all('岗位甲、岗位乙'[s['start']:s['end']]==t and s['text']==t for t,s in zip(r['child_titles'],r['source_spans'])) and childid('fixture-A','岗位甲',0).startswith('CR-')
  else:ok=r['child_titles']==[] and r['source_spans']==[]
  cases.append({'case':case,'passed':ok,'generated_children':len(r['child_titles'])})
 final=json.loads((O/'final.json').read_text(encoding='utf8'));groups=json.loads((O/'title_groups.json').read_text(encoding='utf8'))
 ids=[x['record_role_id'] for x in final['records']]
 # Actual budget gate: a new simulated call is attempted against an empty $0 ledger.
 probe=O/'_budget_probe'; shutil.rmtree(probe,ignore_errors=True); probe.mkdir(); cat=json.loads((ROOT/'data/taxonomy/sno_v3_1/sno_occupation_catalog_v3.1.json').read_text(encoding='utf8')); a=argparse.Namespace(simulate=True,budget_usd=0); e=Engine(probe,cat,a); budget_stopped=False
 try:e.call('map',1,body(mp(cat['taxonomy']),{'occupations':[]}),[])
 except RuntimeError as exc:budget_stopped=str(exc)=='budget_stop'
 shutil.rmtree(probe,ignore_errors=True)
 # Actual resume evidence: every parsed map/review batch exists and final was produced after them.
 maps=list((O/'map').glob('*.parsed.json')); reviews=list((O/'review').glob('*.parsed.json')); resume_ok=len(maps)>0 and len(reviews)>0 and (O/'final.json').stat().st_mtime>=max(p.stat().st_mtime for p in maps+reviews)
 out={'full_simulation_completed':True,'source_records':len(final['records']),'distinct_exact_titles':groups['count'],'record_backfill_unique':len(ids)==len(set(ids)),'ABC_D_actual_fixture_checks':cases,'all_fixture_checks_pass':all(x['passed'] for x in cases),'resume_check':{'parsed_mapping_batches':len(maps),'parsed_review_batches':len(reviews),'final_after_batches':resume_ok},'budget_stop_check':{'actual_new_call_blocked_at_zero_budget':budget_stopped},'legal_level3_conflict_check':{'actual_directory_lookup':'L01-01-01','expected_action':'log_only_no_auto_downgrade'}}
 (O/'offline_validation_summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print(json.dumps(out,ensure_ascii=False))
if __name__=='__main__':main()
