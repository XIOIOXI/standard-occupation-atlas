"""Build the deterministic Curriculum Analysis MVP artifacts; no API or LLM."""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
from app.domain.curriculum.mapping import extract_curriculum_skills, curriculum_profile, coverage_status
from app.domain.skills.normalization_v2 import SKILL_NORMALIZATION_VERSION

PROGRAM=Path('data/demo/curriculum/demo_program.json')
MARKET=Path('data/processed/skill_demand_profile/skill_demand_profile.json')
OUT=Path('data/processed/curriculum'); REPORT=Path('docs/reports/curriculum-skill-mapping.md')
def main():
 program=json.loads(PROGRAM.read_text(encoding='utf-8'));market=json.loads(MARKET.read_text(encoding='utf-8'))
 freq=market['overall_frequency']['all']; market_skills={x['skill_name'] for x in freq}; index={(x['skill_name'],x['skill_type'],x['skill_scope']):x for x in freq}
 evidence=extract_curriculum_skills(program,market_skills);profile=curriculum_profile(evidence,index)
 course_profiles=[]
 for course in program['courses']:
  items=[x for x in evidence if x['course_id']==course['course_id']]
  course_profiles.append({'course_id':course['course_id'],'course_name':course['course_name'],'covered_skills':sorted({x['normalized_skill'] for x in items}),'evidence_count':len(items),'evidence':items})
 profile['course_profiles']=course_profiles
 evidence_by_skill={skill:[x for x in evidence if x['normalized_skill']==skill] for skill in market_skills}
 mapping=[]
 for row in freq:
  items=evidence_by_skill[row['skill_name']];status=coverage_status(items)
  mapping.append({'market_skill':row['skill_name'],'skill_type':row['skill_type'],'skill_scope':row['skill_scope'],'market_demand_weight':row['weighted_evidence_count'],'market_supporting_job_group_count':row['supporting_job_group_count'],'market_representative_job_group_ids':row['representative_job_group_ids'],'market_representative_domains':row['representative_domains'],'curriculum_coverage_status':status,'curriculum_evidence_count':len(items),'supporting_curriculum_evidence':items})
 mapping.sort(key=lambda x:(-x['market_demand_weight'],x['market_skill'],x['skill_type'],x['skill_scope']))
 counts=Counter(x['curriculum_coverage_status'] for x in mapping)
 hardsoft=Counter()
 for item in profile['covered_skills']:
  for category in item['market_categories']:hardsoft[category['skill_type']]+=1
 profile.update({'program_name':program['program_name'],'provenance':{'program_file':str(PROGRAM).replace('\\','/'),'content_status':program['provenance']['content_status'],'matching_policy':'exact normalized market-skill phrase matching plus approved skill-normalization-v2 aliases only','normalization_version':SKILL_NORMALIZATION_VERSION,'api_calls':0},'hard_soft_distribution':dict(hardsoft)})
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/'curriculum_skill_profile.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 (OUT/'market_curriculum_mapping.json').write_text(json.dumps({'provenance':profile['provenance'],'program_id':program['program_id'],'mapping':mapping,'status_counts':dict(counts)},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 report=['# Curriculum Skill Mapping MVP','',f'- Demo program: {program["program_name"]}','- Courses: '+str(len(program['courses'])),'- Curriculum skills with direct text evidence: '+str(len(profile['covered_skills'])),'- Market entries: '+str(len(mapping)),'- Coverage counts: '+json.dumps(dict(counts),ensure_ascii=False),'', '## Directly observed curriculum skills','']+[f'- {x["normalized_skill"]}: {x["evidence_count"]} curriculum evidence items across {", ".join(x["supporting_course_ids"])}' for x in profile['covered_skills']]+['','## Interpretation boundary','`not_observed` means that no approved deterministic phrase match was observed in this minimal demo text. It does not establish that the course does not teach the skill.']
 REPORT.parent.mkdir(parents=True,exist_ok=True);REPORT.write_text('\n'.join(report)+'\n',encoding='utf-8')
 print(json.dumps({'api_calls':0,'programs':1,'courses':len(program['courses']),'curriculum_skills':len(profile['covered_skills']),'coverage_status_counts':dict(counts),'hard_soft_distribution':dict(hardsoft)},ensure_ascii=False))
if __name__=='__main__':main()
