import json, os, sys, random, hashlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from run_deepseek_name_classification_trial_v1 import read_dotenv,api_post_retry,canonical_base_url,output_content,usage_summary,estimate_cost
from sno_v31_mapping_contract import validate
CAT=ROOT/'data/taxonomy/sno_v3_1/sno_occupation_catalog_v3.1.json'; REG=ROOT/'data/processed/record_role_classification_v1/name_registry/standard_occupation_to_original_names_final_deterministic_v4.json'; A=ROOT/'data/processed/record_role_classification_v1/api_trials'; O=A/'deepseek_sno_v31_reasonable_primary_new200'; SEED=2026101303; B=20; RB=10; LIMIT=1.0
def L(p):return json.loads(p.read_text(encoding='utf8'))
def W(p,x):
 p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():return
 t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(t,p)
def lev(c):
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
def prompt(t):return '''只依据标题及目录做职业“合理主归属”。不需要唯一答案：只要主归属有标题依据且符合范围即可 mapped，其他合理位置可列 candidate_category_ids，不因存在歧义而 review。先职能、再最直接二级、最后仅在有直接细分证据时三级；无三级依据落二级。可用职业名称通常含义及专业常识，不能虚构职责或场景。管培/培训/储备/助理为身份修饰，已明确职能仍归专业目录。完全无职能线索才 review；明确职业无目录范围才 taxonomy_gap。multi_role、non_role_text 保留原状态且不拆分。只输出 JSON：{"results":[{"occupation_id":string,"status":"mapped|review|taxonomy_gap|multi_role|non_role_text","target_category_id":string|null,"target_level":"level_2|level_3"|null,"candidate_category_ids":[],"title_evidence":string,"level_3_evidence":string|null,"reason":string}]}。mapped 只有一个正式 target；review 候选不能是 target；三级需直接证据。目录：'''+json.dumps(t,ensure_ascii=False,separators=(',',':'))
def rprompt(t):return '''独立 AI 复核已有“合理主归属”。不要求唯一答案：当前归属有标题依据且符合目录范围即 pass，即使还有其他合理位置。只有明显违反范围、忽略更直接专门类别或三级过细才 correction_required；完全无法确认处理是否合理才 unresolved；目录真实缺项/冲突才 taxonomy_issue。合理 review、multi_role、non_role_text 也可 pass。输出 JSON {"records":[{"occupation_id":string,"verdict":"pass|correction_required|unresolved|taxonomy_issue","suggested_target_category_id":string|null,"issue":string}]}。目录：'''+json.dumps(t,ensure_ascii=False,separators=(',',':'))
def compact(t):return [{"level_1_id":a['level_1_id'],"name":a['name'],"level_2":[{"level_2_id":b['level_2_id'],"name":b['name'],"scope":b.get('scope')} for b in a['level_2']]} for a in t]
def post(kind,n,body,base,key,batch,levels,ret):
 p=O/f'{kind}_{n:03d}_parsed.json';rawp=O/f'{kind}_{n:03d}_raw_response.json';req=O/f'{kind}_{n:03d}_request.json'
 if p.exists():return L(p)
 W(req,{"version":"sno-v3.1-reasonable-primary-v1","body_without_key":body,"catalog_sha256":hashlib.sha256(CAT.read_bytes()).hexdigest()})
 if rawp.exists():raw=L(rawp);attempt=0
 else:raw,attempt=api_post_retry(base,key,body);W(rawp,raw)
 x=json.loads(output_content(raw)); keyn='records' if kind=='review' else 'results'; rows=[norm(v) for v in x[keyn]]
 if {v.get('occupation_id') for v in rows}!={v['occupation_id'] for v in batch} or len(rows)!=len(batch):raise ValueError('output completeness')
 fail=[]
 if kind=='map':
  for v in rows:
   try:validate({'sample_id':v['occupation_id'],**{k:v[k] for k in ('status','target_category_id','candidate_category_ids','target_level','reason','level_3_evidence')}},levels,ret)
   except Exception as e:fail.append({'occupation_id':v['occupation_id'],'error':str(e)})
  if fail:raise ValueError(fail)
 at=datetime.fromtimestamp(raw['created'],timezone.utc) if isinstance(raw.get('created'),(int,float)) else datetime.now(timezone.utc);z={'raw_response_file':rawp.name,'results':rows,'usage':usage_summary(raw),'cost':estimate_cost(usage_summary(raw),at),'attempts':attempt,'normalization':'only nullable empty strings to null'};W(p,z);return z
def main():
 O.mkdir(parents=True,exist_ok=True);lock=O/'.lock'
 try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.close(fd)
 except FileExistsError:raise RuntimeError('writer lock exists')
 try:
  c=L(CAT); levels=lev(c);ret=set(c['retired_category_ids']); excluded=set();sources=[]
  prior=[A/'sno_v31_200_selection.json',A/'deepseek_sno_v3_directory_trial_100_v2_independent_selection.json',A/'deepseek_sno_v3_directory_trial_100_v2_fixed'/'selection_manifest.json']
  for p in prior:
   try:
    j=L(p); arr=j.get('occupations',[])
    for x in arr:
     name=x.get('standard_name') or x.get('occupation_name');
     if name:excluded.add(name)
    sources.append(str(p))
   except Exception:pass
  pool=[x for x in L(REG)['occupations'] if x['standard_name'] not in excluded]; random.Random(SEED).shuffle(pool);seen=set();sel=[]
  for x in pool:
   if x['standard_name'] not in seen:sel.append({'occupation_id':x['standard_occupation_id'],'title':x['standard_name']});seen.add(x['standard_name'])
   if len(sel)==200:break
  if len(sel)!=200:raise ValueError('insufficient pool')
  W(O/'selection.json',{'seed':SEED,'source':str(REG),'source_count':len(L(REG)['occupations']),'excluded_title_count':len(excluded),'remaining_title_pool':len(pool),'sample_count':200,'excluded_sources':sources,'occupations':sel})
  dot=read_dotenv(ROOT/'.env');key=os.getenv('DEEPSEEK_API_KEY') or dot.get('DEEPSEEK_API_KEY') or os.getenv('OPENAI_API_KEY') or dot.get('OPENAI_API_KEY');base=canonical_base_url(os.getenv('DEEPSEEK_BASE_URL') or dot.get('DEEPSEEK_BASE_URL') or 'https://api.deepseek.com');model=os.getenv('DEEPSEEK_MODEL') or dot.get('DEEPSEEK_MODEL') or 'deepseek-flash'; maps=[]
  for i in range(0,200,B):
   b=sel[i:i+B];body={'model':model,'messages':[{'role':'system','content':prompt(c['taxonomy'])},{'role':'user','content':json.dumps({'occupations':b},ensure_ascii=False)}],'temperature':0,'max_tokens':6000,'response_format':{'type':'json_object'},'thinking':{'type':'disabled'}};maps+=post('map',i//B+1,body,base,key,b,levels,ret)['results']
  by={x['occupation_id']:x for x in maps};reviews=[];ct=compact(c['taxonomy'])
  for i in range(0,200,RB):
   b=sel[i:i+RB];items=[{'occupation_id':x['occupation_id'],'title':x['title'],'current':by[x['occupation_id']]} for x in b];body={'model':model,'messages':[{'role':'system','content':rprompt(ct)},{'role':'user','content':json.dumps({'records':items},ensure_ascii=False)}],'temperature':0,'max_tokens':4000,'response_format':{'type':'json_object'},'thinking':{'type':'disabled'}};reviews+=post('review',i//RB+1,body,base,key,b,levels,ret)['results']
  rb={x['occupation_id']:x for x in reviews};rows=[{'occupation_id':x['occupation_id'],'title':x['title'],'initial':by[x['occupation_id']],'ai_reasonableness_review':rb[x['occupation_id']]} for x in sel];W(O/'review_all.json',{'count':200,'records':rows});u=Counter();cost=0
  for p in list(O.glob('map_*_parsed.json'))+list(O.glob('review_*_parsed.json')):
   z=L(p);u.update(z['usage']);cost+=z['cost']['estimated_usd']
  m=Counter(x['status'] for x in maps);rv=Counter(x['verdict'] for x in reviews);mapped=m['mapped'];passed_m=sum(1 for x in maps if x['status']=='mapped' and rb[x['occupation_id']]['verdict']=='pass');report={'sample_count':200,'initial_status_counts':dict(m),'initial_mapping_rate':mapped/200,'mapped_reasonableness_pass':{'numerator':passed_m,'denominator':mapped,'rate':passed_m/mapped if mapped else None},'overall_processing_pass':{'numerator':rv['pass'],'denominator':200,'rate':rv['pass']/200},'review_counts':dict(rv),'level_counts':dict(Counter(x['target_level'] or 'none' for x in maps)),'structural_validation':{'valid':200,'failed':0},'usage':dict(u),'estimated_cost_usd':cost,'budget_usd':LIMIT,'goal':{'overall_pass_target':190,'mapped_pass_rate_target':.95,'overall_reached':rv['pass']>=190,'mapped_rate_reached':passed_m/mapped>=.95 if mapped else False},'note':'AI reasonable-primary review, not human gold-standard accuracy.'};W(O/'report.json',report);print(json.dumps(report,ensure_ascii=False))
 finally:lock.unlink(missing_ok=True)
if __name__=='__main__':main()
