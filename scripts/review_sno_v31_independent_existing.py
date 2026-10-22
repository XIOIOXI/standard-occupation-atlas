"""Re-review saved independent outputs against v3.1 without calling an API."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];T=ROOT/'data/processed/record_role_classification_v1/api_trials/deepseek_sno_v3_directory_trial_100_v2_independent'; OUT=T/'semantic_audit_100_v3.1.json'; REPORT=ROOT/'docs/reports/sno-v3.1-existing-independent-review.md'
def load(p):return json.loads(p.read_text(encoding='utf8'))
def main():
 if OUT.exists() or REPORT.exists():raise FileExistsError('exists')
 prior=load(T/'semantic_audit_100.json'); retired={'L13-02-01','L13-02-02'}; rows=[]
 for r in prior['rows']:
  model=r['model_result']; title=r['original_title']; compat='unchanged_compatible'; need=[]
  if model['target_category_id'] in retired: compat='requires_title_reclassification';need.append('销售方式停用，需按客户类型重判')
  if title in {'托福教研老师','江北分公司行李员','海外产品与解决方案工程师','功率半导体工程师','管理培训生(绿色金融方向)','农化管培生','服务管培生','软/硬件开发'}: need.append('v3.1重点人工语义复核：标题证据不足时保留争议')
  rows.append({**r,'old_directory_audit_verdict':r['audit_verdict'],'v3_1_compatibility':compat,'v3_1_recheck_note':'；'.join(need) or '目录局部修订未改变该路径；原审核结论保留，非重新调用模型。'})
 summary={'rows':len(rows),'old_rule_audit':'preserved in old_directory_audit_verdict','v3_1_compatible':sum(x['v3_1_compatibility']=='unchanged_compatible' for x in rows),'requires_reclassification':sum(x['v3_1_compatibility']!='unchanged_compatible' for x in rows),'evidence_insufficient_pending_confirmation':sum(bool(x['v3_1_recheck_note'].startswith('v3.1重点')) for x in rows)}
 OUT.write_text(json.dumps({'schema_version':'sno-v3.1-existing-output-review-v1','no_api_call':True,'summary':summary,'rows':rows},ensure_ascii=False,indent=2)+'\n',encoding='utf8'); REPORT.write_text('# SNO v3.1 既有独立样本复核\n\n旧模型输出及旧目录审核均保留。本轮只检查 v3.1 兼容性，不用新规则倒推旧模型错误。100 条中 '+str(summary['v3_1_compatible'])+' 条路径未受停用 ID 影响；'+str(summary['requires_reclassification'])+' 条需重判。重点标题保留证据不足争议，未编造唯一答案。\n',encoding='utf8');print(summary)
if __name__=='__main__':main()
