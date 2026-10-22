"""Resumable SNO v3.1 full-draft executor. Real API is opt-in; simulate is offline."""
import argparse,hashlib,json,os,sys,time
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from sno_v31_mapping_contract import validate
from run_deepseek_name_classification_trial_v1 import read_dotenv,api_post_retry,canonical_base_url,usage_summary,estimate_cost,output_content
DATA=ROOT/'data/processed/record_role_classification_v1/record_roles.json';CAT=ROOT/'data/taxonomy/sno_v3_1/sno_occupation_catalog_v3.1.json';DEFAULT=ROOT/'data/processed/record_role_classification_v1/full_drafts/sno_v31_reasonable_primary_v3';PV='sno-v3.1-reasonable-primary-v3-full';BATCH=20;MAX_ATTEMPTS=2
def load(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,x,replace=False):
 p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists() and not replace:return
 t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(t,p)
def levels(c):
 d={}
 for a in c['taxonomy']:
  d[a['level_1_id']]='level_1'
  for b in a['level_2']:
   d[b['level_2_id']]='level_2'
   for z in b['level_3']:d[z['level_3_id']]='level_3'
 return d
def norm(x):
 x=dict(x)
 for k in ('target_category_id','target_level','level_3_evidence'):
  if isinstance(x.get(k),str) and not x[k].strip():x[k]=None
 return x
def mp(t):return '合理主归属：标题有依据且符合范围即可mapped，不需唯一答案；先职能、后最直接二级，仅直接细分证据才三级。不得虚构职责。输入项可包含context（公司、行业、原始组合岗位、地点、届次、批次）；仅在它能直接消除同名泛化岗位歧义时使用，不能据此编造职责。输出JSON results，每项 occupation_id,status(mapped|review|taxonomy_gap|multi_role|non_role_text),target_category_id(合法二三级或null),target_level(level_2|level_3|null),candidate_category_ids(合法数组),title_evidence,level_3_evidence(三级字符串否则null),reason。mapped一个正式目标；review候选不能当目标；其它非mapped目标=null；禁止停用ID。目录：'+json.dumps(t,ensure_ascii=False,separators=(',',':'))
def rp(t):return 'AI合理性复核JSON records：occupation_id,verdict(pass|correction_required|unresolved|taxonomy_issue),suggested_target_category_id,issue。合理主归属、二级直达、合理review/multi_role/non_role_text均可pass；不要求唯一答案。仅明显错分或三级过细修正。模型称ID不存在时程序查目录；合法ID只记录冲突，不覆盖。完整目录：'+json.dumps(t,ensure_ascii=False,separators=(',',':'))
def np():return '仅标题确认non_role_text，JSON results: original_record_id,decision(exclude_non_role|restore_title_and_map|hold),reason,recovered_title。无法确认hold；剔除不删除源记录。'
def xp():return '多岗位判别JSON results: original_record_id,case(A|B|C|D),child_titles(字符串数组),source_spans([{text,start,end}]),reason。仅A拆分；斜杠顿号多词不能单独证明A；Unicode start含end不含，切片必须等于text；B/C/D子岗位为空。'
def body(s,u):return {'model':'deepseek-flash','messages':[{'role':'system','content':s},{'role':'user','content':json.dumps(u,ensure_ascii=False)}],'response_format':{'type':'json_object'},'thinking':{'type':'disabled'},'temperature':0,'max_tokens':6000}
def childid(r,t,i):return 'CR-'+hashlib.sha256(f'{r}|{i}|{t}'.encode()).hexdigest()[:20]
def groups(roles):
 d={}
 for r in roles:d.setdefault(r['source_title'],[]).append(r['record_role_id'])
 allids=[i for v in d.values() for i in v]
 if len(allids)!=len(roles) or len(set(allids))!=len(roles):raise ValueError('group coverage')
 return [{'occupation_id':'TG-'+hashlib.sha256(t.encode()).hexdigest()[:20],'title':t,'record_role_ids':ids} for t,ids in d.items()]
def sim(stage,items):
 o=[]
 for x in items:
  title=x.get('title','');id=x.get('occupation_id') or x['original_record_id']
  if stage=='map':
   st='non_role_text' if title=='具体招聘岗位' else 'multi_role' if title=='岗位甲、岗位乙' else 'mapped' if '前端' in title else 'review'; target='L01-01' if st=='mapped' else None;o.append({'occupation_id':id,'status':st,'target_category_id':target,'target_level':'level_2' if target else None,'candidate_category_ids':[],'title_evidence':title,'level_3_evidence':None,'reason':'sim'})
  elif stage=='review':o.append({'occupation_id':id,'verdict':'pass','suggested_target_category_id':None,'issue':'sim'})
  elif stage=='non':o.append({'original_record_id':id,'decision':'exclude_non_role','reason':'sim','recovered_title':None})
  elif stage=='multi':
   case=x.get('case') or ('A' if title=='岗位甲、岗位乙' else 'D');o.append({'original_record_id':id,'case':case,'child_titles':['岗位甲','岗位乙'] if case=='A' else [],'source_spans':[{'text':'岗位甲','start':0,'end':3},{'text':'岗位乙','start':4,'end':7}] if case=='A' else [],'reason':'sim'})
 return o
class Engine:
 def __init__(self,O,c,a):
  self.O=O;self.c=c;self.a=a;self.lv=levels(c);self.ret=set(c['retired_category_ids']);self.ledger=O/'ledger.json';put(self.ledger,{'spent_usd':0,'reserved_usd':0,'responses':[]})
 def charge(self,stage,n,r):
  u=usage_summary(r);cost=estimate_cost(u,datetime.now(timezone.utc));led=load(self.ledger)
  if not any(x['stage']==stage and x['batch']==n for x in led['responses']):
   led['spent_usd']+=cost['estimated_usd'];led['responses'].append({'stage':stage,'batch':n,'cost':cost});tmp=self.ledger.with_suffix('.tmp');tmp.write_text(json.dumps(led,ensure_ascii=False,indent=2),encoding='utf8');os.replace(tmp,self.ledger)
  return u,cost
 def call(self,stage,n,req,items):
  p=self.O/stage/f'{n:06d}.parsed.json';raw=self.O/stage/f'{n:06d}.raw.json';request=self.O/stage/f'{n:06d}.request.json'
  if p.exists():return load(p)['results']
  led=load(self.ledger)
  reserve=0.02
  if led['spent_usd']+reserve>self.a.budget_usd:raise RuntimeError('budget_stop')
  put(request,{'prompt_version':PV,'body_without_key':req,'input_ids':[x.get('occupation_id') or x.get('original_record_id') for x in items]})
  if raw.exists():r=load(raw);attempts=0
  elif self.a.simulate:r={'created':0,'usage':{'prompt_tokens':0,'completion_tokens':0},'choices':[{'message':{'content':json.dumps({'results':sim(stage,items) if stage!='review' else sim('review',items),'records':sim('review',items)},ensure_ascii=False)}}]};attempts=0
  else:
   dot=read_dotenv(ROOT/'.env');key=os.getenv('DEEPSEEK_API_KEY') or dot.get('DEEPSEEK_API_KEY')
   if not key:raise RuntimeError('missing DEEPSEEK_API_KEY; refusing to send another provider\'s credential to DeepSeek')
   base=canonical_base_url(os.getenv('DEEPSEEK_BASE_URL') or dot.get('DEEPSEEK_BASE_URL') or 'https://api.deepseek.com');r,attempts=api_post_retry(base,key,req)
  # Persist and charge before parsing: a malformed envelope is still a billable
  # response, and a later resume must parse this exact raw payload rather than
  # issue it again.
  put(raw,r);u,cost=self.charge(stage,n,r);data=json.loads(output_content(r))
  expected_key='records' if stage=='review' else 'results'
  # The non-role/multi contracts request `results`, but tolerate the common
  # provider envelope alias `records`.  Keep the original raw response intact
  # and record the parser-level envelope repair separately.
  used_key=expected_key
  if expected_key not in data and stage in ('non','multi') and isinstance(data.get('records'),list):
   used_key='records'
  if not isinstance(data.get(used_key),list):
   failure={'stage':stage,'batch':n,'error':'missing_or_non_list_output_envelope','expected_key':expected_key,'available_keys':list(data) if isinstance(data,dict) else [],'raw_response_file':raw.name}
   put(self.O/'failed'/f'{stage}_{n:06d}.json',{'stage':stage,'batch':n,'failures':[failure],'action':'retain_raw_and_continue_without_reissue'})
   put(p,{'results':[],'raw_response_file':raw.name,'usage':u,'cost':cost,'attempts':attempts,'parser_failure':failure})
   return []
  rows=[norm(x) for x in data[used_key]]
  failures=[]
  if stage in ('map','child'):
   for x in rows:
    try:validate({'sample_id':x['occupation_id'],**{k:x[k] for k in ('status','target_category_id','candidate_category_ids','target_level','reason','level_3_evidence')}},self.lv,self.ret)
    except Exception as exc:failures.append({'occupation_id':x.get('occupation_id'),'error':str(exc),'raw_response_file':raw.name})
  if failures:
   put(self.O/'failed'/f'{stage}_{n:06d}.json',{'stage':stage,'batch':n,'failures':failures,'action':'retain_raw_and_continue_without_reissue'})
  put(p,{'results':rows,'raw_response_file':raw.name,'usage':u,'cost':cost,'attempts':attempts,'normalization':'nullable whitespace only','envelope_normalization':None if used_key==expected_key else {'from':used_key,'to':expected_key,'reason':'provider_envelope_alias'},'validation_failures':failures});return rows
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run',action='store_true');ap.add_argument('--simulate',action='store_true');ap.add_argument('--budget-usd',type=float,default=5);ap.add_argument('--output',default=str(DEFAULT));a=ap.parse_args();O=Path(a.output);O.mkdir(parents=True,exist_ok=True);lock=O/'.run.lock'
 if not a.run:raise SystemExit('Use --run --simulate for offline validation or --run for real API.')
 try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,json.dumps({'pid':os.getpid(),'started':time.time()}).encode());os.close(fd)
 except FileExistsError:raise SystemExit('writer lock exists')
 try:
  c=load(CAT);roles=load(DATA)['roles'];gs=groups(roles);manifest={'prompt_version':PV,'catalog_sha256':sha(CAT),'input_sha256':sha(DATA),'taxonomy_version':c['taxonomy_version'],'source_records':len(roles),'distinct_titles':len(gs),'budget_usd':a.budget_usd,'mode':'simulate' if a.simulate else 'real'};m=O/'manifest.json';
  if m.exists() and {k:load(m)[k] for k in ('prompt_version','catalog_sha256','input_sha256','mode')}!={k:manifest[k] for k in ('prompt_version','catalog_sha256','input_sha256','mode')}:raise RuntimeError('resume version/mode mismatch')
  put(m,manifest);put(O/'title_groups.json',{'count':len(gs),'groups':gs})
  sample=gs[0]; non_sample=next((x for x in gs if x['title']=='具体招聘岗位'),sample); multi_sample={'occupation_id':'TG-sample-multi','title':'岗位甲、岗位乙'}
  samples={'01_initial_mapping_request.json':body(mp(c['taxonomy']),{'occupations':[{'occupation_id':sample['occupation_id'],'title':sample['title']}]}),'02_reasonableness_review_request.json':body(rp(c['taxonomy']),{'records':[{'occupation_id':sample['occupation_id'],'title':sample['title'],'current':{'status':'mapped','target_category_id':'L01-01','target_level':'level_2','candidate_category_ids':[],'title_evidence':'sample','level_3_evidence':None,'reason':'sample'}}]}),'03_non_role_confirmation_request.json':body(np(),{'records':[{'original_record_id':non_sample['occupation_id'],'title':non_sample['title']}]}),'04_multi_role_decision_request.json':body(xp(),{'records':[{'original_record_id':multi_sample['occupation_id'],'title':multi_sample['title']}]}),'05_child_role_mapping_request.json':body(mp(c['taxonomy']),{'occupations':[{'occupation_id':childid('TG-sample-multi','岗位甲',0),'title':'岗位甲'}]})}
  for n,q in samples.items():put(O/'request_samples'/n,{'metadata':manifest,'body_without_key':q})
  e=Engine(O,c,a);maps=[]
  for i in range(0,len(gs),BATCH):maps+=e.call('map',i//BATCH+1,body(mp(c['taxonomy']),{'occupations':[{'occupation_id':x['occupation_id'],'title':x['title']} for x in gs[i:i+BATCH]]}),gs[i:i+BATCH])
  by={x['occupation_id']:x for x in maps};reviews=[]
  for i in range(0,len(gs),BATCH):
   q=gs[i:i+BATCH];reviews+=e.call('review',i//BATCH+1,body(rp(c['taxonomy']),{'records':[{'occupation_id':x['occupation_id'],'title':x['title'],'current':by[x['occupation_id']]} for x in q]}),q)
  non=[{'original_record_id':g['occupation_id'],'title':g['title']} for g in gs if by[g['occupation_id']]['status']=='non_role_text'];multi=[{'original_record_id':g['occupation_id'],'title':g['title']} for g in gs if by[g['occupation_id']]['status']=='multi_role'];nd=[];md=[]
  for i in range(0,len(non),BATCH):nd+=e.call('non',i//BATCH+1,body(np(),{'records':non[i:i+BATCH]}),non[i:i+BATCH])
  for i in range(0,len(multi),BATCH):md+=e.call('multi',i//BATCH+1,body(xp(),{'records':multi[i:i+BATCH]}),multi[i:i+BATCH])
  kids=[]
  for x in md:
   title=next(v['title'] for v in multi if v['original_record_id']==x['original_record_id'])
   if x['case']=='A':
    if len(x['child_titles'])!=len(x['source_spans']):
     put(O/'failed'/f"multi_spans_{x['original_record_id']}.json",{'stage':'multi','original_record_id':x['original_record_id'],'error':'child_title_and_source_span_count_mismatch','action':'hold_multi_role_without_child_expansion','raw_decision':x})
     continue
    group_kids=[];span_error=None
    for j,(t,s) in enumerate(zip(x['child_titles'],x['source_spans'])):
     if title[s['start']:s['end']]!=t or s['text']!=t:
      span_error={'stage':'multi','original_record_id':x['original_record_id'],'child_index':j,'error':'unicode_source_span_mismatch','action':'hold_multi_role_without_child_expansion','title':title,'child_title':t,'source_span':s,'raw_decision':x};break
     group_kids.append({'occupation_id':childid(x['original_record_id'],t,j),'title':t,'original_record_id':x['original_record_id'],'source_span':s,'quantity_policy':'never_copy_headcount'})
    if span_error:
     put(O/'failed'/f"multi_spans_{x['original_record_id']}_{span_error['child_index']}.json",span_error);continue
    kids+=group_kids
  child=[]
  for i in range(0,len(kids),BATCH):child+=e.call('child',i//BATCH+1,body(mp(c['taxonomy']),{'occupations':[{'occupation_id':x['occupation_id'],'title':x['title']} for x in kids[i:i+BATCH]]}),kids[i:i+BATCH])
  rb={x['occupation_id']:x for x in reviews};expanded=[];conflicts=[]
  # Failed mapping validation is never silently promoted to an eligible mapped
  # record.  Retain its raw initial result for audit, while exposing a distinct
  # processing state and hold eligibility in the final draft.
  failed_map_ids=set()
  for fp in (O/'failed').glob('map_*.json'):
   for f in load(fp).get('failures',[]):
    if f.get('occupation_id'):failed_map_ids.add(f['occupation_id'])
  held_multi_ids=set()
  for fp in (O/'failed').glob('multi_spans_*.json'):
   x=load(fp)
   if x.get('original_record_id'):held_multi_ids.add(x['original_record_id'])
  child_parent_ids={x['original_record_id'] for x in kids}
  for g in gs:
   initial=by[g['occupation_id']];review=rb[g['occupation_id']];effective=initial
   suggestion=review.get('suggested_target_category_id')
   if review.get('verdict')=='correction_required' and suggestion in e.lv:
    effective={**initial,'status':'mapped','target_category_id':suggestion,'target_level':e.lv[suggestion],'candidate_category_ids':[],'reason':review.get('issue','correction')}
   elif review.get('verdict')=='correction_required' and suggestion:
    conflicts.append({'occupation_id':g['occupation_id'],'suggestion':suggestion,'issue':review.get('issue'),'action':'retain_initial_invalid_suggestion'})
   processing_state='failed_mapping_validation' if g['occupation_id'] in failed_map_ids else ('hold_multi_source_span' if g['occupation_id'] in held_multi_ids else 'completed')
   for rid in g['record_role_ids']:expanded.append({'record_role_id':rid,'title_group_id':g['occupation_id'],'initial':initial,'review':review,'effective_result':effective,'processing_state':processing_state,'display_eligibility':'pending'})
  if len(expanded)!=len(roles) or len({x['record_role_id'] for x in expanded})!=len(roles):raise ValueError('backfill coverage')
  excluded={x['original_record_id'] for x in nd if x['decision']=='exclude_non_role'};held={x['original_record_id'] for x in nd if x['decision']=='hold'}
  for r in expanded:
   gid=r['title_group_id']
   r['display_eligibility']='excluded_non_role' if gid in excluded else ('hold_non_role' if gid in held else ('hold_mapping_validation_failure' if gid in failed_map_ids else ('hold_multi_source_span' if gid in held_multi_ids else ('replaced_by_child_roles' if gid in child_parent_ids else 'eligible'))))
  put(O/'final.json',{'records':expanded,'reviews':reviews,'review_conflicts':conflicts,'non_role_log':nd,'multi_log':md,'children':kids,'child_mappings':child,'statistics':{'source_records':len(roles),'distinct_titles':len(gs),'child_roles':len(kids),'mapped_title_groups':sum(x['status']=='mapped' for x in maps),'unclassified_title_groups':sum(x['status'] in ('review','taxonomy_gap') for x in maps),'excluded_non_role_title_groups':len(excluded),'failed_mapping_validation_title_groups':len(failed_map_ids),'failed_mapping_validation_source_records':sum(len(g['record_role_ids']) for g in gs if g['occupation_id'] in failed_map_ids),'held_multi_source_span_title_groups':len(held_multi_ids),'replaced_by_child_role_title_groups':len(child_parent_ids)}},replace=True)
 finally:lock.unlink(missing_ok=True)
if __name__=='__main__':main()
