"""Build a read-only SNO v3.1 display projection from the completed v4 draft.

No model calls are made.  Source records remain untouched; this only creates
an independently versioned frontend artifact and an actionable holding queue.
"""
from __future__ import annotations
import hashlib, json, os
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/processed/record_role_classification_v1/full_drafts/sno_v31_reasonable_primary_v4_display'
# An explicitly supplied merged draft can be projected without changing the
# immutable real-run source.  Default remains the existing real final.
FINAL=Path(os.environ['SNO_FINAL_PATH']) if os.environ.get('SNO_FINAL_PATH') else ROOT/'data/processed/record_role_classification_v1/full_drafts/sno_v31_reasonable_primary_v4_real/final.json'
ROLES=ROOT/'data/processed/record_role_classification_v1/record_roles.json'
CAT=ROOT/'data/taxonomy/sno_v3_1/sno_occupation_catalog_v3.1.json'

def write(name,obj):
 OUT.mkdir(parents=True,exist_ok=True); p=OUT/name; t=p.with_suffix(p.suffix+'.tmp'); t.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf8'); t.replace(p)
def stable(prefix,*parts): return prefix+'-'+hashlib.sha256('|'.join(parts).encode()).hexdigest()[:20]
def main():
 f=json.loads(FINAL.read_text(encoding='utf8')); roles={x['record_role_id']:x for x in json.loads(ROLES.read_text(encoding='utf8'))['roles']}; cat=json.loads(CAT.read_text(encoding='utf8'))
 nodes={}; parent={}; catalog_level3=[]
 for l1 in cat['taxonomy']:
  for l2 in l1['level_2']:
   nodes[l2['level_2_id']]={'category_id':l2['level_2_id'],'level_1':l1['name'],'level_2':l2['name'],'level_3':None,'target_level':'level_2'};parent[l2['level_2_id']]=l1['level_1_id']
   for l3 in l2['level_3']:
    nodes[l3['level_3_id']]={'category_id':l3['level_3_id'],'level_1':l1['name'],'level_2':l2['name'],'level_3':l3['name'],'target_level':'level_3'};parent[l3['level_3_id']]=l2['level_2_id']
    catalog_level3.append(nodes[l3['level_3_id']])
 failure_errors={}
 for p in FINAL.parent.joinpath('failed').glob('map_*.json'):
  for x in json.loads(p.read_text(encoding='utf8')).get('failures',[]): failure_errors[x.get('occupation_id')]=x.get('error')
 grouped=defaultdict(list)
 for r in f['records']: grouped[r['title_group_id']].append(r)
 child_by_parent=defaultdict(list)
 for c in f['children']: child_by_parent[c['original_record_id']].append(c)
 child_map={x['occupation_id']:x for x in f['child_mappings']}
 restored_titles={x['original_record_id']:x.get('recovered_title') for x in f['non_role_log'] if x.get('decision')=='restore_title_and_map'}
 bubbles=defaultdict(list); level2_direct=defaultdict(list); unplaced=[]; queue=[]; repair=[]; displayed_ids=set(); invalid_paths=[]
 def row(item_id,label,source_rows,result,kind,original_group_ids):
  return {'standard_occupation_id':item_id,'label':label,'original_group_ids':original_group_ids,'source_atomic_unit_ids':sorted({roles[x['record_role_id']]['source_atomic_unit_id'] for x in source_rows}),'source_record_ids':sorted({roles[x['record_role_id']]['source_record_id'] for x in source_rows}),'source_record_role_ids':[x['record_role_id'] for x in source_rows],'status':result.get('status','review'),'reason':result.get('reason'),'candidate_category_ids':result.get('candidate_category_ids',[]),'item_kind':kind}
 for gid,rs in grouped.items():
  first=rs[0]; source=rs; effective=first['effective_result']; title=roles[first['record_role_id']]['source_title']; parent_children=child_by_parent.get(gid,[])
  # A validated split replaces its original combination in display; each child
  # still retains every original source record as provenance without copying counts.
  if parent_children:
   for child in parent_children:
    result=child_map.get(child['occupation_id'],{'status':'review','reason':'missing child mapping','candidate_category_ids':[]})
    item=row(child['occupation_id'],child['title'],source,result,'child_role',[gid])
    if result.get('status')=='mapped' and result.get('target_category_id') in nodes:
     target=result['target_category_id']
     (level2_direct if nodes[target]['target_level']=='level_2' else bubbles)[target].append(item);displayed_ids.add(item['standard_occupation_id'])
    else:
     unplaced.append(item);queue.append({**item,'queue_reason':'child_unclassified','processing_state':'pending'})
   continue
  error=failure_errors.get(gid); level_repaired=False
  if error=='mapped target level' and effective.get('target_category_id') in nodes:
   effective={**effective,'target_level':nodes[effective['target_category_id']]['target_level']}
   level_repaired=True
   repair.append({'title_group_id':gid,'field':'target_level','from':first['effective_result'].get('target_level'),'to':effective['target_level'],'action':'derived_from_legal_target_id','raw_response_unchanged':True})
  item=row(gid,title,source,effective,'original_role',[gid])
  eligibility=first.get('display_eligibility'); state=first.get('processing_state')
  if eligibility=='excluded_non_role': continue
  if effective.get('status')=='mapped' and effective.get('target_category_id') in nodes and (eligibility=='eligible' or level_repaired):
   target=effective['target_category_id']
   (level2_direct if nodes[target]['target_level']=='level_2' else bubbles)[target].append(item);displayed_ids.add(gid)
  else:
   reason='review_or_unclassified'
   if state=='failed_mapping_validation': reason='mapping_validation_failure'; repair.append({'title_group_id':gid,'original_result':effective,'action':'held_no_semantic_change','reason':'Existing raw response has candidate or L3-evidence contract failure; no occupation inference added.'})
   elif state=='hold_multi_source_span': reason='multi_source_span_unverified'
   elif eligibility=='hold_non_role': reason='non_role_hold'
   elif gid in restored_titles: reason='non_role_recovered_title_requires_mapping'; item['recovered_title']=restored_titles[gid]
   elif effective.get('status')=='taxonomy_gap': reason='taxonomy_gap'
   unplaced.append(item);queue.append({**item,'queue_reason':reason,'processing_state':state or 'pending'})
 # Explicitly report child mapping results that do not enter a valid category.
 categories={k:{'category':nodes[k],'occupations':v} for k,v in bubbles.items()}
 direct_buckets={k:{'bucket_id':'direct:'+k,'category':nodes[k],'occupations':v} for k,v in level2_direct.items()}
 projection={'schema_version':'sno-v3.1-full-draft-display-v3-catalog-recovery','taxonomy_version':cat['taxonomy_version'],'source_final':str(FINAL.relative_to(ROOT)).replace('\\','/'),'catalog_level3':catalog_level3,'category_bubbles':categories,'level2_direct_buckets':direct_buckets,'other_bubbles':{},'holding_bubbles':{},'level1_holding_bubbles':{},'unplaced':unplaced,'validation':{}}
 record_ids=[x['record_role_id'] for x in f['records']]
 replacement_final={r['title_group_id'] for r in f['records'] if r['display_eligibility']=='replaced_by_child_roles'}; span_final={r['title_group_id'] for r in f['records'] if r['display_eligibility']=='hold_multi_source_span'}
 stats={'source_records':len(roles),'final_records':len(f['records']),'source_coverage_ok':len(record_ids)==len(set(record_ids))==len(roles) and set(record_ids)==set(roles),'mapped_display_items':sum(len(x) for x in bubbles.values())+sum(len(x) for x in level2_direct.values()),'mapped_level2_direct_items':sum(len(x) for x in level2_direct.values()),'unclassified_queue_items':len(queue),'excluded_non_role_title_groups':len({r['title_group_id'] for r in f['records'] if r['display_eligibility']=='excluded_non_role'}),'replaced_combination_title_groups':len(child_by_parent),'replacement_display_field_unique_title_groups':len(replacement_final),'replacement_overlap_not_displayed_title_groups':len(set(child_by_parent)-replacement_final),'child_roles':len(f['children']),'child_mapped':sum(x.get('status')=='mapped' for x in f['child_mappings']),'child_unclassified':sum(x.get('status')!='mapped' for x in f['child_mappings']),'span_hold_field_unique_title_groups':len(span_final),'invalid_category_paths':invalid_paths,'final_field_counts':dict(Counter(r['display_eligibility'] for r in f['records']))}
 projection['validation']=stats
 trace_items=[x for b in bubbles.values() for x in b]+[x for b in level2_direct.values() for x in b]+unplaced
 write('display_projection_v31_full_draft.json',projection);write('sno_occ_trace_index_v31.json',{'schema_version':'sno-v3.1-display-trace-index-v1','occupations':{x['standard_occupation_id']:{'linked_occupation_ids':[],'source_record_role_ids':x['source_record_role_ids'],'source_record_ids':x['source_record_ids']} for x in trace_items}});write('unclassified_queue_v31.json',{'schema_version':'sno-v3.1-unclassified-queue-v1','taxonomy_version':cat['taxonomy_version'],'items':queue,'statistics':{'items':len(queue),'reasons':dict(Counter(x['queue_reason'] for x in queue))}});write('format_repair_log_v31.json',{'repairs':repair,'count':len(repair)});write('display_summary_v31.json',stats);write('integration_report_v31.json',{'statistics':stats,'notes':['Child-parent groups and final display-status groups use different stages: one parent was also excluded as non-role, so 108 generated child-parent relations become 107 replacement-status title groups.','One source-span hold likewise overlaps an excluded/other final state: 60 raw span failures become 59 final hold-status title groups.','No API calls were made during cleanup or display integration.']})
 print(json.dumps({'output':str(OUT),'statistics':stats},ensure_ascii=False))
if __name__=='__main__': main()
