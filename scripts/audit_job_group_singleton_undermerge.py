"""Read-only singleton under-merging audit for job-grouping-v1."""
from __future__ import annotations
import argparse, hashlib, json, re
from collections import defaultdict
from pathlib import Path
from app.domain.taxonomy.coverage import normalise_title

def safe_surface_key(title:str)->str:
    text=normalise_title(title)
    return re.sub(r'(?:岗位|岗)$','',text)
def possible_stem(title:str)->str:
    text=safe_surface_key(title)
    return re.sub(r'(?:开发工程师|工程师|专员|经理|助理)$','',text)
def sample(items:list[dict], count:int)->list[dict]:
    return sorted(items,key=lambda x:hashlib.sha256(('audit-v1|'+x['cluster_key']).encode()).hexdigest())[:count]
def view(groups:list[dict],kind:str,reason:str,key:str)->dict:
    return {'classification':kind,'cluster_key':key,'reason':reason,'group_count':len(groups),'source_group_ids':[g['job_group_id'] for g in groups],'titles':[g['representative_title'] for g in groups],'normalized_titles':[normalise_title(g['representative_title']) for g in groups],'industry_contexts':sorted({g['industry_domain_context'] for g in groups}),'canonical_occupation_ids':sorted({g['canonical_occupation_id'] for g in groups if g['canonical_occupation_id']}),'taxonomy_evidence':sorted({g['canonical_occupation_title'] for g in groups if g['canonical_occupation_title']})}
def main():
 p=argparse.ArgumentParser();p.add_argument('--groups',type=Path,required=True);p.add_argument('--summary',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--candidates',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
 groups=[json.loads(x) for x in a.groups.read_text(encoding='utf-8').splitlines() if x]; single=[g for g in groups if g['occurrence_count']==1]
 # Existing deterministic key should already make this zero; retain it as an explicit regression audit.
 canonical=defaultdict(list); strong=defaultdict(list); possible=defaultdict(list)
 for g in single:
  context=g['industry_domain_context']; oid=g.get('canonical_occupation_id')
  if oid: canonical[(oid,context)].append(g)
  if not oid: strong[(safe_surface_key(g['representative_title']),context)].append(g)
  possible[(possible_stem(g['representative_title']),context)].append(g)
 canonical_cases=[view(v,'strong_merge_candidate','same canonical occupation + same compatible industry context',f'canonical:{k[0]}|{k[1]}') for k,v in canonical.items() if len(v)>1]
 surface_cases=[view(v,'strong_merge_candidate','same unmapped title after only safe 岗/岗位 suffix normalization + same industry context',f'surface:{k[0]}|{k[1]}') for k,v in strong.items() if len(v)>1 and k[0]]
 strong_cases=canonical_cases+surface_cases; strong_ids={x for c in strong_cases for x in c['source_group_ids']}
 possible_cases=[]
 for k,v in possible.items():
  ids={g['job_group_id'] for g in v}
  if len(v)>1 and k[0] and not ids.issubset(strong_ids): possible_cases.append(view(v,'possible_merge_candidate','same conservative role-expression stem + same industry context, but no approved alias/canonical evidence',f'stem:{k[0]}|{k[1]}'))
 possible_ids={x for c in possible_cases for x in c['source_group_ids']}-strong_ids
 no_peer=len(single)-len(strong_ids)-len(possible_ids)
 # Strong clusters would each become one group; no change is applied.
 simulated=len(groups)-sum(c['group_count']-1 for c in strong_cases)
 unmapped_strong=sum(len(c['source_group_ids']) for c in strong_cases if not c['canonical_occupation_ids'])
 candidates=strong_cases+possible_cases
 no_peer_samples=[{'classification':'no_plausible_peer','cluster_key':'single:'+g['job_group_id'],'reason':'No same-industry safe-surface or conservative-stem peer was generated.','source_group_ids':[g['job_group_id']],'titles':[g['representative_title']],'normalized_titles':[normalise_title(g['representative_title'])],'industry_contexts':[g['industry_domain_context']],'canonical_occupation_ids':[g['canonical_occupation_id']] if g.get('canonical_occupation_id') else []} for g in sorted([g for g in single if g['job_group_id'] not in strong_ids|possible_ids],key=lambda x:hashlib.sha256(x['job_group_id'].encode()).hexdigest())[:100]]
 samples=[]
 for label,data in [('top_50_strong',sorted(strong_cases,key=lambda x:(-x['group_count'],x['cluster_key']))[:50]),('deterministic_100_strong',sample(strong_cases,100)),('deterministic_100_possible',sample(possible_cases,100)),('deterministic_100_no_peer',no_peer_samples)]:
  samples += [{'sample_set':label,**x} for x in data]
 result={'audit_version':'singleton-undermerge-audit-v1','grouping_version':'job-grouping-v1','singleton_count':len(single),'no_plausible_peer_count':no_peer,'strong_merge_candidate_singleton_count':len(strong_ids),'possible_merge_candidate_singleton_count':len(possible_ids),'strong_merge_candidate_cluster_count':len(strong_cases),'same_canonical_same_industry_singleton_count':sum(len(c['source_group_ids']) for c in canonical_cases),'unmapped_strong_singleton_count':unmapped_strong,'strong_merge_simulated_job_group_count':simulated,'candidate_generation':'same canonical+industry; safe 岗/岗位 surface key; conservative role-expression stem with same industry','conclusion':'C' if possible_cases else 'A','conclusion_reason':'Most candidate relationships require semantic identity judgment; strong deterministic cases are absent or negligible.' if possible_cases else 'No plausible under-merging signal was found.'}
 a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');a.candidates.write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in candidates+samples)+'\n',encoding='utf-8')
 lines=['# Job Grouping Singleton Under-merging Audit','',f"- Singleton groups: {len(single):,}",f"- No plausible peer: {no_peer:,}",f"- Strong candidate singleton groups / clusters: {len(strong_ids):,} / {len(strong_cases):,}",f"- Possible candidate singleton groups: {len(possible_ids):,}",f"- Same canonical + compatible industry still split: {result['same_canonical_same_industry_singleton_count']:,}",f"- Unmapped singleton strong candidates: {unmapped_strong:,}",f"- Strong-only simulated group count: {simulated:,} (baseline {len(groups):,})",'','## Interpretation','',result['conclusion_reason'],'','## Safety boundary','', 'Possible candidates are not merge recommendations. Protected specialisations such as software/hardware/AI testing, product manager/product engineer, data engineering/data science, algorithm/vision algorithm, and frontend/backend are not treated as strong evidence merely because they share tokens. No grouping output was changed.']
 a.report.write_text('\n'.join(lines)+'\n',encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
