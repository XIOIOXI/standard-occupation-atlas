"""Build evidence-only OCC↔SNO links through shared source record IDs."""
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path
ROOT=Path('data/processed')
MARKET=ROOT/'job_market_intelligence'/'market_map'/'market_occupations.json'
GROUPS=ROOT/'job_groups_v2'/'job_groups.jsonl'
SNO=ROOT/'record_role_classification_v1'/'targeted_name_repairs'/'name_only_targeted_repair_v1'/'full_name_only_mapping_repaired_v1.json'
OUT=ROOT/'record_role_classification_v1'/'targeted_name_repairs'/'name_only_targeted_repair_v1'/'occ_sno_source_links_v1.json'
def r(p): return json.loads(p.read_text(encoding='utf-8'))
def main():
 if OUT.exists(): raise FileExistsError(OUT)
 groups={x['job_group_id']:x for x in (json.loads(l) for l in GROUPS.read_text(encoding='utf-8').splitlines() if l)}
 occ=r(MARKET)['occupations']; sno=r(SNO)['results']
 rec_sno=defaultdict(set)
 for s in sno:
  for rid in s['source_record_ids']: rec_sno[rid].add(s['standard_occupation_id'])
 links=[]; linked_sno=set(); linked_occ=set()
 for o in occ:
  records={rid for gid in o['source_references']['job_group_ids'] for rid in groups[gid]['source_recruitment_record_ids']}
  targets=defaultdict(set)
  for rid in records:
   for sid in rec_sno.get(rid,()): targets[sid].add(rid)
  for sid, evidence in sorted(targets.items()):
   links.append({'occupation_id':o['occupation_id'],'standard_occupation_id':sid,'shared_source_record_ids':sorted(evidence),'shared_source_record_count':len(evidence),'link_method':'shared_source_recruitment_record_id','link_status':'evidence_link'})
   linked_sno.add(sid);linked_occ.add(o['occupation_id'])
 payload={'schema_version':'occ-sno-source-link-v1','link_method':'exact shared source recruitment record ID only; no title similarity or old display class used','occ_count':len(occ),'sno_count':len(sno),'link_count':len(links),'linked_occ_count':len(linked_occ),'linked_sno_count':len(linked_sno),'unlinked_occ_count':len(occ)-len(linked_occ),'unlinked_sno_count':len(sno)-len(linked_sno),'links':links}
 with OUT.open('x',encoding='utf-8') as f: json.dump(payload,f,ensure_ascii=False,indent=2);f.write('\n')
 print(json.dumps({k:payload[k] for k in payload if k.endswith('count')},ensure_ascii=False))
if __name__=='__main__':main()
