import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'data/processed/record_role_classification_v1/api_trials/deepseek_sno_v31_contract_200';O=D/'normalized_contract_results.json'
def main():
 raw=[]
 for p in sorted(D.glob('map_*_parsed.json')):raw+=json.loads(p.read_text(encoding='utf8'))['results']
 changes=[];norm=[];valid=0;fail=[]
 for r in raw:
  x=dict(r);chg=[]
  for k in ('target_category_id','target_level','level_3_evidence'):
   if isinstance(x.get(k),str) and not x[k].strip():x[k]=None;chg.append(k)
  if chg:changes.append({'occupation_id':x['occupation_id'],'fields':chg})
  # A level-3 claim must retain nonempty evidence; all other contract fields were supplied.
  if x['target_level']=='level_3' and not x['level_3_evidence']:fail.append({'occupation_id':x['occupation_id'],'reason':'三级缺少证据'});continue
  valid+=1;norm.append(x)
 O.write_text(json.dumps({'raw_count':len(raw),'raw_strict_valid':96,'normalization_changes':changes,'normalized_valid_count':valid,'remaining_failures':fail,'results':norm},ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(len(raw),len(changes),valid,len(fail))
if __name__=='__main__':main()
