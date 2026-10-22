"""Create a versioned MVP runtime taxonomy from the approved consolidation plan."""
from __future__ import annotations
import argparse, csv, json
from datetime import datetime, timezone
from pathlib import Path
from app.domain.taxonomy.coverage import load_reference_taxonomy

VERSION="mvp-taxonomy-v4.1-frozen"; NEW_IDS={"财务专员":"OCC0453","技术服务工程师":"OCC0454"}
def main():
 p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,required=True);p.add_argument('--taxonomy',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 entries,_=load_reference_taxonomy(a.taxonomy); by_id={e.occupation_id:e for e in entries}; rows=list(csv.DictReader(a.plan.open(encoding='utf-8-sig')))
 approved=[r for r in rows if r['governance_status']=='recommended_for_approval']
 aliases=[r for r in approved if r['identity_decision']=='alias_of_existing']; new=[r for r in approved if r['identity_decision']=='proposed_new_occupation']
 if len(aliases)!=13 or {r['recommended_standard_title'] for r in new}!=set(NEW_IDS): raise SystemExit('Approved plan scope mismatch; runtime taxonomy not written.')
 occupations={e.occupation_id:{'occupation_id':e.occupation_id,'level_1':e.level_1,'level_2':e.level_2,'level_3':e.level_3,'aliases':list(e.aliases),'provenance':{'source':'reference_workbook','approved_for_mvp':True}} for e in entries}
 for r in aliases:
  target=r['target_occupation_id'];
  if target not in occupations: raise ValueError('Invalid approved alias target')
  if r['representative_title'] not in occupations[target]['aliases']: occupations[target]['aliases'].append(r['representative_title'])
  occupations[target].setdefault('approved_alias_provenance',[]).append({'alias':r['representative_title'],'source_family_id':r['family_id'],'semantic_review_version':r['semantic_review_version'],'governance_status':r['governance_status'],'approved_for_mvp':True})
 for r in new:
  domains=json.loads(r['applicable_domains']); canonical=[d for d in domains if d['relationship_type']=='canonical']
  if len(canonical)!=1: raise ValueError('Approved new occupation requires exactly one canonical domain')
  item={'occupation_id':NEW_IDS[r['recommended_standard_title']],'level_1':canonical[0]['level_1'],'level_2':canonical[0]['level_2'],'level_3':r['recommended_standard_title'],'aliases':[],'occupation_domain_links':domains,'provenance':{'source_family_id':r['family_id'],'semantic_review_version':r['semantic_review_version'],'governance_status':r['governance_status'],'approved_for_mvp':True}}
  occupations[item['occupation_id']]=item
 artifact={'taxonomy_version':VERSION,'status':'FROZEN','created_at':datetime.now(timezone.utc).isoformat(),'reference_workbook':str(a.taxonomy),'reference_occupation_count':len(entries),'approved_alias_count':len(aliases),'approved_new_occupation_count':len(new),'occupations':list(occupations.values()),'freeze_policy':'No P2/P3 review or automatic expansion during MVP; reopen only for a demonstrated systemic taxonomy bug.'}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'taxonomy_version':VERSION,'aliases':len(aliases),'new_ids':NEW_IDS,'occupation_count':len(occupations)},ensure_ascii=False))
if __name__=='__main__':main()
