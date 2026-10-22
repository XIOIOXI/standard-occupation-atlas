import json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'));from run_deepseek_name_classification_trial_v1 import read_dotenv,api_post_retry,output_content,exclusive_json
D=ROOT/'data/processed/record_role_classification_v1/api_trials/deepseek_sno_v31_contract_200';C=ROOT/'data/taxonomy/sno_v3_1/sno_occupation_catalog_v3.1.json'
def main():
 d=json.loads((D/'normalized_contract_results.json').read_text(encoding='utf8'));sel={x['standard_occupation_id']:x['standard_name'] for x in json.loads((ROOT/'data/processed/record_role_classification_v1/api_trials/sno_v31_200_selection.json').read_text(encoding='utf8'))['occupations']};cat=json.loads(C.read_text(encoding='utf8'))['taxonomy'];dot=read_dotenv(ROOT/'.env');key=os.getenv('DEEPSEEK_API_KEY') or dot.get('DEEPSEEK_API_KEY') or os.getenv('OPENAI_API_KEY') or dot.get('OPENAI_API_KEY');out=[]
 for n in range(0,200,20):
  p=D/f'review_{n//20+1:03d}.json';batch=d['results'][n:n+20]
  if p.exists():out+=json.loads(p.read_text(encoding='utf8'))['results'];continue
  prompt='复核已有分类，不重做首次映射。检查是否明显错分、猜测标题外信息、三级过细或review本可落二级。可回查完整目录。输出JSON results，每项 occupation_id,verdict(pass|correction_required|unresolved|taxonomy_issue),suggested_target_category_id,issue。目录:'+json.dumps(cat,ensure_ascii=False,separators=(',',':'))
  items=[{'occupation_id':x['occupation_id'],'title':sel[x['occupation_id']],'current':x} for x in batch];body={'model':'deepseek-flash','messages':[{'role':'system','content':prompt},{'role':'user','content':json.dumps(items,ensure_ascii=False)}],'response_format':{'type':'json_object'},'temperature':0,'thinking':{'type':'disabled'}};raw=api_post_retry('https://api.deepseek.com',key,body)[0];res=json.loads(output_content(raw))['results'];exclusive_json(p,{'raw':raw,'results':res});out+=res
 exclusive_json(D/'review_all.json',{'count':len(out),'results':out})
if __name__=='__main__':main()
