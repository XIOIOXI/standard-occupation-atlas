"""Small, explainable deterministic gap-candidate rules for the Curriculum MVP."""
from __future__ import annotations

IT_TERMS=('software','data','program','algorithm','network','security','artificial intelligence','web','frontend','backend','system','digital','信息','软件','数据','编程','算法','网络','安全','人工智能','技术','系统','数字')
DOMAIN_TERMS=('信息技术','数字产业','电子信息','通信','金融科技','科技','it')
TRANSFERABLE_SOFT=('问题解决','沟通','协作','team collaboration','communication','problem solving','project management','项目管理')

def relevance(skill:str, skill_type:str, domains:list[str]) -> tuple[str,list[str]]:
    text=skill.casefold(); reasons=[]
    if text.startswith('ai') or any(term.casefold() in text for term in IT_TERMS):
        reasons.append('program_keyword_relevance')
        if any(any(term.casefold() in domain.casefold() for term in DOMAIN_TERMS) for domain in domains): reasons.append('relevant_domain')
        return 'high',reasons
    if any(any(term.casefold() in domain.casefold() for term in DOMAIN_TERMS) for domain in domains):return 'medium',['relevant_domain']
    if skill_type=='soft' and any(term.casefold() in text for term in TRANSFERABLE_SOFT):return 'medium',['transferable_program_skill']
    return 'low',['insufficient_program_relevance_evidence']

def priority(relevance_level:str,status:str,weight:int,support_groups:int) -> tuple[str,list[str]]:
    reasons=[]
    if weight>=50:reasons.append('high_market_demand')
    if support_groups>=5:reasons.append('strong_recruitment_evidence')
    reasons.append('not_observed_in_curriculum' if status=='not_observed' else 'partial_curriculum_evidence')
    if relevance_level=='high':reasons.append('relevant_domain')
    if relevance_level=='high' and status=='not_observed' and weight>=50:return 'high',reasons
    if relevance_level in {'high','medium'} and weight>=5:return 'medium',reasons
    return 'low',reasons
