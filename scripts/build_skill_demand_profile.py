"""Build the frozen selective-mini-1000 deterministic Skill Demand Profile; no API calls."""
from __future__ import annotations
import json, math
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
import networkx as nx
import community as community_louvain
from app.domain.skills.normalization_v2 import SKILL_NORMALIZATION_VERSION, normalize_skill_v2

ROOT=Path('data/processed/skill_inference_v2/selective_mini_1000')
OUT=Path('data/processed/skill_demand_profile')
REPORT=Path('docs/reports/skill-demand-profile.md')
MAX_SUPPORT_IDS=20; PMI_MIN_GROUP_SUPPORT=5; PMI_MIN_PAIR_SUPPORT=5
def read_jsonl(path): return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x]
def bounded(counter,n=MAX_SUPPORT_IDS): return [x for x,_ in sorted(counter.items(),key=lambda x:(-x[1],x[0]))[:n]]
def profile(rows, group_meta):
 """Weighted skill frequency with bounded job-group traceability."""
 acc={}
 for row in rows:
  meta=group_meta[row['job_group_id']]; weight=meta['weight']; gid=row['job_group_id']
  for category, skills in (('hard',row.get('hard_skills',[])),('soft',row.get('soft_skills',[]))):
   seen=set()
   for skill in skills:
    name,_=normalize_skill_v2(skill['raw_skill_name'])
    key=(name,category,skill.get('skill_scope','occupation_core'))
    if key in seen: continue
    seen.add(key)
    item=acc.setdefault(key,{'skill_name':name,'skill_type':category,'skill_scope':key[2],'weighted_evidence_count':0,'supporting_job_group_count':0,'supporting_recruitment_record_count':0,'supporting_job_groups':Counter(),'domains':Counter(),'canonical_occupations':Counter(),'confidence':Counter(),'evidence_levels':Counter()})
    item['weighted_evidence_count']+=weight;item['supporting_job_group_count']+=1;item['supporting_recruitment_record_count']+=len(meta['record_ids']);item['supporting_job_groups'][gid]+=weight;item['domains'][meta['domain']]+=weight
    if meta['occupation']:item['canonical_occupations'][meta['occupation']]+=weight
    item['confidence'][skill.get('confidence')]+=1;item['evidence_levels'][skill.get('evidence_level')]+=1
 out=[]
 for item in acc.values():
  for field in ('supporting_job_groups','domains','canonical_occupations','confidence','evidence_levels'): item[field]=dict(item[field])
  item['representative_job_group_ids']=bounded(Counter(item['supporting_job_groups']))
  item['representative_domains']=bounded(Counter(item['domains']),5)
  item['representative_canonical_occupations']=bounded(Counter(item['canonical_occupations']),5)
  out.append(item)
 return sorted(out,key=lambda x:(-x['weighted_evidence_count'],-x['supporting_job_group_count'],x['skill_name']))
def main():
 results=read_jsonl(ROOT/'results.jsonl'); selected=read_jsonl(ROOT/'selected_inputs.jsonl')
 if len(results)!=1000 or len({r['job_group_id'] for r in results})!=1000: raise ValueError('requires completed frozen 1,000-group results')
 selected_by_id={r['job_group_id']:r for r in selected}
 rows=[r for r in results if r['inference_status']=='completed']
 meta={}
 for r in selected:
  p=r['prepared_inference_input'];meta[r['job_group_id']]={'weight':int(r.get('occurrence_count') or r.get('member_count') or 1),'record_ids':set(r.get('source_recruitment_record_ids') or []),'domain':r.get('industry_domain_context') or 'unknown','occupation':p.get('canonical_occupation_title') if r.get('mapped') else None}
 all_freq=profile(rows,meta)
 hard=[x for x in all_freq if x['skill_type']=='hard'];soft=[x for x in all_freq if x['skill_type']=='soft']
 by_domain=defaultdict(list);by_occ=defaultdict(list)
 for r in rows:
  by_domain[meta[r['job_group_id']]['domain']].append(r)
  if meta[r['job_group_id']]['occupation']:by_occ[meta[r['job_group_id']]['occupation']].append(r)
 domain_profiles={'overall':{'skill_frequency':all_freq},'domains':{d:{'analyzed_groups':len(rs),'skill_frequency':profile(rs,meta)} for d,rs in sorted(by_domain.items())},'canonical_occupations':{o:{'analyzed_groups':len(rs),'skill_frequency':profile(rs,meta)} for o,rs in sorted(by_occ.items())}}
 # PMI uses group-level presence, while edge evidence weight preserves recruitment evidence weight.
 skill_groups=defaultdict(set); pair_groups=defaultdict(set);pair_weight=Counter();pair_domains=defaultdict(Counter)
 for r in rows:
  gid=r['job_group_id']; names=sorted({normalize_skill_v2(s['raw_skill_name'])[0] for s in r.get('hard_skills',[])+r.get('soft_skills',[])})
  for n in names:skill_groups[n].add(gid)
  for a,b in combinations(names,2):
   key=(a,b);pair_groups[key].add(gid);pair_weight[key]+=meta[gid]['weight'];pair_domains[key][meta[gid]['domain']]+=meta[gid]['weight']
 n_groups=len(rows); relationships=[]
 for (a,b), gids in pair_groups.items():
  support=len(gids)
  if support<PMI_MIN_PAIR_SUPPORT or len(skill_groups[a])<PMI_MIN_GROUP_SUPPORT or len(skill_groups[b])<PMI_MIN_GROUP_SUPPORT:continue
  pmi=math.log2((support*n_groups)/(len(skill_groups[a])*len(skill_groups[b])))
  if pmi<=0:continue
  relationships.append({'skill_a':a,'skill_b':b,'pmi':round(pmi,6),'supporting_job_group_count':support,'weighted_evidence_count':pair_weight[(a,b)],'representative_job_group_ids':sorted(gids)[:MAX_SUPPORT_IDS],'representative_domains':bounded(pair_domains[(a,b)],5)})
 relationships.sort(key=lambda x:(-x['pmi'],-x['supporting_job_group_count'],-x['weighted_evidence_count'],x['skill_a'],x['skill_b']))
 graph=nx.Graph()
 for rel in relationships: graph.add_edge(rel['skill_a'],rel['skill_b'],weight=rel['weighted_evidence_count'],pmi=rel['pmi'],support=rel['supporting_job_group_count'])
 partition=community_louvain.best_partition(graph,weight='weight',random_state=42) if graph.nodes else {}
 buckets=defaultdict(list)
 for skill,cid in partition.items():buckets[cid].append(skill)
 communities=[]
 for cid,members in buckets.items():
  edge_count=graph.subgraph(members).number_of_edges(); communities.append({'community_id':f'community-{cid}','member_skills':sorted(members),'skill_count':len(members),'internal_edge_count':edge_count,'total_weighted_edge_evidence':sum(data['weight'] for _,_,data in graph.subgraph(members).edges(data=True))})
 communities.sort(key=lambda x:(-x['skill_count'],-x['internal_edge_count'],x['community_id']))
 provenance={'source':'selective-mini-1000 completed inference results','model':'gpt-4.1-mini','inference_version':'skill-inference-v2','prompt_version':'job-group-skill-inference-prompt-v6','normalization_version':SKILL_NORMALIZATION_VERSION,'evidence_note':'All skills are candidate skills inferred from Job Group context; frequency and network statistics are deterministic aggregations, not LLM-generated market facts.','analyzed_completed_groups':len(rows),'selected_groups':len(results)}
 demand={'provenance':provenance,'overall_frequency':{'all':all_freq,'hard':hard,'soft':soft},'cooccurrence_parameters':{'pmi_min_group_support':PMI_MIN_GROUP_SUPPORT,'pmi_min_pair_support':PMI_MIN_PAIR_SUPPORT,'pmi_requires_positive_value':True,'pmi_group_count':n_groups},'skill_communities':communities,'traceability_policy':{'max_representative_job_group_ids':MAX_SUPPORT_IDS,'frequency_weight':'underlying atomic-unit/occurrence count','relationship_weight':'sum of underlying occurrence weights within co-occurring groups'}}
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/'skill_frequency.json').write_text(json.dumps({'provenance':provenance,'all':all_freq,'hard':hard,'soft':soft},ensure_ascii=False,indent=2),encoding='utf-8')
 (OUT/'skill_cooccurrence_pmi.json').write_text(json.dumps({'parameters':demand['cooccurrence_parameters'],'relationships':relationships},ensure_ascii=False,indent=2),encoding='utf-8')
 (OUT/'skill_communities.json').write_text(json.dumps({'parameters':demand['cooccurrence_parameters'],'communities':communities},ensure_ascii=False,indent=2),encoding='utf-8')
 (OUT/'domain_skill_profiles.json').write_text(json.dumps(domain_profiles,ensure_ascii=False,indent=2),encoding='utf-8')
 (OUT/'skill_demand_profile.json').write_text(json.dumps(demand,ensure_ascii=False,indent=2),encoding='utf-8')
 top_h=[(x['skill_name'],x['weighted_evidence_count']) for x in hard[:10]];top_s=[(x['skill_name'],x['weighted_evidence_count']) for x in soft[:10]]
 report=['# 2026 Recruitment Skill Demand Profile','',json.dumps(provenance,ensure_ascii=False,indent=2),'',f'- Skill occurrences: {sum(x["supporting_job_group_count"] for x in all_freq):,}','- Unique normalized skills: '+str(len({x['skill_name'] for x in all_freq})),'- PMI relationships: '+str(len(relationships)),'- Louvain communities: '+str(len(communities)),'', '## Top hard skills','']+[f'- {n}: {w}' for n,w in top_h]+['','## Top soft skills','']+[f'- {n}: {w}' for n,w in top_s]+['','## Strongest PMI relationships','']+[f'- {x["skill_a"]} ↔ {x["skill_b"]}: PMI {x["pmi"]}, group support {x["supporting_job_group_count"]}' for x in relationships[:15]]
 REPORT.parent.mkdir(parents=True,exist_ok=True);REPORT.write_text('\n'.join(report)+'\n',encoding='utf-8')
 print(json.dumps({'api_calls':0,'analyzed_groups':len(rows),'skill_occurrences':sum(x['supporting_job_group_count'] for x in all_freq),'unique_normalized_skills':len({x['skill_name'] for x in all_freq}),'pmi_relationships':len(relationships),'communities':len(communities),'domain_profiles':len(by_domain),'top_hard':top_h[:5],'top_soft':top_s[:5]},ensure_ascii=False))
if __name__=='__main__':main()
