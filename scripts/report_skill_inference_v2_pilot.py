"""Deterministic reporting for the existing 50-group Skill Inference v2 pilot."""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path

root=Path('data/processed/skill_inference_v2')
inputs={x['job_group_id']:x for x in (json.loads(line) for line in (root/'pilot_50_inputs.jsonl').read_text(encoding='utf-8').splitlines() if line)}
results=[json.loads(line) for line in (root/'pilot_50_results.jsonl').read_text(encoding='utf-8').splitlines() if line]
summary=json.loads((root/'pilot_50_summary.json').read_text(encoding='utf-8'))
enriched=[]
for result in results:
 source=inputs[result['job_group_id']]
 enriched.append({**result,'context_quality':source['context_quality'],'mapped':source['mapped'],'member_count':source['member_count'],'industry_domain_context':source['industry_domain_context']})

# Deterministic, diverse review sample: one per key stratum followed by stable order.
strata={}; review=[]
for row in sorted(enriched,key=lambda x:(x['context_quality'],not x['mapped'],-x['member_count'],x['job_group_id'])):
 key=(row['context_quality'],row['mapped'],row['member_count']>1,row['inference_status'])
 if key not in strata: strata[key]=True; review.append(row)
for row in sorted(enriched,key=lambda x:x['job_group_id']):
 if len(review)>=25: break
 if row not in review: review.append(row)
(root/'pilot_50_human_review.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in review)+'\n',encoding='utf-8')

skills=[skill for row in enriched for skill in row.get('hard_skills',[])+row.get('soft_skills',[])]
freq=Counter(x['normalized_skill_name'] for x in skills)
soft_freq=Counter(x['normalized_skill_name'] for x in skills if x['skill_type']=='soft')
flags={
 'normalization_collisions': [],
 'suspected_semantic_duplicates': [],
 'generic_soft_skill_repetition': [name for name,count in soft_freq.items() if count>=max(3,len(enriched)//3)],
 'suspicious_over_specific_skills': [],
 'possible_hallucination_cases': [],
 'empty_or_near_empty_results': [x['job_group_id'] for x in enriched if not x.get('hard_skills') and not x.get('soft_skills')],
}
finance=[x for x in enriched if '财务专员' in x['representative_title']]
report=['# Skill Inference v2 Pilot','',f"- Groups: {summary['group_count']}",f"- API attempts / successful responses: {summary['api_request_attempts']} / {summary['api_successful_responses']}",f"- Statuses: {summary['status_counts']}",f"- Tokens (input / output / total): {summary['total_input_tokens']} / {summary['total_output_tokens']} / {summary['total_tokens']}",'- Estimated cost: unavailable (no project pricing configuration).','', '## Skills','',f"- Hard / soft: {summary['total_hard_skills']} / {summary['total_soft_skills']}",f"- Raw / normalized unique: {summary['raw_unique_skills']} / {summary['normalized_unique_skills']}",f"- Confidence: {summary['confidence_counts']}",f"- Scope: {summary['scope_counts']}",f"- Evidence: {summary['evidence_level_counts']}",f"- Most frequent normalized skills: {freq.most_common(15)}",'', '## Quality flags','',json.dumps(flags,ensure_ascii=False,indent=2),'','## 财务专员跨行业','',json.dumps(finance,ensure_ascii=False,indent=2)]
Path('docs/reports').mkdir(parents=True,exist_ok=True)
Path('docs/reports/skill-inference-v2-pilot.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
print(json.dumps({'human_review_count':len(review),'financial_specialist_groups':len(finance),'top_skills':freq.most_common(10)},ensure_ascii=False))
