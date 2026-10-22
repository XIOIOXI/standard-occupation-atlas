"""Deterministically select 1,000 frozen v2 Job Groups; no API calls."""
from __future__ import annotations
import json, hashlib
from collections import Counter, defaultdict
from pathlib import Path
from app.domain.skills.inference import INFERENCE_VERSION, PROMPT_VERSION, CONTEXT_SELECTION_VERSION, SKILL_NORMALIZATION_VERSION
from prepare_skill_inference_v2_pilot import make_input, quality, VERSION

ROOT=Path('data/processed'); OUT=ROOT/'skill_inference_v2/selective_mini_1000'
GENERIC={'技术工程师','技术岗','综合专员','运营管理岗','研发助理','运营','产品','销售','管理岗','研发类','专业不限'}

def read_jsonl(p):
 return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x]
def generic(title):
 t=(title or '').strip()
 return len(t)<4 or t in GENERIC or any(x in t for x in ('管培生','培训生','招聘项目'))
def sort_key(g):
 return (-int(g.get('member_count') or 0),-int(g.get('occurrence_count') or 0),-int(g.get('company_count') or 0),not bool(g.get('canonical_occupation_id')),hashlib.sha256(g['job_group_id'].encode()).hexdigest())
def main():
 groups=read_jsonl(ROOT/'job_groups_v2/job_groups.jsonl'); members=defaultdict(list)
 for m in read_jsonl(ROOT/'job_groups_v2/job_group_members.jsonl'): members[m['job_group_id']].append(m)
 candidates=[g for g in groups if quality(g) in {'high','medium'} and not generic(g.get('representative_title'))]
 by_domain=defaultdict(list)
 for g in candidates: by_domain[g.get('industry_domain_context') or 'unknown'].append(g)
 chosen=[]; seen=set()
 # One strongest eligible group per represented domain, then evidence-weighted fill.
 for domain in sorted(by_domain):
  g=sorted(by_domain[domain],key=sort_key)[0]; chosen.append(g);seen.add(g['job_group_id'])
 for g in sorted((x for x in candidates if x['job_group_id'] not in seen),key=sort_key):
  if len(chosen)>=1000: break
  chosen.append(g);seen.add(g['job_group_id'])
 if len(chosen)!=1000 or len(seen)!=1000: raise ValueError(f'selection must be exactly 1000, got {len(chosen)}')
 rows=[]
 for g in chosen:
  i=make_input(g,members)
  rows.append({'job_group_id':g['job_group_id'],'grouping_version':VERSION,'representative_title':g['representative_title'],'selection_reason':'domain_representative_then_evidence_weighted','mapped':g.get('taxonomy_mapping_status')=='mapped','member_count':g['member_count'],'occurrence_count':g['occurrence_count'],'context_quality':i.context_quality,'industry_domain_context':g.get('industry_domain_context'),'source_recruitment_record_ids':g.get('source_recruitment_record_ids',[]),'source_atomic_unit_ids':g.get('source_atomic_unit_ids',[]),'input_fingerprint':i.fingerprint(),'prepared_inference_input':i.__dict__})
 atomic={x for r in rows for x in r['source_atomic_unit_ids']}; records={x for r in rows for x in r['source_recruitment_record_ids']}
 all_atomic={x for g in groups for x in g.get('source_atomic_unit_ids',[])}; all_records={x for g in groups for x in g.get('source_recruitment_record_ids',[])}
 summary={'selection_name':'selective-mini-1000','selection_version':'selective-mini-1000-v1','selection_rules':['exclude deterministic low-context groups','exclude deterministic generic/program-like titles','one best eligible group per industry/domain','evidence-weighted fill: member_count, occurrence_count, company_count, mapped status, stable ID'],'selected_group_count':len(rows),'eligible_candidate_count':len(candidates),'atomic_units_covered':len(atomic),'atomic_unit_coverage_pct':round(100*len(atomic)/len(all_atomic),2),'recruitment_records_covered':len(records),'recruitment_record_coverage_pct':round(100*len(records)/len(all_records),2),'context_quality_counts':dict(Counter(r['context_quality'] for r in rows)),'singleton_multi_counts':{'singleton':sum(r['member_count']==1 for r in rows),'multi':sum(r['member_count']>1 for r in rows)},'mapped_unmapped_counts':{'mapped':sum(r['mapped'] for r in rows),'unmapped':sum(not r['mapped'] for r in rows)},'industry_domain_distribution':dict(Counter(r['industry_domain_context'] for r in rows).most_common()),'versions':{'grouping':VERSION,'taxonomy':'mvp-taxonomy-v4.1-frozen','inference':INFERENCE_VERSION,'prompt':PROMPT_VERSION,'context':CONTEXT_SELECTION_VERSION,'normalization':'skill-normalization-v2','model':'gpt-4.1-mini'},'api_calls':0}
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/'selected_inputs.jsonl').write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in rows)+'\n',encoding='utf-8')
 (OUT/'selection_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__': main()
