"""Prepare exactly 50 bounded v2 Job Group inputs; this script never calls an LLM."""
from __future__ import annotations
import argparse, hashlib, json
from collections import Counter, defaultdict
from pathlib import Path
from app.domain.skills.inference import JobGroupSkillInferenceInput, INFERENCE_VERSION, PROMPT_VERSION, CONTEXT_SELECTION_VERSION, SKILL_NORMALIZATION_VERSION

VERSION='job-grouping-v2-occupation-safe'; MODEL='gpt-4.1-mini'
def stable(rows): return sorted(rows,key=lambda x:hashlib.sha256(x['job_group_id'].encode()).hexdigest())
def quality(g):
 if g['member_count']>3 and g.get('canonical_occupation_id'): return 'high'
 if g['member_count']>1 or g.get('canonical_occupation_id'): return 'medium'
 return 'low'
def make_input(g,members):
 ms=stable(members[g['job_group_id']])[:5]
 majors=tuple(dict.fromkeys(x.get('major_requirement') for x in ms if x.get('major_requirement')))[:3]
 loc=Counter(x.get('location') for x in ms if x.get('location'))
 return JobGroupSkillInferenceInput(g['job_group_id'],g['representative_title'],g.get('canonical_occupation_id'),g.get('canonical_occupation_title'),g['industry_domain_context'],tuple(g['original_job_titles'][:10]),g['occurrence_count'],g['company_count'],g['location_count'],tuple(ms),majors,g.get('company_distribution',{}),dict(loc.most_common(5)),VERSION,'mvp-taxonomy-v4.1-frozen',quality(g))
def main():
 p=argparse.ArgumentParser();p.add_argument('--groups',type=Path,required=True);p.add_argument('--members',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
 groups=[json.loads(x) for x in a.groups.read_text(encoding='utf-8').splitlines() if x]
 if any(g['grouping_version']!=VERSION for g in groups):raise ValueError('Only v2 Job Groups may enter this pilot.')
 members=defaultdict(list)
 for x in a.members.read_text(encoding='utf-8').splitlines():
  if x:
   m=json.loads(x);members[m['job_group_id']].append(m)
 chosen=[];seen=set()
 def take(predicate,n,label):
  for g in stable([x for x in groups if predicate(x)]):
   if g['job_group_id'] not in seen and len(chosen)<50: chosen.append((g,label));seen.add(g['job_group_id'])
   if sum(l==label for _,l in chosen)>=n:break
 take(lambda g:g['taxonomy_mapping_status']=='mapped' and g['member_count']>1,8,'mapped_multi')
 take(lambda g:g['taxonomy_mapping_status']=='unmapped' and g['member_count']>1,12,'unmapped_multi')
 take(lambda g:g['taxonomy_mapping_status']=='mapped' and g['member_count']==1,7,'mapped_singleton')
 take(lambda g:g['taxonomy_mapping_status']=='unmapped' and g['member_count']==1,13,'unmapped_singleton')
 take(lambda g:any(x in g['representative_title'] for x in ('财务','销售','运营','人力','教育','法务')),5,'non_technical')
 take(lambda g:any(x in g['representative_title'] for x in ('算法','软件','硬件','技术支持','AI','工程师')),5,'technical')
 for g in stable(groups):
  if len(chosen)>=50:break
  if g['job_group_id'] not in seen:chosen.append((g,'stratified_fill'));seen.add(g['job_group_id'])
 rows=[]
 for g,label in chosen:
  i=make_input(g,members);rows.append({'job_group_id':g['job_group_id'],'grouping_version':VERSION,'representative_title':g['representative_title'],'selection_reason':label,'mapped':g['taxonomy_mapping_status']=='mapped','member_count':g['member_count'],'context_quality':i.context_quality,'industry_domain_context':g['industry_domain_context'],'input_fingerprint':i.fingerprint(),'prepared_inference_input':i.__dict__})
 if len(rows)!=50 or len({x['job_group_id'] for x in rows})!=50:raise ValueError('Pilot must have exactly 50 unique v2 groups')
 a.output_dir.mkdir(parents=True,exist_ok=True)
 (a.output_dir/'pilot_50_inputs.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in rows)+'\n',encoding='utf-8')
 summary={'grouping_version':VERSION,'pilot_group_count':50,'mapped_count':sum(x['mapped'] for x in rows),'unmapped_count':sum(not x['mapped'] for x in rows),'singleton_count':sum(x['member_count']==1 for x in rows),'multi_member_count':sum(x['member_count']>1 for x in rows),'context_quality_counts':dict(Counter(x['context_quality'] for x in rows)),'industry_domain_count':len({x['industry_domain_context'] for x in rows}),'inference_version':INFERENCE_VERSION,'prompt_version':PROMPT_VERSION,'context_selection_version':CONTEXT_SELECTION_VERSION,'skill_normalization_version':SKILL_NORMALIZATION_VERSION,'selected_model':MODEL,'maximum_api_calls':50,'maximum_validation_retries':50,'execution_state':'ready_no_api_key_required_for_preparation','v1_pilot_status':'stale_superseded_do_not_execute'}
 (a.output_dir/'pilot_50_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
