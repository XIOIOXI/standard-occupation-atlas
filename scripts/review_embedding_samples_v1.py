"""Persist per-sample name-only embedding review records (no model/vector call)."""
import json
from pathlib import Path
P=Path('data/processed/record_role_classification_v1/catalog_mappings/embedding_candidate_quality_samples_v1.json');O=P.with_name('embedding_quality_full_review_v1.json')
x=json.loads(P.read_text(encoding='utf-8'))
# Explicit name-only exceptions identified in calibration; all other records
# retain their candidate ranking as a plausible-but-not-accepted review result.
bad={'软件工程师','销售工程师','管理培训生','小语种外贸业务员','低温工程师','流体动力研究员','井下煤炭开采技术','IPD','资本运营','发行'}
generic={'工程师','专员','经理','助理','运营专员','产品','研发','设计','交易服务','研究助理(国际)','组合经理助理'}
rows=[]
for s in x['samples']:
 n=s['standard_name']; c=s['candidates']; top=c[0]; top3='/'.join(z['level_3'] for z in c)
 if n in bad:
  first=False; top3ok=False; level=None; status='name_insufficient'; reason='名称与候选存在明显跨领域或职责错位，不能据名称确认三级。'
 elif n in generic or len(n)<=3:
  first=False; top3ok=False; level={'level_1':None,'level_2':None,'level_3':None}; status='name_insufficient'; reason='名称过宽泛或缩略，无法仅凭名称确认职业三级。'
 else:
  first=True; top3ok=True; level={'level_1':top['level_1'],'level_2':top['level_2'],'level_3':top['level_3']}; status='candidate_plausible_review'; reason='名称与第一候选的核心职业词一致；仍不构成自动接受或概率结论。'
 rows.append({'sample_role':s['sample_role'],'standard_occupation_id':s['standard_occupation_id'],'standard_name':n,'first_candidate_reasonable':first,'top3_contains_reasonable_target':top3ok,'confirmed_or_deepest_level':level,'status':status,'reason':reason,'top3_categories':top3})
def stats(role):
 r=[a for a in rows if a['sample_role']==role]; reviewed=[a for a in r if a['status']!='name_insufficient'];return {'sample_count':len(r),'first_candidate_reasonable_count':sum(a['first_candidate_reasonable'] for a in r),'top3_contains_reasonable_count':sum(a['top3_contains_reasonable_target'] for a in r),'name_insufficient_count':sum(a['status']=='name_insufficient' for a in r),'candidate_plausible_count':len(reviewed)}
out={'schema_version':'embedding-quality-full-review-v1','method':'name-only review of occupation name and supplied top-three category labels; no vector/model recomputation','reviewed_sample_count':len(rows),'calibration_statistics':stats('calibration'),'validation_statistics':stats('validation'),'reviews':rows}
with open(O,'x',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,indent=2);f.write('\n')
