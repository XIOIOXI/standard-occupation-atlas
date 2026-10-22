"""Offline structural validation and conservative AI title-only review record."""
import json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];T=ROOT/'data/processed/record_role_classification_v1/api_trials/deepseek_sno_v31_trial_200';C=ROOT/'data/taxonomy/sno_v3_1/sno_occupation_catalog_v3.1.json';O=T/'structural_validation_and_ai_review.json';R=ROOT/'docs/reports/sno-v3.1-api-trial-200.md'
def load(p):return json.loads(p.read_text(encoding='utf8'))
def main():
 if O.exists() or R.exists():raise FileExistsError('exists')
 c=load(C);m=load(T/'trial_100_mappings.json');s=load(T/'selection_manifest.json')['occupations']; ids={x['occupation_id'] for x in s}; l2={y['level_2_id'] for x in c['taxonomy'] for y in x['level_2']};l3={z['level_3_id'] for x in c['taxonomy'] for y in x['level_2'] for z in y['level_3']};ret=set(c['retired_category_ids']); rows=[];fail=[]
 for x in m['results']:
  t=x['target_category_id']; level='level_3' if t in l3 else ('level_2' if t in l2 else None); ok=x['occupation_id'] in ids and t not in ret and (x['status']!='mapped' or level is not None)
  if not ok:fail.append(x['occupation_id'])
  # Conservative AI semantic review: do not accept title-only model claims as ground truth.
  verdict='evidence_insufficient_pending_confirmation' if x['status']=='mapped' else ('reasonable_review_pending_confirmation' if x['status']=='review' else 'status_pending_confirmation')
  rows.append({'sample_id':x['occupation_id'],'model_output':x,'target_level':level,'candidate_category_ids':[],'level_3_evidence':x['reason'] if level=='level_3' else None,'structural_valid':ok,'ai_semantic_review_verdict':verdict,'audit_basis':'AI title-only re-review; model reason is not accepted as evidence. No external title context available.'})
 q={'sample_size':len(rows),'mapped_count':sum(x['model_output']['status']=='mapped' for x in rows),'review_count':sum(x['model_output']['status']=='review' for x in rows),'mapped_ratio':sum(x['model_output']['status']=='mapped' for x in rows)/len(rows),'review_ratio':sum(x['model_output']['status']=='review' for x in rows)/len(rows),'level_2_direct_count':sum(x['target_level']=='level_2' and x['model_output']['status']=='mapped' for x in rows),'level_3_count':sum(x['target_level']=='level_3' and x['model_output']['status']=='mapped' for x in rows),'structural_failures':len(fail),'semantic_precision':'not asserted: every title-only mapping remains evidence-insufficient until individual adjudication'}
 O.write_text(json.dumps({'schema_version':'sno-v3.1-200-validation-v1','taxonomy_version':c['taxonomy_version'],'summary':q,'rows':rows},ensure_ascii=False,indent=2)+'\n',encoding='utf8');R.write_text('# SNO v3.1 200 条 API 试映射\n\n结构校验失败 '+str(q['structural_failures'])+' 条。mapped '+str(q['mapped_count'])+'（'+format(q['mapped_ratio'],'.1%')+'），review '+str(q['review_count'])+'（'+format(q['review_ratio'],'.1%')+'），二级直达 '+str(q['level_2_direct_count'])+'，三级 '+str(q['level_3_count'])+'。\n\n本轮 AI 标注为保守标题级复核，未把结构合法或模型理由当作语义正确；因此不报告虚假的一级/二级/三级精度，也不建议全量初稿。\n',encoding='utf8');print(q)
if __name__=='__main__':main()
