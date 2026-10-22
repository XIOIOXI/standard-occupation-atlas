"""Deterministic, capped structural curriculum gap candidates; no API or recommendation generation."""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
from app.domain.curriculum.gaps import relevance, priority

IN=Path('data/processed/curriculum/market_curriculum_mapping.json'); OUT=Path('data/processed/curriculum/curriculum_gap_analysis.json'); REPORT=Path('docs/reports/curriculum-gap-analysis.md')
def main():
 source=json.loads(IN.read_text(encoding='utf-8')); pool=[]
 observed_surface_keys={(item['market_skill'].casefold(),item['skill_type'],item['skill_scope']) for item in source['mapping'] if item['curriculum_coverage_status'] in {'covered','partially_covered'}}
 for item in source['mapping']:
  if item['curriculum_coverage_status'] not in {'not_observed','partially_covered'}:continue
  if item['curriculum_coverage_status']=='not_observed' and (item['market_skill'].casefold(),item['skill_type'],item['skill_scope']) in observed_surface_keys:continue
  rel,rel_codes=relevance(item['market_skill'],item['skill_type'],item.get('market_representative_domains',[]))
  level,codes=priority(rel,item['curriculum_coverage_status'],item['market_demand_weight'],item['market_supporting_job_group_count'])
  # A relevance-tested candidate needs either direct IT/domain evidence or a transferable soft-skill signal.
  if rel=='low' or item['market_demand_weight']<5:continue
  pool.append({
   'normalized_skill':item['market_skill'],'skill_type':item['skill_type'],'skill_scope':item['skill_scope'],
   'market_demand_weight':item['market_demand_weight'],'curriculum_status':item['curriculum_coverage_status'],
   'program_relevance':rel,'priority':level,
   'market_evidence_summary':{'supporting_job_group_count':item['market_supporting_job_group_count'],'representative_job_group_ids':item['market_representative_job_group_ids'],'representative_domains':item['market_representative_domains']},
   'curriculum_evidence_summary':{'evidence_count':item['curriculum_evidence_count'],'evidence':item['supporting_curriculum_evidence']},
   'reason_codes':sorted(set(rel_codes+codes+(['occupation_core'] if item['skill_scope']=='occupation_core' else ['domain_specific'])))
  })
 pool.sort(key=lambda x:({'high':0,'medium':1,'low':2}[x['priority']],-x['market_demand_weight'],-x['market_evidence_summary']['supporting_job_group_count'],x['normalized_skill'],x['skill_type'],x['skill_scope']))
 highs=[x for x in pool if x['priority']=='high'][:10]; mediums=[x for x in pool if x['priority']=='medium'][:10]; final=highs+mediums
 counts=Counter(x['priority'] for x in pool)
 result={'provenance':{'source_mapping':str(IN).replace('\\','/'),'api_calls':0,'analysis_type':'deterministic structural curriculum gap candidate selection','interpretation_boundary':'not_observed means no frozen curriculum-text evidence was observed; it is not confirmation of curriculum absence.'},'input_mapping_entries':len(source['mapping']),'relevance_tested_candidate_count_before_final_cap':len(pool),'priority_counts':dict(counts),'final_actionable_candidates':final,'final_cap':{'high':10,'medium':10,'selected_high':len(highs),'selected_medium':len(mediums)}}
 OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 lines=['# Structural Curriculum Gap Analysis MVP','',json.dumps(result['provenance'],ensure_ascii=False,indent=2),'',f'- Input mapping entries: {len(source["mapping"])}','- Relevance-tested candidates before final cap: '+str(len(pool)),'- Priority counts: '+json.dumps(dict(counts),ensure_ascii=False),'', '## Final actionable candidates','']
 for x in final:lines.append(f'- [{x["priority"]}] {x["normalized_skill"]} ({x["skill_type"]}, {x["skill_scope"]}) — market weight {x["market_demand_weight"]}; curriculum status {x["curriculum_status"]}; codes: {", ".join(x["reason_codes"])}')
 REPORT.parent.mkdir(parents=True,exist_ok=True);REPORT.write_text('\n'.join(lines)+'\n',encoding='utf-8')
 print(json.dumps({'api_calls':0,'input_mapping_entries':len(source['mapping']),'candidate_pool':len(pool),'priority_counts':dict(counts),'final_candidates':len(final),'top_high':[x['normalized_skill'] for x in highs]},ensure_ascii=False))
if __name__=='__main__':main()
