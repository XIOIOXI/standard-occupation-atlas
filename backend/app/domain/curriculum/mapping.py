"""Conservative curriculum-to-market skill matching; no semantic inference."""
from __future__ import annotations
import re
from collections import defaultdict
from app.domain.skills.normalization_v2 import ALIASES_V2, normalize_skill_v2

def _text_key(value: str) -> str:
    return re.sub(r'\s+', ' ', value).strip().casefold()

def extract_curriculum_skills(program: dict, market_skills: set[str]) -> list[dict]:
    """Exact canonical skill phrase matches plus the approved v2 aliases only."""
    aliases={_text_key(raw):canonical for raw,canonical in ALIASES_V2.items() if canonical in market_skills}
    candidates={_text_key(skill):skill for skill in market_skills}
    candidates.update(aliases)
    evidence=[]
    for course in program['courses']:
        fields=[('course_description',course.get('description',''))]
        fields += [('learning_outcome',item) for item in course.get('learning_outcomes',[])]
        fields += [('assessment',item) for item in course.get('assessments',[])]
        for source_field,text in fields:
            normalized=_text_key(text)
            for phrase,canonical in candidates.items():
                if phrase and phrase in normalized:
                    evidence.append({'program_id':program['program_id'],'course_id':course['course_id'],'source_field':source_field,'matched_text':text,'matched_phrase':phrase,'normalized_skill':canonical,'match_method':'exact_normalized_match' if phrase==_text_key(canonical) else 'approved_v2_alias_match'})
    return evidence

def coverage_status(evidence: list[dict]) -> str:
    """Covered needs breadth or repeated explicit evidence; absence is not a teaching claim."""
    if not evidence:return 'not_observed'
    if len({x['course_id'] for x in evidence}) >= 2 or len(evidence) >= 3:return 'covered'
    return 'partially_covered'

def curriculum_profile(evidence: list[dict], market_index: dict[tuple[str,str,str],dict]) -> dict:
    grouped=defaultdict(list)
    for item in evidence:grouped[item['normalized_skill']].append(item)
    skills=[]
    for skill,items in grouped.items():
        categories={(x['skill_type'],x['skill_scope']) for x in market_index.values() if x['skill_name']==skill}
        skills.append({'normalized_skill':skill,'evidence_count':len(items),'supporting_course_ids':sorted({x['course_id'] for x in items}),'supporting_learning_outcomes':[x['matched_text'] for x in items if x['source_field']=='learning_outcome'],'evidence':items,'market_categories':[{'skill_type':t,'skill_scope':s} for t,s in sorted(categories)]})
    return {'program_id':evidence[0]['program_id'] if evidence else None,'covered_skills':sorted(skills,key=lambda x:(-x['evidence_count'],x['normalized_skill'])),'evidence_count':len(evidence)}
