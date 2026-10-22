"""Consolidate immutable P0/P1 semantic-review artifacts into a governance plan."""
from __future__ import annotations
import argparse, csv, json, re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from app.domain.taxonomy.coverage import load_reference_taxonomy, normalise_title

RECOMMENDED_NEW = {"财务专员", "技术服务工程师"}
HOLD_NEW = {"硬件技术高级工程师"}

def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

def to_unified_v1(row: dict[str, Any]) -> dict[str, Any]:
    decision=row["review_decision"]
    return {"family_id":row["family_id"], "representative_title":row["representative_title"], "identity_decision":decision,
      "placement_status":"single_domain" if decision=="alias_of_existing" else "context_dependent",
      "target_occupation_id":row.get("matched_existing_occupation_id"), "target_occupation_title":row.get("matched_existing_occupation_title"),
      "recommended_standard_title":row.get("recommended_standard_title"), "canonical_level_1":row.get("recommended_level_1"), "canonical_level_2":row.get("recommended_level_2"),
      "applicable_domains":[], "confidence":row.get("confidence","medium"), "occurrence_count":row["evidence_summary"]["occurrence_count"],
      "source_batch":"P0 semantic-review-v1 (non-pending)", "semantic_review_version":row["semantic_review_version"], "prompt_version":row["prompt_version"], "notes":"Retained from v1 because P0 v2 replaces only v1 pending_human_review families."}

def to_unified_v2(row: dict[str, Any], batch: str) -> dict[str, Any]:
    evidence=row["observed_evidence"] if "observed_evidence" in row else row["evidence_summary"]
    return {"family_id":row["family_id"], "representative_title":row["representative_title"], "identity_decision":row["identity_decision"],
      "placement_status":row["placement_status"], "target_occupation_id":row.get("matched_existing_occupation_id"), "target_occupation_title":row.get("matched_existing_occupation_title"),
      "recommended_standard_title":row.get("recommended_standard_title"), "canonical_level_1":row.get("canonical_level_1"), "canonical_level_2":row.get("canonical_level_2"),
      "applicable_domains":row.get("applicable_domains",[]), "confidence":row.get("confidence","medium"), "occurrence_count":evidence["occurrence_count"],
      "source_batch":batch, "semantic_review_version":row["semantic_review_version"], "prompt_version":row["prompt_version"], "notes":row.get("semantic_interpretation","")}

def governance(row: dict[str, Any]) -> tuple[str, str]:
    d=row["identity_decision"]; title=row["representative_title"]
    if d=="alias_of_existing": return "recommended_for_approval", "Validated target occupation; approval would add only a market alias."
    if d=="proposed_new_occupation":
        if title in RECOMMENDED_NEW: return "recommended_for_approval", "Identity and available governance evidence are sufficiently specific for approval review."
        if title in HOLD_NEW: return "hold", "Seniority is embedded in the proposed canonical title; retain the semantic result but do not add a seniority-specific occupation in the MVP."
        return "needs_manual_review", "Keep as a proposal, but resolve naming, boundary, or canonical placement before any taxonomy addition."
    if d=="merge_with_candidate": return "needs_manual_review", "Candidate merge is valid only if the target candidate is approved; no taxonomy entry is created now."
    return "deferred_for_mvp", "Retain the raw title and source context; do not pursue more taxonomy expansion in MVP."

def main() -> None:
    p=argparse.ArgumentParser()
    for n in ("p0_v1","p0_v2","p1_v2","taxonomy","coverage_summary","plan","summary","report"):
        p.add_argument("--"+n.replace("_","-"),dest=n,type=Path,required=True)
    a=p.parse_args()
    p0_v1=[to_unified_v1(r) for r in read_jsonl(a.p0_v1) if r["review_decision"]!="pending_human_review"]
    p0_v2=[to_unified_v2(r,"P0 semantic-review-v2 (replaces v1 pending)") for r in read_jsonl(a.p0_v2)]
    p1_v2=[to_unified_v2(r,"P1 semantic-review-v2") for r in read_jsonl(a.p1_v2)]
    rows=p0_v1+p0_v2+p1_v2
    if (len(p0_v1),len(p0_v2),len(p1_v2),len(rows)) != (10,12,107,129): raise SystemExit("Unexpected review input scope; no plan written.")
    if len({r["family_id"] for r in rows}) != len(rows): raise SystemExit("Family collision after P0 replacement; no plan written.")
    entries,_=load_reference_taxonomy(a.taxonomy); ids={e.occupation_id:e for e in entries}; pairs={(e.level_1,e.level_2) for e in entries}
    alias_by_title=defaultdict(set)
    for r in rows:
        status,note=governance(r); r["governance_status"]=status; r["governance_notes"]=note+" "+r["notes"]
        if r["target_occupation_id"]:
            target=ids.get(r["target_occupation_id"])
            if not target or target.level_3!=r["target_occupation_title"]: raise ValueError("Invalid alias target.")
        if r["identity_decision"]=="alias_of_existing": alias_by_title[normalise_title(r["representative_title"])].add(r["target_occupation_id"])
        for d in r["applicable_domains"]:
            if (d["level_1"],d["level_2"]) not in pairs: raise ValueError("Invalid domain pair.")
    if any(len(v)>1 for v in alias_by_title.values()): raise ValueError("Alias conflict.")
    proposals=[r for r in rows if r["identity_decision"]=="proposed_new_occupation"]
    proposal_norm=defaultdict(list)
    for r in proposals: proposal_norm[normalise_title(r["recommended_standard_title"] or r["representative_title"])].append(r)
    duplicate_proposals={k:v for k,v in proposal_norm.items() if len(v)>1}
    if duplicate_proposals: raise ValueError("Exact/normalised duplicate proposed titles.")
    existing_forms={normalise_title(e.level_3) for e in entries}|{normalise_title(alias) for e in entries for alias in e.aliases}
    conflicts=[r["representative_title"] for r in proposals if normalise_title(r["recommended_standard_title"] or r["representative_title"]) in existing_forms]
    merge_rows=[r for r in rows if r["identity_decision"]=="merge_with_candidate"]
    proposed_titles={r["recommended_standard_title"] for r in proposals}
    for r in merge_rows:
        if r["recommended_standard_title"] not in proposed_titles: raise ValueError("Merge target does not exist among proposed candidates.")
    coverage=json.loads(a.coverage_summary.read_text(encoding="utf-8")); accepted=coverage["accepted_title_unit_count"]; baseline=coverage["level_3"]["exact_standard_mapped"]
    aliases=[r for r in rows if r["identity_decision"]=="alias_of_existing"]
    rec_new=[r for r in proposals if r["governance_status"]=="recommended_for_approval"]
    alias_impact=sum(int(r["occurrence_count"]) for r in aliases); new_impact=sum(int(r["occurrence_count"]) for r in rec_new)
    simulation={"baseline_level_3_coverage":coverage["level_3"]["coverage_rate"],"baseline_mapped_units":baseline,"accepted_units":accepted,"alias_only_mapped_units":baseline+alias_impact,"alias_only_coverage":round((baseline+alias_impact)/accepted,4),"alias_plus_recommended_new_mapped_units":baseline+alias_impact+new_impact,"alias_plus_recommended_new_coverage":round((baseline+alias_impact+new_impact)/accepted,4),"deferred_family_count":sum(r["governance_status"]=="deferred_for_mvp" for r in rows)}
    a.plan.parent.mkdir(parents=True,exist_ok=True)
    fields=["family_id","representative_title","identity_decision","governance_status","target_occupation_id","target_occupation_title","recommended_standard_title","placement_status","canonical_level_1","canonical_level_2","applicable_domains","confidence","source_batch","semantic_review_version","prompt_version","governance_notes"]
    with a.plan.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in rows: w.writerow({**{k:r.get(k) for k in fields},"applicable_domains":json.dumps(r["applicable_domains"],ensure_ascii=False)})
    counts=Counter(r["identity_decision"] for r in rows); gov=Counter(r["governance_status"] for r in rows)
    cross=[r for r in rows if r["placement_status"]=="cross_industry"]
    summary={"consolidated_family_count":len(rows),"source_batches":{"p0_v1_non_pending":len(p0_v1),"p0_v2_replacement":len(p0_v2),"p1_v2":len(p1_v2)},"identity_decision_counts":dict(counts),"governance_counts":dict(gov),"alias_count":len(aliases),"proposed_new_occupation_count":len(proposals),"merge_count":len(merge_rows),"cross_industry_count":len(cross),"deferred_counts":{"pending_identity_review":counts["pending_identity_review"],"too_generic":counts["too_generic"],"company_specific_or_program":counts["company_specific_or_program"]},"coverage_simulation":simulation,"validation":{"unique_families":True,"alias_targets_valid":True,"alias_conflicts":0,"merge_targets_valid":True,"circular_merges":0,"invalid_domain_pairs":0,"duplicate_proposed_titles":0,"proposal_title_conflicts_with_existing_taxonomy":conflicts,"p2_p3_executed":False,"reference_taxonomy_modified":False}}
    a.summary.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    def titles(rs:list[dict[str,Any]])->str:return "、".join(r["representative_title"] for r in rs) or "无"
    manual=[r for r in proposals if r["governance_status"]=="needs_manual_review"]; held=[r for r in proposals if r["governance_status"]=="hold"]
    lines=["# Consolidated Taxonomy Expansion Review","", "This plan consolidates completed P0/P1 reviews only. It is a governance proposal and does not alter the Reference Taxonomy.","", "## Scope","", f"- Consolidated unique families: {len(rows)} (P0 v1 non-pending {len(p0_v1)} + P0 v2 replacement {len(p0_v2)} + P1 v2 {len(p1_v2)})", "- P2/P3 are explicitly deferred.","", "## Governance summary","", "| Bucket | Count |","|---|---:|"]+[f"| {k} | {gov[k]} |" for k in ["recommended_for_approval","needs_manual_review","hold","deferred_for_mvp"]]
    lines += ["", "## Recommended aliases", "", titles(aliases), "", "## Recommended new occupations", "", titles(rec_new), "", "## New occupations requiring manual review", "", titles(manual), "", "## Held proposals", "", titles(held), "", "## Candidate merges", ""]
    lines += [f"- {r['representative_title']} → {r['recommended_standard_title']} ({r['family_id']})" for r in merge_rows]
    lines += ["", "## Cross-industry domain-link proposals", ""]
    for r in cross: lines.append(f"- {r['representative_title']}: canonical {r['canonical_level_1']} / {r['canonical_level_2']}; applicable {json.dumps(r['applicable_domains'],ensure_ascii=False)}")
    lines += ["", "## Coverage simulation", "", f"- Baseline Level-3 coverage: {simulation['baseline_level_3_coverage']:.2%} ({baseline}/{accepted})",f"- Approved aliases only: {simulation['alias_only_coverage']:.2%} ({simulation['alias_only_mapped_units']}/{accepted})",f"- Aliases + recommended new occupations: {simulation['alias_plus_recommended_new_coverage']:.2%} ({simulation['alias_plus_recommended_new_mapped_units']}/{accepted})","- Simulations use accepted-unit occurrence upper bounds; they are not a formal remapping or approval.","", "## MVP Taxonomy Freeze policy", "", "After an explicit human approval of this plan, freeze the Reference Taxonomy for MVP: do not execute P2/P3, do not pursue 100% coverage, and retain unknown/pending titles with raw context for Job Group and future offline Skill Inference. Reopen policy only for a demonstrated systemic issue.","", "## Validation", "", "- No family duplication after P0 v2 replaced only P0 v1 pending families.","- Alias IDs, merge targets, and emitted domain pairs were validated.","- No exact/normalised duplicate proposed title, invalid reference, or circular merge was found.","- No source result, workbook, P2, or P3 work was modified or executed."]
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
