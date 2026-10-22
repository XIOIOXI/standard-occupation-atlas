"""Small, conservative, pilot-evidence-backed Skill Normalization v2."""
from __future__ import annotations
import re

SKILL_NORMALIZATION_VERSION='skill-normalization-v2'
ALIASES_V2={
 'team collaboration':'团队协作',
 'collaboration':'团队协作',
 '团队协作能力':'团队协作',
 'analytical problem solving':'问题解决',
 'problem solving':'问题解决',
 '问题解决能力':'问题解决',
 'cross-functional collaboration':'跨部门协作',
 'communication with cross-functional teams':'跨部门协作',
 '跨部门协作能力':'跨部门协作',
}

def _key(value:str)->str:
 return re.sub(r'[\s._-]+','',value.strip().casefold())

_INDEX={_key(k):(v,k) for k,v in ALIASES_V2.items()}

def normalize_skill_v2(value:str):
 text=re.sub(r'\s+',' ',value.strip())
 hit=_INDEX.get(_key(text))
 return (hit[0],hit[1]) if hit else (text,None)
