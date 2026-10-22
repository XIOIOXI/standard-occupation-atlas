"""Offline v2 normalization and report for completed selective mini inference."""
import json
from collections import Counter
from pathlib import Path
from app.domain.skills.normalization_v2 import normalize_skill_v2, SKILL_NORMALIZATION_VERSION

ROOT=Path('data/processed/skill_inference_v2/selective_mini_1000')
def main():
 selection=json.loads((ROOT/'selection_summary.json').read_text(encoding='utf-8'))
 rows=[json.loads(x) for x in (ROOT/'results.jsonl').read_text(encoding='utf-8').splitlines() if x]
 if len(rows)!=1000 or len({x['job_group_id'] for x in rows})!=1000: raise SystemExit('cannot finalize incomplete selection')
 comp=[];v2=set();raw=set();rules=Counter()
 for row in rows:
  for skill in row.get('hard_skills',[])+row.get('soft_skills',[]):
   norm,rule=normalize_skill_v2(skill['raw_skill_name']);raw.add(skill['raw_skill_name']);v2.add(norm)
   if rule:rules[rule]+=1
   comp.append({'job_group_id':row['job_group_id'],'raw_skill_name':skill['raw_skill_name'],'v1_normalized_skill':skill['normalized_skill_name'],'v2_normalized_skill':norm,'changed':norm!=skill['normalized_skill_name'],'alias_rule':rule})
 (ROOT/'normalization_v2_comparison.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in comp)+'\n',encoding='utf-8')
 summary=json.loads((ROOT/'inference_summary.json').read_text(encoding='utf-8'))
 summary.update({'raw_unique_skills':len(raw),'normalized_v2_unique_skills':len(v2),'skill_normalization_version':SKILL_NORMALIZATION_VERSION,'normalization_v2_changed_occurrences':sum(x['changed'] for x in comp),'normalization_v2_alias_rules':dict(rules),'atomic_unit_coverage_pct':selection['atomic_unit_coverage_pct'],'recruitment_record_coverage_pct':selection['recruitment_record_coverage_pct']})
 (ROOT/'final_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 report=['# Selective Skill Inference — Mini 1,000','',json.dumps(summary,ensure_ascii=False,indent=2),'','## Selection','',json.dumps({k:selection[k] for k in ('selected_group_count','atomic_units_covered','atomic_unit_coverage_pct','recruitment_records_covered','recruitment_record_coverage_pct','context_quality_counts','singleton_multi_counts','mapped_unmapped_counts')},ensure_ascii=False,indent=2)]
 Path('docs/reports').mkdir(parents=True,exist_ok=True);Path('docs/reports/selective-skill-inference-mini-1000.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
 print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
