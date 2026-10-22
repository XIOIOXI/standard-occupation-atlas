"""Contract-first v3.1 mapping + review; preserves raw provider artifacts."""
import json,os,sys,hashlib
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from run_deepseek_name_classification_trial_v1 import read_dotenv,api_post_retry,canonical_base_url,usage_summary,estimate_cost,exclusive_json,output_content,response_metadata
C=ROOT/'data/taxonomy/sno_v3_1/sno_occupation_catalog_v3.1.json';S=ROOT/'data/processed/record_role_classification_v1/api_trials/sno_v31_200_selection.json';O=ROOT/'data/processed/record_role_classification_v1/api_trials/deepseek_sno_v31_contract_200'; B=20
def load(p):return json.loads(p.read_text(encoding='utf8'))
def main():
 c=load(C);s=load(S)['occupations']; O.mkdir(parents=True,exist_ok=True); dot=read_dotenv(ROOT/'.env');key=os.getenv('DEEPSEEK_API_KEY') or dot.get('DEEPSEEK_API_KEY') or os.getenv('OPENAI_API_KEY') or dot.get('OPENAI_API_KEY');base=canonical_base_url(os.getenv('DEEPSEEK_BASE_URL') or dot.get('DEEPSEEK_BASE_URL') or 'https://api.deepseek.com');model=os.getenv('DEEPSEEK_MODEL') or dot.get('DEEPSEEK_MODEL') or 'deepseek-flash'
 directory=c['taxonomy']; rules='''只依据标题和目录；可理解标题明确的专业词、技术、语言、行业和对象，但不能补充未写出的职责或场景。先核心职能、再二级、最后三级。二级明确三级未知时 mapped 到二级。mapped 的 target 是唯一确定的二级或三级。review 的未确认候选仅放 candidate_category_ids；target 只能是确定公共父级或 null。三级必须有标题细分证据。输出 JSON results，每项严格包含 occupation_id,status,target_category_id,target_level,candidate_category_ids,title_evidence,level_3_evidence,reason。status 为 mapped|review|taxonomy_gap|multi_role|non_role_text。'''
 all=[];cost=[]
 for n,start in enumerate(range(0,200,B),1):
  final=O/f'map_{n:03d}_parsed.json'; batch=s[start:start+B]
  if final.exists(): z=load(final);all+=z['results'];cost.append(z['cost']);continue
  msgs=[{'role':'system','content':rules+'\n目录：'+json.dumps(directory,ensure_ascii=False,separators=(',',':'))},{'role':'user','content':json.dumps({'occupations':[{'occupation_id':x['standard_occupation_id'],'title':x['standard_name']} for x in batch]},ensure_ascii=False)}]; body={'model':model,'messages':msgs,'temperature':0,'max_tokens':5000,'response_format':{'type':'json_object'},'thinking':{'type':'disabled'}}; inp=O/f'map_{n:03d}_request.json';rawp=O/f'map_{n:03d}_raw_response.json';exclusive_json(inp,{'contract_version':'sno-v3.1-contract-v1','messages':msgs,'body_without_key':body,'catalog_sha256':hashlib.sha256(C.read_bytes()).hexdigest()}) if not inp.exists() else None
  obs=datetime.now(timezone.utc);raw=load(rawp) if rawp.exists() else api_post_retry(base,key,body)[0]
  if not rawp.exists():exclusive_json(rawp,raw)
  rows=json.loads(output_content(raw))['results']; usage=usage_summary(raw); co=estimate_cost(usage,obs);exclusive_json(final,{'raw_response_file':rawp.name,'results':rows,'usage':usage,'cost':co,'attempts':1,'post_processing':'none'}) ;all+=rows;cost.append(co)
 # No defaults: parsed output remains distinct from raw. Contract validation happens below.
 levels={x['level_1_id']:'level_1' for x in c['taxonomy']};levels.update({y['level_2_id']:'level_2' for x in c['taxonomy'] for y in x['level_2']});levels.update({z['level_3_id']:'level_3' for x in c['taxonomy'] for y in x['level_2'] for z in y['level_3']});ret=set(c['retired_category_ids']); valid=[];errors=[]
 for r in all:
  try:
   from sno_v31_mapping_contract import validate
   validate({'sample_id':r['occupation_id'],'status':r['status'],'target_category_id':r['target_category_id'],'candidate_category_ids':r['candidate_category_ids'],'target_level':r['target_level'],'reason':r['reason'],'level_3_evidence':r['level_3_evidence']},levels,ret);valid.append(r)
  except Exception as e:errors.append({'row':r,'error':str(e)})
 exclusive_json(O/'mapping_validation.json',{'input_count':200,'parsed_count':len(all),'valid_count':len(valid),'failures':errors,'post_processing_added_fields':0})
 print(json.dumps({'parsed':len(all),'valid':len(valid),'failures':len(errors),'cost':sum(x['estimated_usd'] for x in cost)},ensure_ascii=False))
if __name__=='__main__':main()
