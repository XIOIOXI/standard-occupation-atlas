import json, math, statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JG = ROOT/'data/processed/job_groups_v2/job_groups.jsonl'
MEM = ROOT/'data/processed/job_groups_v2/job_group_members.jsonl'
PI = ROOT/'data/processed/skill_inference_v2/pilot_50_inputs.jsonl'
PR = ROOT/'data/processed/skill_inference_v2/_mini_backup/pilot_50_results.jsonl'
OUT = ROOT/'data/processed/skill_inference_v2/inference_eligibility_analysis.json'
REPORT = ROOT/'docs/reports/skill-inference-eligibility-budget-analysis.md'

def read_jsonl(p):
    with p.open(encoding='utf-8') as f:
        return [json.loads(x) for x in f if x.strip()]

def nonempty(v): return v is not None and str(v).strip() not in ('', 'null', 'None')
def generic(t):
    t=(t or '').strip()
    return len(t)<4 or t in {'技术工程师','技术岗','综合专员','运营管理岗','研发助理','运营','产品','销售','管理岗','研发类','专业不限'} or any(x in t for x in ('管培生','培训生','招聘项目'))

def main():
    groups=read_jsonl(JG); members=read_jsonl(MEM); mb=defaultdict(list)
    for m in members: mb[m.get('job_group_id')].append(m)
    rows=[]
    for g in groups:
        ms=mb.get(g['job_group_id'],[]); title=g.get('representative_title','')
        atomic=len(ms) or int(g.get('member_count') or 1); recs=len({m.get('source_record_id') for m in ms if nonempty(m.get('source_record_id'))}) or len(g.get('source_recruitment_record_ids') or []) or 1
        major=any(nonempty(m.get('major_requirement')) and m.get('major_requirement')!='按照岗位筛选' for m in ms)
        industry=nonempty(g.get('industry_domain_context')) or any(nonempty(m.get('industry_category')) for m in ms)
        specific=not generic(title); mapped=g.get('taxonomy_mapping_status')=='mapped' or nonempty(g.get('canonical_occupation_id'))
        if mapped and specific and industry and (atomic>1 or major): q='high'
        elif (mapped and specific) or (industry and specific) or major: q='medium'
        else: q='low'
        rows.append({'id':g['job_group_id'],'title':title,'quality':q,'mapped':mapped,'atomic':atomic,'records':recs,'record_ids':{m.get('source_record_id') for m in ms if nonempty(m.get('source_record_id'))},'multi':atomic>1,'major':major,'industry':industry,'specific':specific})
    def profile(rs):
        c=Counter(r['quality'] for r in rs); mapped=Counter('mapped' if r['mapped'] else 'unmapped' for r in rs); sm=Counter('multi' if r['multi'] else 'singleton' for r in rs)
        ids=set().union(*(r['record_ids'] for r in rs)) if rs else set()
        return {'groups':len(rs),'atomic_units':sum(r['atomic'] for r in rs),'recruitment_records':len(ids) or sum(r['records'] for r in rs),'quality':dict(c),'mapped':dict(mapped),'singleton_multi':dict(sm)}
    cross=Counter((r['quality'], 'mapped' if r['mapped'] else 'unmapped', 'multi' if r['multi'] else 'singleton') for r in rows)
    strategies={
      'A_high_context':[r for r in rows if r['quality']=='high'],
      'B_high_plus_medium_multi':[r for r in rows if r['quality']=='high' or (r['quality']=='medium' and r['multi'])],
      'C_high_plus_medium_sufficient_evidence':[r for r in rows if r['quality']=='high' or (r['quality']=='medium' and r['major'] and r['industry'] and r['specific'])],
      'D_recruitment_weight_prioritized_top_25pct':sorted(rows,key=lambda r:(r['records'],r['atomic'],r['quality']=='high'),reverse=True)[:math.ceil(len(rows)*.25)]}
    base=profile(rows)
    strat={k:{**profile(v),'selected_pct':round(100*len(v)/len(rows),2),'skipped_groups':len(rows)-len(v),'atomic_coverage_pct':round(100*sum(x['atomic'] for x in v)/base['atomic_units'],2),'record_coverage_pct':round(100*len(set().union(*(x['record_ids'] for x in v)))/base['recruitment_records'],2)} for k,v in strategies.items()}
    inp={x['job_group_id']:x for x in read_jsonl(PI)}; results=read_jsonl(PR); abst=[]
    for r in results:
        i=inp.get(r.get('job_group_id'),{}); ctx=i.get('context_quality','unknown'); title=i.get('representative_title',''); pi=i.get('prepared_inference_input',{})
        maj=bool(pi.get('major_requirement_examples')); ind=bool(pi.get('industry_distribution') or pi.get('industry_domain_context')); sc=len(pi.get('representative_source_contexts') or i.get('representative_source_contexts') or [])
        abst.append({'status':r.get('inference_status') or r.get('status'),'context_quality':ctx,'mapped':nonempty(i.get('canonical_occupation_id')),'multi':(i.get('member_count') or 1)>1,'title_specific':not generic(title),'major_available':maj,'industry_available':ind,'source_context_count':sc,'member_count':i.get('member_count',1)})
    pilot={'status_counts':dict(Counter(x['status'] for x in abst)),'by_feature':{}}
    for f in ['context_quality','mapped','multi','title_specific','major_available','industry_available']:
        d=defaultdict(Counter)
        for x in abst:d[str(x[f])][x['status']]+=1
        pilot['by_feature'][f]={k:dict(v) for k,v in d.items()}
    avg_in,avg_out=55864/50,13072/50; per_cost=(avg_in*.15+avg_out*.60)/1e6
    budget={}
    ranked=sorted(rows,key=lambda r:(r['records'],r['atomic'],r['quality']=='high'),reverse=True)
    for cap in (2,3,4):
        n=min(len(rows),math.floor(cap/per_cost)); sel=ranked[:n]; budget[str(cap)]={'assumption_usd_per_million':{'input':.15,'output':.60},'groups':n,'input_tokens':round(n*avg_in),'output_tokens':round(n*avg_out),'total_tokens':round(n*(avg_in+avg_out)),'atomic_coverage_pct':round(100*sum(x['atomic'] for x in sel)/base['atomic_units'],2),'record_coverage_pct':round(100*len(set().union(*(x['record_ids'] for x in sel)))/base['recruitment_records'],2)}
    data={'api_calls':0,'population':base,'derived_quality_note':'context_quality is a deterministic proxy derived from persisted fields; no new inference was run.','cross_tab':{ '|'.join(k):v for k,v in cross.items()},'pilot_abstention':pilot,'strategies':strat,'pilot_average_tokens':{'input':avg_in,'output':avg_out,'total':avg_in+avg_out},'budget_scenarios':budget}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# Skill Inference Eligibility and Budget Analysis','',f'- API calls: **0**','- Population: **{len(rows):,} frozen Job Groups**','- Quality is a deterministic proxy from persisted context/mapping/member fields; it is not a trained classifier.','', '## Population profile', json.dumps(base,ensure_ascii=False,indent=2),'','## Cross-tab (quality | mapping | singleton/multi)',json.dumps(data['cross_tab'],ensure_ascii=False,indent=2),'','## Mini pilot abstention (descriptive only)',json.dumps(pilot,ensure_ascii=False,indent=2),'','## Candidate strategies']
    for k,v in strat.items(): lines += [f'### {k}',json.dumps(v,ensure_ascii=False,indent=2)]
    lines += ['', '## Token and budget planning',f'- Pilot averages: {avg_in:.2f} input, {avg_out:.2f} output, {avg_in+avg_out:.2f} total tokens/group.','- Illustrative planning rates only (not production pricing): $0.15/M input, $0.60/M output.',json.dumps(budget,ensure_ascii=False,indent=2),'','## Conclusion','Recruitment-weight prioritization yields the strongest evidence coverage per selected group; no strategy is auto-approved. Low-evidence groups remain represented and are not deleted.']
    REPORT.parent.mkdir(parents=True,exist_ok=True); REPORT.write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({'groups':len(rows),'population':base,'strategies':{k:{'groups':v['groups'],'atomic_coverage_pct':v['atomic_coverage_pct'],'record_coverage_pct':v['record_coverage_pct']} for k,v in strat.items()},'budget':budget,'api_calls':0},ensure_ascii=False))
if __name__=='__main__': main()
