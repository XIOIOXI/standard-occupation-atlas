"""Concurrency-safe selective inference: parallel HTTP workers, one SQLite writer, no retries."""
from __future__ import annotations
import json, os, sqlite3, uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from run_skill_inference_v2_pilot import (MODEL,GROUPING_VERSION,INFERENCE_VERSION,PROMPT_VERSION,CONTEXT_SELECTION_VERSION,SKILL_NORMALIZATION_VERSION,SqliteSkillInferenceRepository,load_project_dotenv,build_request,validate_request_contract,call,extract_response_text,extract_usage,parse_and_validate_response,execution_fingerprint,classify_exception)

ROOT=Path('data/processed/skill_inference_v2/selective_mini_1000'); DB_PATH=Path('data/processed/recruitment_snapshots.sqlite'); WORKERS=5
def hydrate(db,row,fp):
 cached=db.execute('SELECT run_id,inference_status,input_tokens,output_tokens,total_tokens,estimated_cost FROM skill_inference_runs WHERE job_group_id=? AND inference_version=? AND input_fingerprint=?',(row['job_group_id'],INFERENCE_VERSION,fp)).fetchone()
 if not cached:return None
 saved=db.execute('SELECT raw_skill_name,normalized_skill_name,skill_type,confidence,skill_scope,source_type,evidence_level,reasoning_summary FROM inferred_skills WHERE run_id=?',(cached[0],)).fetchall(); keys=('raw_skill_name','normalized_skill_name','skill_type','confidence','skill_scope','source_type','evidence_level','reasoning_summary'); skills=[dict(zip(keys,x)) for x in saved]
 return {'job_group_id':row['job_group_id'],'representative_title':row['representative_title'],'cache_hit':True,'inference_status':cached[1],'hard_skills':[x for x in skills if x['skill_type']=='hard'],'soft_skills':[x for x in skills if x['skill_type']=='soft'],'model':MODEL,'input_fingerprint':fp,'usage':dict(zip(('input_tokens','output_tokens','total_tokens','estimated_cost'),cached[2:]))}
def request_one(row,fp):
 usage={'input_tokens':None,'output_tokens':None,'total_tokens':None,'estimated_cost':None}; hard=[];soft=[];status='failed_validation';raw=None;diagnostic=None
 try:
  response=call(row['prepared_inference_input'],MODEL); usage=extract_usage(response); raw=json.loads(extract_response_text(response)); _,status,hard,soft=parse_and_validate_response({'output_text':json.dumps(raw,ensure_ascii=False)})
 except Exception as error: diagnostic=classify_exception(error,request_stage='inference_request',validation_stage='response_validation',response_received=True)
 return row,fp,status,hard,soft,usage,raw,diagnostic
def persist(db,rec):
 row,fp,status,hard,soft,usage,raw,diagnostic=rec; now=datetime.now(timezone.utc).isoformat();run_id=str(uuid.uuid4())
 with db:
  db.execute('INSERT INTO skill_inference_runs (run_id,job_group_id,grouping_version,inference_version,input_fingerprint,prompt_version,model,context_selection_version,skill_normalization_version,inference_status,created_at,completed_at,input_tokens,output_tokens,total_tokens,estimated_cost) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(run_id,row['job_group_id'],GROUPING_VERSION,INFERENCE_VERSION,fp,PROMPT_VERSION,MODEL,CONTEXT_SELECTION_VERSION,SKILL_NORMALIZATION_VERSION,status,now,now,usage['input_tokens'],usage['output_tokens'],usage['total_tokens'],usage['estimated_cost']))
  db.executemany('INSERT INTO inferred_skills (inferred_skill_id,run_id,raw_skill_name,normalized_skill_name,skill_type,confidence,source_type,evidence_level,reasoning_summary,skill_scope) VALUES (?,?,?,?,?,?,?,?,?,?)',[(str(uuid.uuid4()),run_id,s['raw_skill_name'],s['normalized_skill_name'],s['skill_type'],s['confidence'],s['source_type'],s['evidence_level'],s['reasoning_summary'],s['skill_scope']) for s in hard+soft])
  if diagnostic: db.execute('INSERT INTO skill_inference_diagnostics (diagnostic_id,run_id,job_group_id,inference_version,error_category,diagnostic_json,created_at,model,exception_type,http_status,openai_error_code,request_stage,validation_stage,response_received,retryable,sanitized_message) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),run_id,row['job_group_id'],INFERENCE_VERSION,diagnostic['error_category'],json.dumps(diagnostic,ensure_ascii=False),now,MODEL,diagnostic['exception_type'],diagnostic['http_status_code'],diagnostic['api_error_code'],diagnostic['request_stage'],diagnostic['validation_stage'],int(diagnostic['response_received']),int(diagnostic['retryable']),diagnostic['message']))
 if raw is not None:
  with (ROOT/'raw_model_outputs.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'job_group_id':row['job_group_id'],'model':MODEL,'inference_version':INFERENCE_VERSION,'prompt_version':PROMPT_VERSION,'output':raw},ensure_ascii=False)+'\n')
 item={'job_group_id':row['job_group_id'],'representative_title':row['representative_title'],'cache_hit':False,'inference_status':status,'hard_skills':hard,'soft_skills':soft,'model':MODEL,'input_fingerprint':fp,'usage':usage}
 if diagnostic:item['diagnostic']=diagnostic
 with (ROOT/'results_checkpoint.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(item,ensure_ascii=False)+'\n')
 return item
def main():
 load_project_dotenv(); rows=[json.loads(x) for x in (ROOT/'selected_inputs.jsonl').read_text(encoding='utf-8').splitlines() if x]
 if len(rows)!=1000 or len({x['job_group_id'] for x in rows})!=1000: raise SystemExit('selection must be exactly 1,000 unique groups')
 if any(validate_request_contract(build_request(r['prepared_inference_input'],MODEL),group_count=1,max_attempts=1,retry_enabled=False) for r in rows):raise SystemExit('preflight failed')
 if not os.environ.get('OPENAI_API_KEY'):raise SystemExit('OPENAI_API_KEY unavailable')
 SqliteSkillInferenceRepository(str(DB_PATH)).initialise();db=sqlite3.connect(DB_PATH); output=[];pending=[];cache_hits=0
 for row in rows:
  fp=execution_fingerprint(row['input_fingerprint'],MODEL);item=hydrate(db,row,fp)
  if item:output.append(item);cache_hits+=1
  else:pending.append((row,fp))
 attempts=responses=0
 try:
  with ThreadPoolExecutor(max_workers=WORKERS) as pool:
   futures={pool.submit(request_one,row,fp):(row,fp) for row,fp in pending}
   for n,future in enumerate(as_completed(futures),1):
    rec=future.result();attempts+=1; responses+=1; output.append(persist(db,rec))
    if n%25==0:print(json.dumps({'new_requests_completed':n,'new_requests_total':len(pending),'cache_hits':cache_hits},ensure_ascii=False),flush=True)
 finally:db.close()
 output.sort(key=lambda x:x['job_group_id']);(ROOT/'results.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in output)+'\n',encoding='utf-8')
 skills=[s for x in output for s in x['hard_skills']+x['soft_skills']]; usage=[x['usage'] for x in output]
 summary={'selection_name':'selective-mini-1000','selected_groups':len(output),'cached_groups_reused':cache_hits,'new_api_requests':attempts,'successful_api_responses':responses,'completed':sum(x['inference_status']=='completed' for x in output),'insufficient_context':sum(x['inference_status']=='insufficient_context' for x in output),'skipped_generic':sum(x['inference_status']=='skipped_generic' for x in output),'failed_validation':sum(x['inference_status']=='failed_validation' for x in output),'hard_skill_count':sum(len(x['hard_skills']) for x in output),'soft_skill_count':sum(len(x['soft_skills']) for x in output),'raw_unique_skills':len({s['raw_skill_name'] for s in skills}),'v1_normalized_unique_skills':len({s['normalized_skill_name'] for s in skills}),'input_tokens':sum(x['input_tokens'] or 0 for x in usage),'output_tokens':sum(x['output_tokens'] or 0 for x in usage),'total_tokens':sum(x['total_tokens'] or 0 for x in usage),'model':MODEL,'prompt_version':PROMPT_VERSION,'inference_version':INFERENCE_VERSION,'normalization_version':'skill-normalization-v2','no_retry':True,'parallel_http_workers':WORKERS,'sqlite_writers':1}
 (ROOT/'inference_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
