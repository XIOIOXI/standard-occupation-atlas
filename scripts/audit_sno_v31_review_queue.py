"""Offline audit of review statuses in the completed SNO v3.1 full draft."""
from __future__ import annotations
import json,re
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FINAL=ROOT/'data/processed/record_role_classification_v1/full_drafts/sno_v31_reasonable_primary_v4_real/final.json'
ROLES=ROOT/'data/processed/record_role_classification_v1/record_roles.json'
OUT=ROOT/'data/processed/record_role_classification_v1/full_drafts/sno_v31_reasonable_primary_v4_display/review_queue_audit_v31.json'
def main():
 f=json.loads(FINAL.read_text(encoding='utf8')); roles={x['record_role_id']:x for x in json.loads(ROLES.read_text(encoding='utf8'))['roles']}; groups={}
 for r in f['records']:groups.setdefault(r['title_group_id'],[]).append(r)
 first=[]; withdrawn=[]; program=[]
 unique_pat=re.compile(r'唯一|无法确定|不能确定'); trainee_pat=re.compile(r'管培|培训|储备|实习')
 for gid,rows in groups.items():
  r=rows[0];initial=r['initial'];review=r['review'];effective=r['effective_result'];title=roles[r['record_role_id']]['source_title'];base={'title_group_id':gid,'title':title,'source_record_count':len(rows),'initial_result':initial,'review_result':review,'effective_result':effective,'processing_state':r.get('processing_state'),'display_eligibility':r.get('display_eligibility')}
  if initial['status']=='review':first.append(base)
  if initial['status']=='mapped' and review.get('verdict')=='unresolved':withdrawn.append(base)
  if r.get('processing_state')=='failed_mapping_validation' or r.get('display_eligibility')=='hold_multi_source_span':program.append(base)
 child_unclassified=[x for x in f['child_mappings'] if x.get('status')!='mapped']
 restored=[x for x in f['non_role_log'] if x.get('decision')=='restore_title_and_map']
 top=sorted(first,key=lambda x:(-x['source_record_count'],x['title']))[:30]
 def count_source(items):return sum(x['source_record_count'] for x in items)
 result={'taxonomy_version':'sno-v3.1-local-revision','scope':'latest display projection source final.json','counts':{'initial_review':{'title_groups':len(first),'source_records':count_source(first)},'review_unresolved_while_effective_mapped':{'title_groups':len(withdrawn),'source_records':count_source(withdrawn),'note':'These are not treated as review in the current display projection; they require a separate reasonableness decision before either retaining or withdrawing.'},'program_hold_original_groups':{'title_groups':len(program),'source_records':count_source(program)},'unclassified_child_roles':len(child_unclassified),'restored_titles_without_followup_mapping':len(restored)},'rule_audit':{'initial_review_reasons_containing_nonunique_language':sum(bool(unique_pat.search(x['initial_result'].get('reason') or '')) for x in first),'initial_review_reasons_containing_trainee_identity_language':sum(bool(trainee_pat.search(x['initial_result'].get('reason') or '')) for x in first),'interpretation':'These are flag counts, not automatic error counts. Under reasonable-primary policy, non-unique alternatives alone cannot justify review; trainee identity alone cannot justify review when the title states a professional function.'},'top_30_initial_review_title_groups':[{'rank':i+1,'title_group_id':x['title_group_id'],'title':x['title'],'source_record_count':x['source_record_count'],'reason':x['initial_result'].get('reason'),'review_verdict':x['review_result'].get('verdict'),'nonunique_language_flag':bool(unique_pat.search(x['initial_result'].get('reason') or '')),'trainee_identity_flag':bool(trainee_pat.search(x['initial_result'].get('reason') or ''))} for i,x in enumerate(top)],'review_unresolved_effective_mapped':withdrawn}
 OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print(json.dumps(result['counts'],ensure_ascii=False))
if __name__=='__main__':main()
