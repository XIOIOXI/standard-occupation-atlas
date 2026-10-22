"""Conservative, deterministic Job Group baseline; no LLM calls."""
from __future__ import annotations
import argparse, hashlib, json, sqlite3, statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from app.domain.taxonomy.coverage import INDUSTRY_CONTEXT_TO_LEVEL_1, normalise_title, split_title_units_with_quality
from app.infrastructure.sqlite_job_group_repository import SqliteJobGroupRepository
VERSION='job-grouping-v1'
def industry_key(value:str|None)->str:
 text=normalise_title(value or ''); matches={v for k,v in INDUSTRY_CONTEXT_TO_LEVEL_1.items() if normalise_title(k) in text}
 return 'l1:'+next(iter(matches)) if len(matches)==1 else 'raw:'+(text or 'unknown')
def grouping_key(occupation_id:str|None,title:str,industry:str|None)->str:
 return ('mapped:'+occupation_id if occupation_id else 'unmapped:'+normalise_title(title))+'|'+industry_key(industry)
def main():
 p=argparse.ArgumentParser();
 for n in ('database','runtime_taxonomy','output_dir','report'): p.add_argument('--'+n.replace('_','-'),dest=n,type=Path,required=True)
 p.add_argument('--snapshot-id');a=p.parse_args(); runtime=json.loads(a.runtime_taxonomy.read_text(encoding='utf-8'))
 canonical=defaultdict(list); aliases=defaultdict(list); by_id={}
 for e in runtime['occupations']:
  by_id[e['occupation_id']]=e; canonical[normalise_title(e['level_3'])].append(e)
  for x in e.get('aliases',[]): aliases[normalise_title(x)].append(e)
 with sqlite3.connect(a.database) as c:
  c.row_factory=sqlite3.Row;snapshot=a.snapshot_id or c.execute('SELECT snapshot_id FROM dataset_snapshots ORDER BY imported_at DESC LIMIT 1').fetchone()[0]
  records=[dict(r) for r in c.execute("SELECT record_id,row_number,job_title,company_name,industry_category,location,recruitment_session,recruitment_batch,major_requirement,education_requirement FROM recruitment_records WHERE snapshot_id=? AND eligible_for_market_analysis=1 AND record_status!='duplicate' ORDER BY row_number",(snapshot,))]
 buckets=defaultdict(list); members=[]
 for r in records:
  for pos,u in enumerate(split_title_units_with_quality(r['job_title'] or '')):
   if u.gate_status!='accepted': continue
   forms=[normalise_title(u.unit)];
   if u.unit.endswith('岗位'): forms.append(normalise_title(u.unit[:-2]))
   elif u.unit.endswith('岗'): forms.append(normalise_title(u.unit[:-1]))
   candidates=[]
   for f in forms: candidates+=canonical.get(f,[])+aliases.get(f,[])
   candidates=list({x['occupation_id']:x for x in candidates}.values()); occ=candidates[0] if len(candidates)==1 else None
   ik=industry_key(r['industry_category']); key=grouping_key(occ['occupation_id'] if occ else None,u.unit,r['industry_category'])
   unit_id=hashlib.sha256(f"{snapshot}|{r['record_id']}|{pos}|{u.unit}".encode()).hexdigest()[:24]
   member={'source_record_id':r['record_id'],'source_atomic_unit_id':unit_id,'raw_job_title':r['job_title'],'job_title_unit':u.unit,'company_name':r['company_name'],'industry_category':r['industry_category'],'location':r['location'],'recruitment_session':r['recruitment_session'],'recruitment_batch':r['recruitment_batch'],'major_requirement':r['major_requirement'],'education_requirement':r['education_requirement'],'industry_compatibility_key':ik,'taxonomy_mapping_status':'mapped' if occ else 'unmapped','canonical_occupation_id':occ['occupation_id'] if occ else None}
   buckets[key].append(member)
 groups=[]
 for key,ms in buckets.items():
  occ_id=ms[0]['canonical_occupation_id'];occ=by_id.get(occ_id); title_counts=Counter(m['job_title_unit'] for m in ms); rep=sorted(title_counts,key=lambda x:(-title_counts[x],x))[0]; gid='JG-'+hashlib.sha256((VERSION+'|'+key).encode()).hexdigest()[:16]
  for m in ms:m['job_group_id']=gid
  groups.append({'job_group_id':gid,'representative_title':rep,'canonical_occupation_id':occ_id,'canonical_occupation_title':occ['level_3'] if occ else None,'industry_domain_context':ms[0]['industry_compatibility_key'],'occurrence_count':len(ms),'company_count':len({m['company_name'] for m in ms if m['company_name']}),'location_count':len({m['location'] for m in ms if m['location']}),'original_job_titles':sorted({m['raw_job_title'] for m in ms}),'source_record_ids':sorted({m['source_record_id'] for m in ms}),'source_atomic_unit_ids':[m['source_atomic_unit_id'] for m in ms],'taxonomy_mapping_status':'mapped' if occ else 'unmapped','grouping_method':'canonical_occupation_and_compatible_industry' if occ else 'normalised_atomic_title_and_compatible_industry','grouping_version':VERSION,'grouping_reason':key})
  members+=ms
 sizes=[g['occurrence_count'] for g in groups]; summary={'snapshot_id':snapshot,'grouping_version':VERSION,'generated_at':datetime.now(timezone.utc).isoformat(),'eligible_record_count':len(records),'accepted_atomic_unit_count':len(members),'job_group_count':len(groups),'mapped_job_group_count':sum(g['taxonomy_mapping_status']=='mapped' for g in groups),'unmapped_job_group_count':sum(g['taxonomy_mapping_status']=='unmapped' for g in groups),'average_members_per_group':round(sum(sizes)/len(sizes),4),'median_members_per_group':statistics.median(sizes),'singleton_group_count':sum(x==1 for x in sizes),'groups_over_5_members':sum(x>5 for x in sizes),'groups_over_10_members':sum(x>10 for x in sizes),'groups_over_50_members':sum(x>50 for x in sizes),'runtime_taxonomy_version':runtime['taxonomy_version']}
 repo=SqliteJobGroupRepository(a.database);repo.save(snapshot,VERSION,summary,groups,members)
 a.output_dir.mkdir(parents=True,exist_ok=True)
 for name,data in [('job_groups.jsonl',groups),('job_group_members.jsonl',members)]: (a.output_dir/name).write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in data)+'\n',encoding='utf-8')
 (a.output_dir/'job_group_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 largest=sorted(groups,key=lambda x:(-x['occurrence_count'],x['job_group_id']))[:30]; multi=sorted([g for g in groups if g['occurrence_count']>1],key=lambda x:hashlib.sha256(x['job_group_id'].encode()).hexdigest())[:100]; cross=sorted([g for g in groups if g['company_count']>1],key=lambda x:hashlib.sha256(x['job_group_id'].encode()).hexdigest())[:50]; unmapped=sorted([g for g in groups if g['taxonomy_mapping_status']=='unmapped'],key=lambda x:hashlib.sha256(x['job_group_id'].encode()).hexdigest())[:50]
 samples=[]
 for label,data in [('largest_30',largest),('deterministic_multi_member_100',multi),('cross_company_50',cross),('unmapped_50',unmapped)]:
  for g in data:samples.append({'sample_set':label,**g})
 (a.output_dir/'job_group_audit_samples.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in samples)+'\n',encoding='utf-8')
 lines=['# Job Grouping v1','',f"- Eligible records: {len(records):,}",f"- Accepted atomic units: {len(members):,}",f"- Job Groups: {len(groups):,}",f"- Mapped / unmapped groups: {summary['mapped_job_group_count']:,} / {summary['unmapped_job_group_count']:,}",f"- Average / median members: {summary['average_members_per_group']:.2f} / {summary['median_members_per_group']}",f"- Singleton / >10 / >50: {summary['singleton_group_count']:,} / {summary['groups_over_10_members']:,} / {summary['groups_over_50_members']:,}",'','## Largest groups','', '| Title | Members | Companies | Mapping | Context |','|---|---:|---:|---|---|']
 for g in largest[:10]: lines.append(f"| {g['representative_title']} | {g['occurrence_count']} | {g['company_count']} | {g['taxonomy_mapping_status']} | {g['industry_domain_context']} |")
 lines += ['','## Policy','', 'Groups require the same approved canonical occupation or the same conservative normalised atomic title, plus the same compatible-industry key. Canonical occupation identity never forces cross-industry merging. No LLM or Skill Inference was run.']
 a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text('\n'.join(lines)+'\n',encoding='utf-8');print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
