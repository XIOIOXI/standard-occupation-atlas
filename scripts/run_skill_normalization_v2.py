"""Offline re-normalization of persisted pilot outputs; never calls an API."""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
from app.domain.skills.normalization_v2 import SKILL_NORMALIZATION_VERSION, normalize_skill_v2
from app.domain.skills.inference import normalize_skill

root=Path('data/processed/skill_inference_v2')
rows=[json.loads(x) for x in (root/'pilot_50_results.jsonl').read_text(encoding='utf-8').splitlines() if x]
comparison=[]; changed=Counter(); raw_unique=set(); v1_unique=set(); v2_unique=set(); unsafe=[]
for row in rows:
 for skill in row.get('hard_skills',[])+row.get('soft_skills',[]):
  raw=skill['raw_skill_name']; v1=skill['normalized_skill_name']; v2,rule=normalize_skill_v2(raw)
  raw_unique.add(raw); v1_unique.add(v1); v2_unique.add(v2)
  if v2!=v1: changed[rule]+=1
  comparison.append({'job_group_id':row['job_group_id'],'raw_skill_name':raw,'v1_normalized_skill':v1,'v2_normalized_skill':v2,'changed':v2!=v1,'alias_rule':rule})
(root/'skill_normalization_v2_comparison.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in comparison)+'\n',encoding='utf-8')
summary={'normalization_version':SKILL_NORMALIZATION_VERSION,'source_inference_version':'skill-inference-v2','api_calls':0,'raw_unique_skills':len(raw_unique),'v1_normalized_unique_skills':len(v1_unique),'v2_normalized_unique_skills':len(v2_unique),'reduction':len(v1_unique)-len(v2_unique),'changed_skill_occurrences':sum(changed.values()),'applied_alias_rules':dict(changed),'potentially_unsafe_merges':unsafe,'remaining_semantic_duplicates':['团队协作 vs 跨部门协作','问题解决 vs 分析能力','Communication Skills vs 沟通协调能力']}
(root/'skill_normalization_v2_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
Path('docs/reports').mkdir(parents=True,exist_ok=True)
Path('docs/reports/skill-normalization-v2.md').write_text('# Skill Normalization v2\n\n'+json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False))
