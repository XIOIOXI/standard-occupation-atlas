"""Persist independent-holdout title-only audit; it is never used to tune v2."""
import json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
T=ROOT/'data/processed/record_role_classification_v1/api_trials/deepseek_sno_v3_directory_trial_100_v2_independent'
O=T/'semantic_audit_100.json'
R=ROOT/'docs/reports/deepseek-sno-v3-directory-trial-100-v2-independent.md'
E={
'SNO-99b44a86e716edad6fac':('overclassified','电芯材料未说明金属或无机材料，应停在材料研发二级。'),
'SNO-60cae4edd430125c7a31':('overclassified','小学教师未给学科，不能指定综合与通识三级。'),
'SNO-35ef17455687d998efb0':('incorrect_primary','助理兽医未说明伴侣或生产动物，不能指定伴侣动物诊疗。'),
'SNO-e36662a6eaca45f3fac2':('overclassified','GNSS算法未证明预测/统计学习，应停在算法研发二级。'),
'SNO-0b6325044ca8d02cb851':('incorrect_status','绿色金融管培仅有方向，未有具体金融职能，应 review。'),
'SNO-5d8c5bfcac72c1441ca3':('incorrect_primary','行政管培生已有行政方向，不能仅因管培归 L32。'),
'SNO-ca77ec470e0934289a16':('incorrect_primary','人力行政管培生已有职能，不能仅因管培归 L32。'),
'SNO-1c3d351e8249df3e98b0':('incorrect_primary','研发测试未说明软件，不能直接归软件测试。'),}
def load(p):return json.loads(p.read_text(encoding='utf8'))
def main():
 if O.exists() or R.exists():raise FileExistsError('audit exists')
 s=load(T/'selection_manifest.json')['occupations'];m={x['occupation_id']:x for x in load(T/'trial_100_mappings.json')['results']};rows=[]
 for x in s:
  e=E.get(x['occupation_id']);y=m[x['occupation_id']];rows.append({'sample_id':x['occupation_id'],'original_title':x['occupation_name'],'model_result':y,'audit_verdict':'correction_required' if e else 'accepted_title_only','audit_basis':e[1] if e else '标题证据支持状态与当前目录粒度。','error_type':e[0] if e else None,'used_for_prompt_tuning':False})
 mapped=[x for x in rows if x['model_result']['status']=='mapped'];errs=[x for x in rows if x['error_type']];me=[x for x in mapped if x['error_type']];q={'sample_size':100,'strict_title_only_accuracy':(100-len(errs))/100,'mapped_count':len(mapped),'mapped_primary_precision':(len(mapped)-len(me))/len(mapped),'status_counts':dict(Counter(x['model_result']['status'] for x in rows)),'error_counts':dict(Counter(x['error_type'] for x in errs)),'random_seed':20261013,'gate':'do_not_production_map_until_human_review_of_error_patterns'}
 O.write_text(json.dumps({'schema_version':'sno-v3-v2-independent-audit-v1','audit_order':'title-and-directory judgement before model comparison; no result feeds prompt changes','summary':q,'rows':rows},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 R.write_text(f'# SNO v3 第二轮独立留出验证\n\n随机种子 20261013；从 10,898 个非固定样本名称中无放回抽取 100 条。该留出样本未用于改 prompt。严格标题级正确率 {(100-len(errs))}/100（{q["strict_title_only_accuracy"]:.1%}），mapped 主归属精度 {len(mapped)-len(me)}/{len(mapped)}（{q["mapped_primary_precision"]:.1%}）。\n',encoding='utf8')
 print(json.dumps(q,ensure_ascii=False))
if __name__=='__main__':main()
