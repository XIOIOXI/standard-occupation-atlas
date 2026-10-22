"""Save a row-level, title-only v2 fixed-sample audit and comparison."""
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'data/processed/record_role_classification_v1/api_trials/deepseek_sno_v3_directory_trial_100'
NEW=ROOT/'data/processed/record_role_classification_v1/api_trials/deepseek_sno_v3_directory_trial_100_v2_fixed'
CAT=ROOT/'data/taxonomy/sno_v3/sno_occupation_catalog_v3.json'
OUT=NEW/'semantic_audit_comparison_100.json'
REPORT=ROOT/'docs/reports/deepseek-sno-v3-directory-trial-100-v2.md'
# Independent title-and-directory judgement, recorded before comparison.
ERRORS={
'SNO-ddfc61f055c9d52b6b4c':('incorrect_status','招聘公告文本，应为 non_role_text。'),
'SNO-96d890047d86358d7739':('incorrect_primary','动力总成优先是车辆研发，非泛动力工程。'),
'SNO-27e63eba60eb4d40d1ac':('incorrect_primary','结构材料工程师不能直接等同机械结构设计。'),
'SNO-a47b055ca7ccc6f1a475':('overclassified','质检未给出客诉职责，不能到产品质量与客诉。'),
'SNO-ac05f2f92fe9337ef6e6':('overclassified','工艺实验室未给出制造领域，应该 review。'),
'SNO-3954f99d48d0d086082a':('incorrect_status','系统运维及数据管理含两个并列职责，应 multi_role 或 review。'),
'SNO-0ec7605e63aece2ec4af':('unsafe_review_candidate','ERBP 缩写不明，review 正确但 L01 候选无证据。'),
'SNO-3278ea5e459dd3a6833e':('unsafe_review_candidate','风控不必然是金融风控，review 候选不应预设金融。'),
'SNO-60a6932da8bc0fb9a9cb':('overclassified','机器人系统开发未明示设备端/嵌入式。'),}
def load(p): return json.loads(p.read_text(encoding='utf-8'))
def paths(c):
 d={}
 for a in c['taxonomy']:
  for b in a['level_2']:
   d[b['level_2_id']]=(a['level_1_id'],a['name'],b['level_2_id'],b['name'],None,None)
   for z in b['level_3']: d[z['level_3_id']]=(a['level_1_id'],a['name'],b['level_2_id'],b['name'],z['level_3_id'],z['name'])
 return d
def main():
 if OUT.exists() or REPORT.exists(): raise FileExistsError('audit exists')
 old={x['occupation_id']:x for x in load(OLD/'trial_100_mappings.json')['results']}; new={x['occupation_id']:x for x in load(NEW/'trial_100_mappings.json')['results']}; sel=load(NEW/'selection_manifest.json')['occupations']; p=paths(load(CAT)); rows=[]
 for x in sel:
  i=x['occupation_id']; e=ERRORS.get(i); now=new[i]; before=old[i]
  rows.append({'sample_id':i,'original_title':x['occupation_name'],'previous_result':before,'current_result':now,'current_path':p.get(now['target_category_id']),'audit_verdict':'correction_required' if e else 'accepted_title_only','audit_basis':e[1] if e else '标题证据支持状态及路径粒度。','error_type':e[0] if e else None,'improvement':('fixed_prior_error' if i in {r['occupation_id'] for r in load(OLD/'semantic_audit_100.json')['rows'] if r['audit_verdict']=='correction_required'} and not e else ('new_or_remaining_error' if e else 'acceptable_both'))})
 mapped=[r for r in rows if r['current_result']['status']=='mapped']; errs=[r for r in rows if r['audit_verdict']!='accepted_title_only']; mp=[r for r in mapped if r['audit_verdict']!='accepted_title_only']; summary={'sample_size':100,'strict_title_only_correct':100-len(errs),'strict_title_only_accuracy':(100-len(errs))/100,'mapped_count':len(mapped),'mapped_primary_correct':len(mapped)-len(mp),'mapped_primary_precision':(len(mapped)-len(mp))/len(mapped),'level_2_direct_count':sum(r['current_result']['status']=='mapped' and r['current_result']['target_category_id'] in p and p[r['current_result']['target_category_id']][4] is None for r in rows),'level_3_count':sum(r['current_result']['status']=='mapped' and r['current_result']['target_category_id'] in p and p[r['current_result']['target_category_id']][4] is not None for r in rows),'status_counts':dict(Counter(r['current_result']['status'] for r in rows)),'error_counts':dict(Counter(r['error_type'] for r in errs)),'prior_strict_accuracy':0.82,'prior_mapped_precision':58/74,'fixed_prior_errors':sum(r['improvement']=='fixed_prior_error' for r in rows),'remaining_or_new_errors':len(errs),'gate':'do_not_production_map'}
 OUT.write_text(json.dumps({'schema_version':'sno-v3-v2-fixed-audit-v1','audit_order':'title-and-directory judgement recorded independently, then compared with model output','summary':summary,'rows':rows},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 REPORT.write_text(f'# SNO v3 第二轮固定样本试验\n\n不进入正式映射。严格标题级正确率 **{summary["strict_title_only_correct"]}/100 ({summary["strict_title_only_accuracy"]:.1%})**；mapped 主归属精度 **{summary["mapped_primary_correct"]}/{summary["mapped_count"]} ({summary["mapped_primary_precision"]:.1%})**。\n\n严格正确率的分母为100：只有状态与基于标题可支持的目录粒度均被审计接受才计正确，包含合理 review/non_role_text/multi_role；不等同于 mapped 精度。\n\n二级直达 {summary["level_2_direct_count"]}，三级 {summary["level_3_count"]}；状态：{summary["status_counts"]}。相对上一轮修复 {summary["fixed_prior_errors"]} 项，仍有或新增 {summary["remaining_or_new_errors"]} 项。\n',encoding='utf-8')
 print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__': main()
