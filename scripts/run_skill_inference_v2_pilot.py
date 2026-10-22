"""Bounded 50-group OpenAI Skill Inference pilot. Reads key only from environment."""
from __future__ import annotations
import argparse, hashlib, json, os, re, sqlite3, sys, urllib.error, urllib.request, uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, 'backend')
from app.domain.skills.inference import INFERENCE_VERSION, PROMPT_VERSION, CONTEXT_SELECTION_VERSION, SKILL_NORMALIZATION_VERSION, normalize_skill
from app.infrastructure.sqlite_skill_inference_repository import SqliteSkillInferenceRepository

MODEL='gpt-4.1-mini'; GROUPING_VERSION='job-grouping-v2-occupation-safe'
ERROR_CATEGORIES={'api_authentication_error','api_model_access_error','api_rate_limit_error','api_network_error','api_request_error','structured_output_error','schema_validation_error','unknown_api_error'}
SYSTEM='''You infer candidate skills from bounded recruitment role context. Return the result as a json object. Return JSON only. The top-level status MUST be exactly one of: completed, insufficient_context, skipped_generic. Never invent another status. Return a top-level skills array. Each skill object MUST contain raw_skill_name (non-empty string), skill_type (exactly hard or soft), confidence (exactly high, medium, or low), skill_scope (exactly occupation_core or domain_specific), and reasoning_summary (short string). Every skill is inferred with source_type=llm_inference and evidence_level=inferred_medium or inferred_low. Use at most five hard and five soft skills. If context is insufficient, use insufficient_context with an empty skills array; if the title is generic or unsuitable, use skipped_generic with an empty skills array. Never claim a skill is explicitly required. Infer only skills reasonably supported by title and supplied context. Do not invent tools, frameworks, certifications, duties, or statistics. Soft skills must not be generic boilerplate.'''
ENDPOINT='https://api.openai.com/v1/responses'

def build_request(payload, model=MODEL):
 actual_input='Return the following inference result as a json object.\n'+json.dumps(payload,ensure_ascii=False)
 return {'model':model,'instructions':SYSTEM,'input':actual_input,'text':{'format':{'type':'json_object'}}}

def validate_request_contract(body, *, prompt_version=PROMPT_VERSION, group_count=None, single_group=False, max_attempts=1, retry_enabled=False):
 errors=[]
 if not body.get('model'): errors.append('model must be non-empty')
 if not ENDPOINT or not isinstance(body,dict): errors.append('endpoint/request structure missing')
 if not body.get('instructions') or not body.get('input'): errors.append('instructions and input must be non-empty')
 fmt=((body.get('text') or {}).get('format') or {})
 if fmt.get('type')=='json_object' and 'json' not in str(body.get('input','')): errors.append('json_object request input must contain lowercase json')
 if not prompt_version: errors.append('prompt_version must be non-empty')
 if single_group and (group_count!=1 or max_attempts!=1 or retry_enabled): errors.append('single-group diagnostic contract invalid')
 return errors

def load_project_dotenv() -> None:
 """Load only unset variables from the project-root .env; never log values."""
 path=Path('.env')
 if not path.exists(): return
 for line in path.read_text(encoding='utf-8').splitlines():
  line=line.strip()
  if not line or line.startswith('#') or '=' not in line: continue
  key,value=line.split('=',1); key=key.strip(); value=value.strip().strip('"').strip("'")
  if key and key not in os.environ: os.environ[key]=value

class StructuredOutputError(Exception): pass
class SchemaValidationError(Exception): pass

def extract_response_text(response):
 if isinstance(response,dict) and isinstance(response.get('output_text'),str) and response['output_text'].strip(): return response['output_text']
 for item in (response.get('output',[]) if isinstance(response,dict) else []):
  for content in (item.get('content',[]) if isinstance(item,dict) else []):
   if isinstance(content,dict) and content.get('type') in {'output_text','text'} and isinstance(content.get('text'),str) and content['text'].strip(): return content['text']
 raise StructuredOutputError('missing_response_output_text')

def _safe_message(value):
 msg=str(value)[:240]
 key=os.environ.get('OPENAI_API_KEY')
 if key: msg=msg.replace(key,'[REDACTED]')
 return re.sub(r'(?i)(authorization|bearer|api[_ -]?key)\s*[:=]\s*[^\s,;]+', r'\1=[REDACTED]', msg)

def classify_exception(error, *, request_stage='unknown', validation_stage=None, response_received=False):
 status=None; api_code=None; api_type=None; api_param=None; api_message=None; retryable=False; category='unknown_api_error'
 if isinstance(error, urllib.error.HTTPError):
  status=error.code; response_received=True
  try:
   body=json.loads(error.read(4096).decode('utf-8','replace')); info=body.get('error') or {}; api_code=info.get('code'); api_type=info.get('type'); api_param=info.get('param'); api_message=info.get('message')
  except Exception: pass
  if status==401: category='api_authentication_error'
  elif status in (403,404): category='api_model_access_error'
  elif status==429: category='api_rate_limit_error'; retryable=True
  elif 400 <= status < 500: category='api_request_error'
  else: category='unknown_api_error'; retryable=status >= 500
 elif isinstance(error,(urllib.error.URLError,TimeoutError,ConnectionError)):
  category='api_network_error'; retryable=True
 elif isinstance(error,StructuredOutputError): category='structured_output_error'; response_received=True
 elif isinstance(error,SchemaValidationError): category='schema_validation_error'; response_received=True
 elif isinstance(error,json.JSONDecodeError): category='structured_output_error'; response_received=True
 return {'exception_type':type(error).__name__,'http_status_code':status,'api_error_type':api_type,'api_error_code':api_code,'api_error_param':api_param,'api_error_message':_safe_message(api_message) if api_message else None,'error_category':category,'model':MODEL,'request_stage':request_stage,'validation_stage':validation_stage,'response_received':bool(response_received),'retryable':retryable,'message':_safe_message(api_message or error)}

def select_rows(rows, single_group_id=None):
 if single_group_id is None: return rows, False
 selected=[x for x in rows if x.get('job_group_id')==single_group_id]
 if len(selected)!=1: raise ValueError('single-group diagnostic mode requires exactly one matching group')
 return selected, True

def call(payload, model=MODEL):
 body=build_request(payload, model)
 request=urllib.request.Request(ENDPOINT,data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+os.environ['OPENAI_API_KEY'],'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(request,timeout=90) as response:
  try: return json.loads(response.read())
  except json.JSONDecodeError as error: raise StructuredOutputError('response was not valid JSON') from error

def parse_and_validate_response(response):
 try: raw=json.loads(response.get('output_text',''))
 except json.JSONDecodeError as error: raise StructuredOutputError('json_parse_error') from error
 status=raw.get('status','failed_validation')
 if status not in {'completed','insufficient_context','skipped_generic'}: raise SchemaValidationError('invalid status')
 skills=raw.get('skills',[])
 if not isinstance(skills,list) or len(skills)>10: raise SchemaValidationError('invalid skills')
 hard=[]; soft=[]; seen=set()
 for s in skills:
  name=str(s.get('raw_skill_name','')).strip(); kind=s.get('skill_type'); conf=s.get('confidence'); scope=s.get('skill_scope','occupation_core'); norm=normalize_skill(name)
  if not name or kind not in {'hard','soft'} or conf not in {'high','medium','low'} or scope not in {'occupation_core','domain_specific'} or norm in seen: raise SchemaValidationError('invalid skill')
  seen.add(norm); item={'raw_skill_name':name,'normalized_skill_name':norm,'skill_type':kind,'confidence':conf,'skill_scope':scope,'source_type':'llm_inference','evidence_level':'inferred_medium' if conf in {'high','medium'} else 'inferred_low','reasoning_summary':str(s.get('reasoning_summary','')).strip()[:240]}
  (hard if kind=='hard' else soft).append(item)
 if len(hard)>5 or len(soft)>5 or (status=='completed' and not skills): raise SchemaValidationError('status/skill mismatch')
 return raw,status,hard,soft

def extract_usage(response):
 usage=response.get('usage') if isinstance(response,dict) else None
 if not isinstance(usage,dict): return {'input_tokens':None,'output_tokens':None,'total_tokens':None,'estimated_cost':None}
 return {'input_tokens':usage.get('input_tokens'),'output_tokens':usage.get('output_tokens'),'total_tokens':usage.get('total_tokens'),'estimated_cost':None}

def execution_fingerprint(input_fingerprint, model=MODEL):
 return hashlib.sha256(f'{input_fingerprint}|{PROMPT_VERSION}|{model}'.encode()).hexdigest()

def main(single_group_id=None, model=MODEL):
 load_project_dotenv()
 root=Path('data/processed/skill_inference_v2'); rows=[json.loads(x) for x in (root/'pilot_50_inputs.jsonl').read_text(encoding='utf-8').splitlines() if x]
 if len(rows)!=50 or len({x['job_group_id'] for x in rows})!=50: raise SystemExit('Pilot must be exactly 50 unique groups')
 rows, diagnostic_mode=select_rows(rows, single_group_id)
 preflight_errors=[]
 for item in rows: preflight_errors.extend(validate_request_contract(build_request(item['prepared_inference_input'],model),group_count=len(rows),single_group=diagnostic_mode,max_attempts=1,retry_enabled=False))
 if preflight_errors: raise SystemExit('Local request preflight failed: '+'; '.join(preflight_errors))
 if not os.environ.get('OPENAI_API_KEY'): raise SystemExit('No OPENAI_API_KEY; pilot remains execution-ready.')
 SqliteSkillInferenceRepository('data/processed/recruitment_snapshots.sqlite').initialise()
 db=sqlite3.connect('data/processed/recruitment_snapshots.sqlite'); out=[]; request_attempts=0; responses_received=0; successful_responses=0; repair_retry_attempts=0
 try:
  for row in rows:
   p=row['prepared_inference_input']; fp=execution_fingerprint(row['input_fingerprint'],model)
   cached=db.execute('SELECT run_id,inference_status FROM skill_inference_runs WHERE job_group_id=? AND inference_version=? AND input_fingerprint=? AND model=?',(row['job_group_id'],INFERENCE_VERSION,fp,model)).fetchone()
   if cached and not diagnostic_mode:
    saved=db.execute('SELECT raw_skill_name,normalized_skill_name,skill_type,confidence,skill_scope,source_type,evidence_level,reasoning_summary FROM inferred_skills WHERE run_id=?',(cached[0],)).fetchall()
    skills_saved=[{'raw_skill_name':x[0],'normalized_skill_name':x[1],'skill_type':x[2],'confidence':x[3],'skill_scope':x[4],'source_type':x[5],'evidence_level':x[6],'reasoning_summary':x[7]} for x in saved]
    usage_saved=db.execute('SELECT input_tokens,output_tokens,total_tokens,estimated_cost FROM skill_inference_runs WHERE run_id=?',(cached[0],)).fetchone()
    out.append({'job_group_id':row['job_group_id'],'representative_title':row['representative_title'],'cache_hit':True,'inference_status':cached[1],'hard_skills':[x for x in skills_saved if x['skill_type']=='hard'],'soft_skills':[x for x in skills_saved if x['skill_type']=='soft'],'model':model,'input_fingerprint':fp,'usage':{'input_tokens':usage_saved[0],'output_tokens':usage_saved[1],'total_tokens':usage_saved[2],'estimated_cost':usage_saved[3]},'versions':{'grouping':GROUPING_VERSION,'inference':INFERENCE_VERSION,'prompt':PROMPT_VERSION,'context':CONTEXT_SELECTION_VERSION,'normalization':SKILL_NORMALIZATION_VERSION}});continue
   now=datetime.now(timezone.utc).isoformat(); status='failed_validation'; hard=[];soft=[]; raw={}; usage={'input_tokens':None,'output_tokens':None,'total_tokens':None,'estimated_cost':None}
   try:
    request_attempts+=1
    response=call(p,model); responses_received+=1; successful_responses+=1; usage=extract_usage(response)
    raw_text=extract_response_text(response)
    try: raw=json.loads(raw_text)
    except json.JSONDecodeError as error: raise StructuredOutputError('response output was not valid JSON') from error
    raw_path=root/(f'raw_model_outputs_{model}.jsonl' if model!=MODEL else 'raw_model_outputs.jsonl')
    with raw_path.open('a',encoding='utf-8') as raw_file: raw_file.write(json.dumps({'job_group_id':row['job_group_id'],'model':model,'inference_version':INFERENCE_VERSION,'prompt_version':PROMPT_VERSION,'output':raw},ensure_ascii=False)+'\n')
    raw,status,hard,soft=parse_and_validate_response({'output_text':json.dumps(raw,ensure_ascii=False)})
   except Exception as error:
    status='failed_validation'; raw={'error_type':type(error).__name__}
    diagnostic=classify_exception(error, request_stage='inference_request', validation_stage='response_validation', response_received=isinstance(error,(StructuredOutputError,SchemaValidationError,json.JSONDecodeError)))
   else: diagnostic=None
   run_id=str(uuid.uuid4())
   with db:
    if not diagnostic_mode:
     db.execute('INSERT INTO skill_inference_runs (run_id,job_group_id,grouping_version,inference_version,input_fingerprint,prompt_version,model,context_selection_version,skill_normalization_version,inference_status,created_at,completed_at,input_tokens,output_tokens,total_tokens,estimated_cost) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(run_id,row['job_group_id'],GROUPING_VERSION,INFERENCE_VERSION,fp,PROMPT_VERSION,model,CONTEXT_SELECTION_VERSION,SKILL_NORMALIZATION_VERSION,status,now,now,usage['input_tokens'],usage['output_tokens'],usage['total_tokens'],usage['estimated_cost']))
     db.executemany('INSERT INTO inferred_skills (inferred_skill_id,run_id,raw_skill_name,normalized_skill_name,skill_type,confidence,source_type,evidence_level,reasoning_summary,skill_scope) VALUES (?,?,?,?,?,?,?,?,?,?)',[(str(uuid.uuid4()),run_id,s['raw_skill_name'],s['normalized_skill_name'],s['skill_type'],s['confidence'],s['source_type'],s['evidence_level'],s['reasoning_summary'],s['skill_scope']) for s in hard+soft])
    if diagnostic:
     db.execute('INSERT INTO skill_inference_diagnostics (diagnostic_id,run_id,job_group_id,inference_version,error_category,diagnostic_json,created_at,model,exception_type,http_status,openai_error_code,request_stage,validation_stage,response_received,retryable,sanitized_message) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),run_id,row['job_group_id'],INFERENCE_VERSION,diagnostic['error_category'],json.dumps(diagnostic,ensure_ascii=False),now,diagnostic['model'],diagnostic['exception_type'],diagnostic['http_status_code'],diagnostic['api_error_code'],diagnostic['request_stage'],diagnostic['validation_stage'],int(diagnostic['response_received']),int(diagnostic['retryable']),diagnostic['message']))
   result={'job_group_id':row['job_group_id'],'representative_title':row['representative_title'],'cache_hit':False,'inference_status':status,'hard_skills':hard,'soft_skills':soft,'model':model,'input_fingerprint':fp,'usage':usage,'versions':{'grouping':GROUPING_VERSION,'inference':INFERENCE_VERSION,'prompt':PROMPT_VERSION,'context':CONTEXT_SELECTION_VERSION,'normalization':SKILL_NORMALIZATION_VERSION}}
   if diagnostic: result['diagnostic']=diagnostic
   out.append(result)
 finally: pass
 if diagnostic_mode:
  diag=db.execute('SELECT diagnostic_json FROM skill_inference_diagnostics WHERE job_group_id=? ORDER BY created_at DESC LIMIT 1',(rows[0]['job_group_id'],)).fetchone()
  persisted_diagnostic=json.loads(diag[0]) if diag else None
 else: persisted_diagnostic=None
 db.close()
 if not diagnostic_mode: (root/'pilot_50_results.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in out)+'\n',encoding='utf-8')
 skills=[s for x in out for s in x.get('hard_skills',[])+x.get('soft_skills',[])]
 usage_rows=[x.get('usage',{}) for x in out]
 summary={'group_count':len(out),'api_request_attempts':request_attempts,'api_responses_received':responses_received,'api_successful_responses':successful_responses,'repair_retry_attempts':repair_retry_attempts,'api_calls':successful_responses,'model':model,'status_counts':dict(Counter(x['inference_status'] for x in out)),'total_hard_skills':sum(len(x.get('hard_skills',[])) for x in out),'total_soft_skills':sum(len(x.get('soft_skills',[])) for x in out),'confidence_counts':dict(Counter(s['confidence'] for s in skills)),'evidence_level_counts':dict(Counter(s['evidence_level'] for s in skills)),'scope_counts':dict(Counter(s['skill_scope'] for s in skills)),'raw_unique_skills':len({s['raw_skill_name'] for s in skills}),'normalized_unique_skills':len({s['normalized_skill_name'] for s in skills}),'groups_with_zero_skills':sum(not x.get('hard_skills') and not x.get('soft_skills') for x in out),'total_input_tokens':sum(x['input_tokens'] or 0 for x in usage_rows),'total_output_tokens':sum(x['output_tokens'] or 0 for x in usage_rows),'total_tokens':sum(x['total_tokens'] or 0 for x in usage_rows),'estimated_cost':None}
 if not diagnostic_mode:
  formal=db=sqlite3.connect('data/processed/recruitment_snapshots.sqlite')
  try:
   formal_rows=formal.execute('SELECT inference_status,input_tokens,output_tokens,total_tokens FROM skill_inference_runs WHERE prompt_version=?',(PROMPT_VERSION,)).fetchall()
   summary['api_request_attempts']=len(formal_rows); summary['api_responses_received']=len(formal_rows); summary['api_successful_responses']=len(formal_rows); summary['api_calls']=len(formal_rows)
  finally: formal.close()
 if diagnostic_mode:
  if persisted_diagnostic: summary['diagnostic']=persisted_diagnostic
 if not diagnostic_mode: (root/'pilot_50_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':
 parser=argparse.ArgumentParser(); parser.add_argument('--single-group-id', default=None, help='安全单组诊断模式；最多一个组、一次请求')
 parser.add_argument('--model', default=MODEL)
 args=parser.parse_args(); main(args.single_group_id,args.model)
