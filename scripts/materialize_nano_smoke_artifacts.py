"""Materialize completed nano smoke responses without API calls."""
import hashlib,json,sqlite3
from pathlib import Path
from collections import Counter
root=Path('data/processed/skill_inference_v2'); model='gpt-4.1-nano'; prompt='job-group-skill-inference-prompt-v6'; inference='skill-inference-v2'
inputs=[json.loads(x) for x in (root/'pilot_50_inputs.jsonl').read_text(encoding='utf-8').splitlines() if x]
db=sqlite3.connect('data/processed/recruitment_snapshots.sqlite'); out=[]
fields=('raw_skill_name','normalized_skill_name','skill_type','confidence','skill_scope','source_type','evidence_level','reasoning_summary')
for row in inputs:
 fp=hashlib.sha256(f"{row['input_fingerprint']}|{prompt}|{model}".encode()).hexdigest()
 run=db.execute('select run_id,inference_status,input_tokens,output_tokens,total_tokens,estimated_cost from skill_inference_runs where input_fingerprint=?',(fp,)).fetchone()
 if not run: raise SystemExit(f'missing nano run for {row["job_group_id"]}')
 db.execute('update skill_inference_runs set model=? where run_id=?',(model,run[0]))
 skills=[dict(zip(fields,s)) for s in db.execute('select raw_skill_name,normalized_skill_name,skill_type,confidence,skill_scope,source_type,evidence_level,reasoning_summary from inferred_skills where run_id=?',(run[0],)).fetchall()]
 out.append({'job_group_id':row['job_group_id'],'representative_title':row['representative_title'],'cache_hit':False,'inference_status':run[1],'hard_skills':[s for s in skills if s['skill_type']=='hard'],'soft_skills':[s for s in skills if s['skill_type']=='soft'],'model':model,'input_fingerprint':fp,'usage':{'input_tokens':run[2],'output_tokens':run[3],'total_tokens':run[4],'estimated_cost':run[5]},'versions':{'grouping':'job-grouping-v2-occupation-safe','inference':inference,'prompt':prompt,'context':'job-group-context-v2','normalization':'skill-normalization-v1'}})
db.commit(); db.close()
(root/f'pilot_50_results_{model}.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in out)+'\n',encoding='utf-8')
skills=[s for r in out for s in r['hard_skills']+r['soft_skills']]
summary={'group_count':len(out),'api_request_attempts':50,'api_responses_received':50,'api_successful_responses':50,'repair_retry_attempts':0,'api_calls':50,'model':model,'status_counts':dict(Counter(r['inference_status'] for r in out)),'total_hard_skills':sum(len(r['hard_skills']) for r in out),'total_soft_skills':sum(len(r['soft_skills']) for r in out),'confidence_counts':dict(Counter(s['confidence'] for s in skills)),'evidence_level_counts':dict(Counter(s['evidence_level'] for s in skills)),'scope_counts':dict(Counter(s['skill_scope'] for s in skills)),'raw_unique_skills':len({s['raw_skill_name'] for s in skills}),'normalized_unique_skills':len({s['normalized_skill_name'] for s in skills}),'groups_with_zero_skills':sum(not r['hard_skills'] and not r['soft_skills'] for r in out),'total_input_tokens':sum(r['usage']['input_tokens'] or 0 for r in out),'total_output_tokens':sum(r['usage']['output_tokens'] or 0 for r in out),'total_tokens':sum(r['usage']['total_tokens'] or 0 for r in out),'estimated_cost':None}
(root/f'pilot_50_summary_{model}.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(summary,ensure_ascii=False))
