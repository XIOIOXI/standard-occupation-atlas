"""Persist a versioned, structured semantic-review pilot for P0 families.

The decisions are LLM-assisted review recommendations captured in this pilot;
they never modify the reference taxonomy and are cache-keyed by family/version.
"""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path
from app.domain.taxonomy.coverage import load_reference_taxonomy

VERSION="semantic-review-v1"; PROMPT="semantic-candidate-review-prompt-v1"; MODEL="gpt-5 (Codex runtime)"
DECISIONS={
"测试工程师":("pending_human_review",None,"","","","Cross-industry testing has materially different domain meanings; generic title cannot select software, semiconductor, or industrial testing.","medium"),
"研发工程师":("too_generic",None,"","","","R&D engineer is a broad function spanning many existing domain-specific R&D occupations.","high"),
"客户经理":("pending_human_review",None,"","","","Customer-manager meaning changes substantially between banking, enterprise sales, and service contexts.","medium"),
"销售工程师":("pending_human_review",None,"","","","A reusable role is plausible, but the current taxonomy has no stable cross-industry sales-engineering placement.","medium"),
"财务管理岗":("too_generic",None,"","","","Broad finance-management label lacks a stable level-3 occupational definition.","high"),
"结构工程师":("pending_human_review",None,"","","","Existing structural-engineer occupations occur in manufacturing, automotive, medical devices, and construction; context is required.","high"),
"产品工程师":("pending_human_review",None,"","","","Product engineer is cross-industry and distinct from product manager; placement requires human taxonomy policy.","medium"),
"技术支持工程师":("pending_human_review",None,"","","","Could mean IT support, communications support, or domain-specific technical support; no single safe match.","medium"),
"财务专员":("pending_human_review",None,"","","","Likely a reusable finance role, but no exact level-3 equivalent was identified in the supplied taxonomy context.","medium"),
"软件开发":("alias_of_existing","OCC0001","软件工程师","信息技术与数字产业","软件开发与工程","Market shorthand denotes the existing software-engineer occupation.","high"),
"采购":("too_generic",None,"","","","Purchasing is a function; it does not distinguish procurement specialist, strategic procurement, or procurement engineer.","high"),
"销售经理":("pending_human_review",None,"","","","Stable role wording, but taxonomy placement and boundary with sector-specific sales roles need human review.","medium"),
"项目管理岗":("alias_of_existing","OCC0295","项目经理","商业与企业服务","项目管理","Surface wording denotes the existing project-manager occupation without a domain qualifier.","medium"),
"项目工程师":("pending_human_review",None,"","","","Project engineer is domain-dependent and not equivalent to generic project manager.","medium"),
"技术支持":("too_generic",None,"","","","Function-only label is insufficiently specific to select an occupation.","high"),
"C++开发工程师":("alias_of_existing","OCC0004","C/C++开发工程师","信息技术与数字产业","软件开发与工程","C++ is a surface variant of the existing C/C++ development-engineer occupation.","high"),
"AI工程师":("pending_human_review",None,"","","","Too broad to distinguish algorithm, application, platform, or infrastructure roles.","high"),
"项目助理":("pending_human_review",None,"","","","Could support different project types and is not safely equivalent to project-management specialist.","low"),
"法务岗":("alias_of_existing","OCC0313","法务专员","商业与企业服务","法务与合规","Surface suffix variant of the existing legal-affairs specialist occupation.","high"),
"工程管理岗":("too_generic",None,"","","","Broad engineering-management category requires a domain and responsibility boundary.","high"),
"市场专员":("alias_of_existing","OCC0317","市场营销专员","市场营销与传媒","市场营销","Common market shorthand of the existing marketing specialist occupation.","high"),
"运维工程师":("pending_human_review",None,"","","","Could be IT operations, energy operations, or industrial maintenance; taxonomy placement is not stable.","high"),
}
def main():
 p=argparse.ArgumentParser();p.add_argument('--queue',type=Path,required=True);p.add_argument('--taxonomy',type=Path,required=True);p.add_argument('--results',type=Path,required=True);p.add_argument('--summary',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
 queue=[json.loads(x) for x in a.queue.read_text(encoding='utf-8').splitlines()];p0=[x for x in queue if x['priority_tier']=='P0']
 if len(p0)!=22: raise SystemExit(f'Expected exactly 22 P0 families, found {len(p0)}; no review executed.')
 entries,_=load_reference_taxonomy(a.taxonomy); by_id={e.occupation_id:e for e in entries}; now=datetime.now(timezone.utc).isoformat()
 prior={}
 if a.results.exists():
  for line in a.results.read_text(encoding='utf-8').splitlines():
   r=json.loads(line);prior[(r['family_id'],r['semantic_review_version'])]=r
 out=[]
 for f in p0:
  cache=(f['family_id'],VERSION)
  if cache in prior: out.append(prior[cache]);continue
  d=DECISIONS[f['representative_title']];decision,oid,standard,l1,l2,reason,confidence=d
  if oid and oid not in by_id: raise ValueError(f'Unknown occupation id: {oid}')
  out.append({'family_id':f['family_id'],'representative_title':f['representative_title'],'review_decision':decision,'matched_existing_occupation_id':oid or None,'matched_existing_occupation_title':standard or None,'recommended_standard_title':standard or None,'recommended_level_1':l1 or None,'recommended_level_2':l2 or None,'proposed_aliases':json.loads(f['member_titles']) if decision=='alias_of_existing' else [],'cross_industry':True,'taxonomy_structure_review_required':decision=='pending_human_review','confidence':confidence,'reasoning_summary':reason,'evidence_summary':{'occurrence_count':f['aggregate_occurrence_count'],'company_count':f['aggregate_company_count'],'location_count':f['aggregate_location_count'],'industry_distribution':json.loads(f['industry_distribution']),'source_contexts':json.loads(f['representative_source_contexts']),'possible_existing_taxonomy_matches':json.loads(f['existing_taxonomy_possible_matches'])},'semantic_review_version':VERSION,'prompt_version':PROMPT,'model':MODEL,'reviewed_at':now})
 a.results.parent.mkdir(parents=True,exist_ok=True);a.results.write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in out)+'\n',encoding='utf-8')
 from collections import Counter
 counts=Counter(x['review_decision'] for x in out);conf=Counter(x['confidence'] for x in out)
 summary={'p0_expected_count':22,'p0_reviewed_count':len(out),'decision_counts':dict(counts),'confidence_counts':dict(conf),'semantic_review_version':VERSION,'prompt_version':PROMPT,'model':MODEL,'cache_key':'family_id + semantic_review_version','validation':'All alias IDs validated against supplied Reference Taxonomy; outputs are recommendations only.'}
 a.summary.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
 focus=['测试工程师','研发工程师','客户经理','销售工程师','财务管理岗','结构工程师','产品工程师','技术支持工程师'];lines=['# Taxonomy Semantic Review — P0 Pilot','','P0 only: 22 candidate families. Results are LLM-assisted recommendations; the Reference Taxonomy was not modified.','',f'- Model: `{MODEL}`','- Semantic review version: `'+VERSION+'`; prompt version: `'+PROMPT+'`.','', '## Decision counts','','| Decision | Count |','|---|---:|']
 for k in ['alias_of_existing','proposed_new_occupation','merge_with_candidate','too_generic','company_specific_or_program','pending_human_review']:lines.append(f'| {k} | {counts[k]} |')
 lines+=['','## Focus cases','', '| Candidate | Evidence | Relevant taxonomy / decision | Reason |','|---|---|---|---|']
 for x in out:
  if x['representative_title'] in focus:
   e=x['evidence_summary'];target=x['matched_existing_occupation_title'] or 'No single safe existing occupation';lines.append(f"| {x['representative_title']} | {e['occurrence_count']} occurrences; {e['company_count']} companies; {e['location_count']} locations | {target}; {x['review_decision']} | {x['reasoning_summary']} |")
 lines+=['','## Validation','','- 22/22 P0 families have one versioned result.','- Every alias occupation ID exists in the Reference Taxonomy.','- No taxonomy workbook, splitter, candidate queue, or P1 family was changed or executed.']
 a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text('\n'.join(lines)+'\n',encoding='utf-8');print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
