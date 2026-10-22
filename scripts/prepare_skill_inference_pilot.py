"""Prepare exactly 50 bounded Job Group inference inputs; never calls an LLM."""
from __future__ import annotations
import argparse,hashlib,json,re
from collections import Counter,defaultdict
from pathlib import Path
from app.domain.skills.inference import JobGroupSkillInferenceInput
def stable(items):return sorted(items,key=lambda x:hashlib.sha256(x['job_group_id'].encode()).hexdigest())
def quality(g):
 t=g['representative_title']; generic=any(x in t for x in ['管理培训生','管培生','类','岗'])
 if generic and not g.get('canonical_occupation_id'):return 'low'
 if g.get('canonical_occupation_id') and g['occurrence_count']>1:return 'high'
 return 'medium' if g['occurrence_count']>1 or g.get('canonical_occupation_id') else 'low'
def make_input(g,members,taxver):
 ms=stable(members[g['job_group_id']])[:5]; majors=tuple(dict.fromkeys(m.get('major_requirement') for m in ms if m.get('major_requirement')))[:3]; loc=Counter(m['location'] for m in ms if m.get('location'))
 return JobGroupSkillInferenceInput(g['job_group_id'],g['representative_title'],g.get('canonical_occupation_id'),g.get('canonical_occupation_title'),g['industry_domain_context'],tuple(g['original_job_titles'][:10]),g['occurrence_count'],g['company_count'],g['location_count'],tuple(ms),majors,{},dict(loc.most_common(5)),g['grouping_version'],taxver,quality(g))
def main():
 p=argparse.ArgumentParser();p.add_argument('--groups',type=Path,required=True);p.add_argument('--members',type=Path,required=True);p.add_argument('--runtime-taxonomy',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--summary',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
 groups=[json.loads(x) for x in a.groups.read_text(encoding='utf-8').splitlines() if x];members=defaultdict(list)
 for x in a.members.read_text(encoding='utf-8').splitlines():
  if x: m=json.loads(x);members[m['job_group_id']].append(m)
 taxver=json.loads(a.runtime_taxonomy.read_text(encoding='utf-8'))['taxonomy_version']; chosen=[];seen=set()
 def take(predicate,n,reason):
  for g in stable([x for x in groups if predicate(x)]):
   if g['job_group_id'] not in seen and len(chosen)<50:chosen.append((g,reason));seen.add(g['job_group_id']);
   if sum(r==reason for _,r in chosen)>=n:break
 take(lambda g:g.get('canonical_occupation_id') and g['occurrence_count']>1,10,'mapped_multi_member')
 take(lambda g:not g.get('canonical_occupation_id') and g['occurrence_count']>1,10,'unmapped_multi_member')
 take(lambda g:g.get('canonical_occupation_id') and g['occurrence_count']==1,8,'mapped_singleton')
 take(lambda g:not g.get('canonical_occupation_id') and g['occurrence_count']==1,12,'unmapped_singleton')
 take(lambda g:'管理培训生' in g['representative_title'] or '管培生' in g['representative_title'],1,'management_trainee')
 take(lambda g:quality(g)=='low',5,'low_context')
 for g in stable(groups):
  if len(chosen)>=50:break
  if g['job_group_id'] not in seen:chosen.append((g,'deterministic_stratified_fill'));seen.add(g['job_group_id'])
 rows=[]
 for g,reason in chosen:
  i=make_input(g,members,taxver);rows.append({'job_group_id':g['job_group_id'],'representative_title':g['representative_title'],'selection_reasons':[reason],'mapped':bool(g.get('canonical_occupation_id')),'canonical_occupation':g.get('canonical_occupation_title'),'industry_domain':g['industry_domain_context'],'member_count':g['occurrence_count'],'context_quality':i.context_quality,'input_fingerprint':i.fingerprint(),'prepared_inference_input':i.__dict__})
 if len(rows)!=50 or len({x['job_group_id'] for x in rows})!=50:raise ValueError('Pilot must contain exactly 50 unique groups.')
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in rows)+'\n',encoding='utf-8')
 q=Counter(x['context_quality'] for x in rows);summary={'pilot_group_count':50,'mapped_count':sum(x['mapped'] for x in rows),'unmapped_count':sum(not x['mapped'] for x in rows),'singleton_count':sum(x['member_count']==1 for x in rows),'multi_member_count':sum(x['member_count']>1 for x in rows),'context_quality_counts':dict(q),'industry_context_count':len({x['industry_domain'] for x in rows}),'management_trainee_count':sum('管理培训生' in x['representative_title'] or '管培生' in x['representative_title'] for x in rows),'llm_called':False,'inference_results_generated':False}
 a.summary.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text('# Skill Inference Pipeline Design\n\nPrepared deterministic bounded inputs for 50 Job Groups. No LLM call or inference result was generated.\n',encoding='utf-8');print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
