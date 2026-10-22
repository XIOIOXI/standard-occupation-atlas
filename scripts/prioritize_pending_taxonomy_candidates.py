"""Deterministically group and prioritize pending taxonomy candidates."""
from __future__ import annotations

import argparse, csv, json, math, re, unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from app.domain.taxonomy.coverage import load_reference_taxonomy, normalise_title

TRAINEE = re.compile(r"(?:管培|管理培训生|培训生|储备干部|培养生|英才生|星计划|菁鲤|菁英|优\+|金种子)")

def key(title: str) -> str:
    text = unicodedata.normalize("NFKC", title).casefold()
    text = re.sub(r"[\s\-_／/·,，。；;（）()\[\]]", "", text)
    return re.sub(r"(?:岗位|岗)$", "", text)

def parse_dist(row: dict[str, str]) -> dict[str, int]:
    try: return json.loads(row.get("industry_distribution", "{}"))
    except json.JSONDecodeError: return {}

def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument("--taxonomy",type=Path,required=True); ap.add_argument("--proposal",type=Path,required=True); ap.add_argument("--candidates",type=Path,required=True); ap.add_argument("--mapping",type=Path,required=True); ap.add_argument("--output-dir",type=Path,required=True); ap.add_argument("--report",type=Path,required=True); args=ap.parse_args()
    entries,_=load_reference_taxonomy(args.taxonomy)
    with args.proposal.open(encoding="utf-8-sig",newline="") as f: proposal={r["candidate_title"]:r for r in csv.DictReader(f)}
    with args.candidates.open(encoding="utf-8-sig",newline="") as f: source={r["candidate_job_title"]:r for r in csv.DictReader(f)}
    with args.mapping.open(encoding="utf-8-sig",newline="") as f: mapping=list(csv.DictReader(f))
    mapping_by_title=defaultdict(list)
    for x in mapping:
        if x["gate_status"]=="accepted": mapping_by_title[x["job_title_unit"]].append(x)
    pending=[r for r in proposal.values() if r["review_status"]=="pending_review"]
    families=defaultdict(list)
    for r in pending: families[key(r["candidate_title"])].append(r)
    max_occ=max(int(r["occurrence_count"]) for r in pending); max_co=max(int(r["company_count"]) for r in pending); max_lo=max(int(r["location_count"]) for r in pending)
    rows=[]
    for idx,members in enumerate(families.values(),1):
        members=sorted(members,key=lambda r:(-int(r["occurrence_count"]),r["candidate_title"]))
        rep=members[0]["candidate_title"]; occ=sum(int(r["occurrence_count"]) for r in members); companies=sum(int(r["company_count"]) for r in members); locations=sum(int(r["location_count"]) for r in members)
        dist=Counter();
        for r in members: dist.update(parse_dist(source.get(r["candidate_title"],{})))
        industry_spread=len(dist); spread_component=min(industry_spread/10,1.0)*20
        oc=40*math.log1p(occ)/math.log1p(max_occ); cc=30*math.log1p(companies)/math.log1p(max_co); lc=10*math.log1p(locations)/math.log1p(max_lo)
        score=round(oc+cc+lc+spread_component,3)
        tier="P0" if score>=75 else "P1" if score>=55 else "P2" if score>=30 else "P3"
        possible=[]
        n=normalise_title(rep)
        for e in entries:
            en=normalise_title(e.level_3)
            if (len(n)>=4 and (en in n or n in en)) and e.level_3 not in possible: possible.append(e.level_3)
        contexts=[]; seen=set()
        for member in members:
            for x in mapping_by_title.get(member["candidate_title"],[]):
                sig=(x.get("company_name",""),x.get("industry_category",""))
                if sig in seen: continue
                seen.add(sig); contexts.append({k:x.get(k) for k in ["source_record_id","raw_job_title","company_name","industry_category","location","major_requirement","education_requirement"]})
                if len(contexts)>=5: break
            if len(contexts)>=5: break
        rows.append({"family_id":f"PCF-{idx:05d}","representative_title":rep,"member_titles":json.dumps([m["candidate_title"] for m in members],ensure_ascii=False),"member_count":len(members),"aggregate_occurrence_count":occ,"aggregate_company_count":companies,"aggregate_location_count":locations,"industry_distribution":json.dumps(dict(dist.most_common()),ensure_ascii=False),"source_record_count":sum(int(m["occurrence_count"]) for m in members),"existing_taxonomy_possible_matches":json.dumps(possible,ensure_ascii=False),"management_trainee_family":bool(TRAINEE.search(rep) or any(TRAINEE.search(m["candidate_title"]) for m in members)),"priority_score":score,"occurrence_component":round(oc,3),"company_component":round(cc,3),"location_component":round(lc,3),"industry_component":round(spread_component,3),"priority_tier":tier,"representative_source_contexts":json.dumps(contexts,ensure_ascii=False)})
    rows.sort(key=lambda r:(-float(r["priority_score"]),-int(r["aggregate_occurrence_count"]),r["representative_title"]))
    for i,r in enumerate(rows,1): r["priority_rank"]=i
    args.output_dir.mkdir(parents=True,exist_ok=True)
    fields=list(rows[0])
    with (args.output_dir/"pending_candidate_families.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    queue=[r for r in rows if r["priority_tier"] in {"P0","P1"}]
    with (args.output_dir/"semantic_review_queue.jsonl").open("w",encoding="utf-8") as f:
        for r in queue: f.write(json.dumps({k:r[k] for k in ["family_id","representative_title","member_titles","aggregate_occurrence_count","aggregate_company_count","aggregate_location_count","industry_distribution","representative_source_contexts","existing_taxonomy_possible_matches","priority_score","priority_tier"]},ensure_ascii=False)+"\n")
    counts=Counter(r["priority_tier"] for r in rows); trainee=[r for r in rows if r["management_trainee_family"]]; p0=sum(int(r["aggregate_occurrence_count"]) for r in rows if r["priority_tier"]=="P0"); p01=sum(int(r["aggregate_occurrence_count"]) for r in rows if r["priority_tier"] in {"P0","P1"})
    summary={"pending_candidates_reviewed":len(pending),"candidate_family_count":len(rows),"priority_tier_counts":dict(counts),"p0_p1_family_count":counts["P0"]+counts["P1"],"llm_review_units_if_one_per_family":len(queue),"management_trainee_family_count":len(trainee),"p0_upper_bound_accepted_units":p0,"p0_p1_upper_bound_accepted_units":p01,"score_formula":"40 log occurrence + 30 log companies + 10 log locations + 20 industry spread; company and occurrence are log-scaled to limit single-company repetition.","tier_thresholds":"P0 >=75; P1 >=55; P2 >=30; P3 <30","estimate_note":"Impact is an upper bound only; no candidate is assumed to become a new occupation."}
    (args.output_dir/"pending_prioritization_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    def table(items): return "\n".join(f"| {r['priority_rank']} | {r['representative_title']} | {r['aggregate_occurrence_count']} | {r['aggregate_company_count']} | {r['aggregate_location_count']} | {r['priority_score']} | {r['priority_tier']} |" for r in items)
    lines=["# Pending Candidate Prioritization","","Only `pending_review` candidates are included. This is deterministic grouping and queue preparation; no LLM or taxonomy change was performed.","","## Summary","",f"- Pending titles reviewed: {len(pending):,}",f"- Conservative candidate families: {len(rows):,}",f"- P0/P1 semantic review queue: {len(queue):,}",f"- Management-trainee families: {len(trainee):,}","", "| Tier | Families |", "|---|---:|"]
    for t in ["P0","P1","P2","P3"]: lines.append(f"| {t} | {counts[t]:,} |")
    lines += ["", "## Scoring", "", "Priority = 40×log occurrence + 30×log companies + 10×log locations + 20×industry spread. Each component is retained in the family CSV. Thresholds: P0 ≥75, P1 ≥55, P2 ≥30, P3 <30.","", "## Top 30 families", "", "| Rank | Representative | Occurrences | Companies | Locations | Score | Tier |", "|---:|---|---:|---:|---:|---:|---|"]+ [table(rows[:30]),"", "## Management-trainee review", "", "Management-trainee families are flagged separately and are not proposed as occupations. They require a taxonomy policy decision distinguishing occupation, trainee type, and company programme.","", "## Impact upper bounds", "",f"- P0 accepted-unit upper bound: {p0:,}",f"- P0+P1 accepted-unit upper bound: {p01:,}","- These are prioritization impacts, not predicted new occupations or formal coverage results.","", "## Sanity constraints", "", "- Grouping removes only surface suffix/format variants; domain qualifiers such as AI, software, hardware, or industry terms remain separate.","- Scores are log-scaled so repeated postings by one company do not dominate.","- All families retain member titles, industry distributions, and representative contexts."]
    args.report.parent.mkdir(parents=True,exist_ok=True); args.report.write_text("\n".join(lines)+"\n",encoding="utf-8"); print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
