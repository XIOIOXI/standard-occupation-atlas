"""Offline Job Group Skill Inference contracts; no model client is implemented."""
from __future__ import annotations
import hashlib,json,re
from dataclasses import asdict,dataclass
from typing import Literal
INFERENCE_VERSION='skill-inference-v2'; PROMPT_VERSION='job-group-skill-inference-prompt-v6'; CONTEXT_SELECTION_VERSION='job-group-context-v2'; SKILL_NORMALIZATION_VERSION='skill-normalization-v1'
Status=Literal['completed','insufficient_context','skipped_generic','failed_validation']; Confidence=Literal['high','medium','low']
ALIASES={'python programming':'Python','python 编程':'Python','python':'Python','git version control':'Git'}
def normalize_skill(value:str)->str:
 text=re.sub(r'\s+',' ',value.strip()); key=re.sub(r'[\s._-]','',text.casefold());
 for raw,target in ALIASES.items():
  if re.sub(r'[\s._-]','',raw.casefold())==key:return target
 return text
@dataclass(frozen=True)
class InferredSkill:
 raw_skill_name:str; normalized_skill_name:str; skill_type:Literal['hard','soft']; confidence:Confidence; source_type:str='llm_inference'; evidence_level:str='inferred_medium'; reasoning_summary:str=''; skill_scope:Literal['occupation_core','domain_specific']='occupation_core'
 def __post_init__(self):
  if self.source_type!='llm_inference' or self.evidence_level not in {'inferred_medium','inferred_low'}:raise ValueError('Inferred skills cannot be observed evidence.')
@dataclass(frozen=True)
class JobGroupSkillInferenceInput:
 job_group_id:str; representative_title:str; canonical_occupation_id:str|None; canonical_occupation_title:str|None; industry_domain_context:str; original_job_titles:tuple[str,...]; occurrence_count:int; company_count:int; location_count:int; representative_source_contexts:tuple[dict,...]; major_requirement_examples:tuple[str,...]; company_type_distribution:dict[str,int]; location_distribution:dict[str,int]; grouping_version:str; taxonomy_version:str; context_quality:Literal['high','medium','low']
 def __post_init__(self):
  for name,value,maximum in (('representative_source_contexts',self.representative_source_contexts,5),('major_requirement_examples',self.major_requirement_examples,3),('original_job_titles',self.original_job_titles,10),('location_distribution',self.location_distribution,5)):
   if len(value)>maximum:raise ValueError(f'{name} may contain at most {maximum} entries')
 def fingerprint(self)->str:return hashlib.sha256(json.dumps(asdict(self),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
@dataclass(frozen=True)
class JobGroupSkillInferenceResult:
 job_group_id:str; input_fingerprint:str; inference_status:Status; hard_skills:tuple[InferredSkill,...]=(); soft_skills:tuple[InferredSkill,...]=(); inference_version:str=INFERENCE_VERSION; prompt_version:str=PROMPT_VERSION; context_selection_version:str=CONTEXT_SELECTION_VERSION; skill_normalization_version:str=SKILL_NORMALIZATION_VERSION; model:str|None=None; inferred_at:str|None=None
 def __post_init__(self):
  if len(self.hard_skills)>5 or len(self.soft_skills)>5:raise ValueError('At most five hard and five soft skills.')
  if any(x.skill_type!='hard' for x in self.hard_skills) or any(x.skill_type!='soft' for x in self.soft_skills):raise ValueError('Skill lists must match skill_type.')
