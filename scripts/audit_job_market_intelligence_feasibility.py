"""Deterministic feasibility audit for the Job Market Intelligence product pivot."""
from __future__ import annotations
import json, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, "backend")
from app.domain.job_market.feasibility import build_occupation_inventory, build_comparison_candidates, select_demo_occupations

ROOT = Path("data/processed")
SELECTED = ROOT / "skill_inference_v2/selective_mini_1000/selected_inputs.jsonl"
RESULTS = ROOT / "skill_inference_v2/selective_mini_1000/results.jsonl"
OUT = ROOT / "job_market_intelligence"
REPORT = Path("docs/reports/job-market-intelligence-feasibility.md")

def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

def main():
    selected = read_jsonl(SELECTED); results = {x["job_group_id"]: x for x in read_jsonl(RESULTS)}
    if len(selected) != 1000: raise SystemExit(f"expected frozen selective population of 1000, found {len(selected)}")
    inventory = build_occupation_inventory(selected, results)
    comparisons = build_comparison_candidates(inventory)
    demos = select_demo_occupations(inventory, comparisons)
    profile = json.loads((ROOT / "skill_demand_profile/skill_demand_profile.json").read_text(encoding="utf-8"))
    pmi = json.loads((ROOT / "skill_demand_profile/skill_cooccurrence_pmi.json").read_text(encoding="utf-8"))
    communities = json.loads((ROOT / "skill_demand_profile/skill_communities.json").read_text(encoding="utf-8"))
    domain_profiles = json.loads((ROOT / "skill_demand_profile/domain_skill_profiles.json").read_text(encoding="utf-8"))
    result_statuses = Counter(x.get("inference_status", "unknown") for x in results.values())
    context_distribution = Counter(str(len(x["contexts"])) if len(x["contexts"]) < 4 else "4+" for x in inventory["occupations"])
    mapped_context = Counter("mapped" if x["mapped"] else "unmapped" for x in inventory["occupations"])
    skill_nodes = {item["skill_name"] for item in profile.get("overall_frequency", {}).get("all", [])}
    skill_map = {
        "usable_skill_node_count": len(skill_nodes),
        "usable_global_pmi_edge_count": len(pmi.get("relationships", [])),
        "louvain_community_count": len(communities.get("communities", [])),
        "community_sizes": [{"community_id": c.get("community_id"), "skill_count": c.get("skill_count", len(c.get("member_skills", [])))} for c in communities.get("communities", [])],
        "relationship_levels": {
            "global_market_skill_relationships": {"status": "SUPPORTED", "source": "skill_cooccurrence_pmi.json", "scope": "global across selective completed inference groups"},
            "occupation_specific_skill_relationships": {"status": "DERIVABLE", "method": "recompute co-occurrence over completed groups keyed by occupation identity; not present as a frozen artifact"},
            "occupation_context_specific_relationships": {"status": "DERIVABLE", "method": "recompute co-occurrence over completed groups partitioned by occupation and industry/domain context"},
        },
        "visual_relationships": {
            "occupation_to_skill": "DERIVABLE", "occupation_to_skill_community": "DERIVABLE", "community_to_skills": "SUPPORTED", "context_to_domain_skills": "DERIVABLE", "skill_to_recruitment_evidence": "SUPPORTED", "skill_to_skill_pmi": "SUPPORTED", "skill_prerequisite_edges": "NOT_SUPPORTED",
        },
        "domain_skill_profiles_count": len(domain_profiles.get("by_domain", domain_profiles if isinstance(domain_profiles, list) else {})),
        "pmi_parameters": pmi.get("parameters", {}),
        "community_source": communities.get("parameters", {}),
    }
    product_matches = [x for x in inventory["occupations"] if "产品经理" in x["occupation_label"] or "product manager" in x["occupation_label"].casefold()]
    product_comparison = [x for x in comparisons["candidates"] if x["occupation_key"] in {p["occupation_key"] for p in product_matches}]
    product_report = {"matched_occupation_records": [{"occupation": x["occupation_label"], "mapped": x["mapped"], "canonical_occupation_id": x["canonical_occupation_id"], "job_group_count": x["job_group_count"], "contexts": x["contexts"], "recruitment_evidence_count": x["recruitment_evidence_count"], "completed_inference_group_count": x["completed_inference_group_count"], "skill_count": x["normalized_unique_skill_count"]} for x in product_matches], "comparison_candidates": product_comparison, "eligibility": bool(product_comparison)}
    summary = {
        "audit_type": "job_market_intelligence_data_feasibility",
        "population": {"selected_groups": len(selected), "completed_inference_groups": result_statuses.get("completed", 0), "inference_status_counts": dict(result_statuses), "distinct_occupation_identities": len(inventory["occupations"]), "mapped_occupation_count": inventory["mapped_occupation_count"], "unmapped_occupation_count": inventory["unmapped_occupation_count"], "context_count_distribution": dict(context_distribution), "mapped_unmapped_distribution": dict(mapped_context)},
        "cross_context_comparison": {"eligible_count": comparisons["eligible_count"], "eligibility_rule": comparisons["eligibility_rule"]},
        "product_manager": product_report,
        "demo_occupations": demos,
        "skill_map_feasibility": skill_map,
        "limitations": ["The selective-1000 population is not equally representative of every occupation or industry.", "Unmapped labels are retained as candidate labels and are not canonical occupations.", "Inferred skills are candidate skills inferred from Job Group context, not direct job-ad requirements.", "PMI indicates co-occurrence association, not prerequisite or learning order.", "Louvain communities indicate network structure, not a curriculum sequence."],
        "api_calls": 0,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "feasibility_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "occupation_inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "comparison_candidates.json").write_text(json.dumps(comparisons, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "demo_occupations.json").write_text(json.dumps({"occupations": demos, "product_manager": product_report}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "skill_map_feasibility.json").write_text(json.dumps(skill_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Job Market Intelligence — Data Feasibility Audit", "", "## Direct conclusion", "", f"The frozen selective-1000 evidence can support a Job Market Intelligence MVP with bounded evidence labels. It contains {len(inventory['occupations'])} occupation identity records ({inventory['mapped_occupation_count']} mapped canonical and {inventory['unmapped_occupation_count']} unmapped candidate labels) and {comparisons['eligible_count']} conservative cross-context comparison candidates.", "", "## Population", "", f"- Selective groups: {len(selected)}; completed inference groups: {result_statuses.get('completed', 0)}.", f"- Context distribution: {dict(context_distribution)}.", f"- Mapped/unmapped occupation records: {dict(mapped_context)}.", "", "## Cross-context comparison", "", f"Eligibility requires ≥2 contexts, completed inference and recruitment evidence in each context, ≥3 normalized skills per context, plus both shared and distinctive skills. Eligible occupations: **{comparisons['eligible_count']}**.", "", "## Product Manager / 产品经理", ""]
    if product_matches:
        for item in product_matches: lines.append(f"- {item['occupation_label']}: {'mapped' if item['mapped'] else 'unmapped candidate label'}, {item['job_group_count']} groups, {len(item['contexts'])} contexts, {item['recruitment_evidence_count']} recruitment evidence units, {item['normalized_unique_skill_count']} skills.")
        lines.append(f"- Cross-context comparison eligible: **{'yes' if product_comparison else 'no'}**.")
    else: lines.append("- No Product Manager / 产品经理 occupation identity record was found in the selective-1000 evidence; it should not be fabricated as a demo.")
    lines += ["", "## Deterministic demo candidates", ""]
    for item in demos: lines.append(f"- {item['occupation']}: {len(item['contexts'])} contexts, evidence {item['evidence_volume']}, {item['skill_count']} skills, shared {len(item['shared_skills'])}, distinctive {sum(len(v) for v in item['distinctive_skills_by_context'].values())}.")
    lines += ["", "## Skill-map feasibility", "", f"- Usable normalized skill nodes: {skill_map['usable_skill_node_count']}", f"- Frozen global PMI edges: {skill_map['usable_global_pmi_edge_count']}", f"- Frozen Louvain communities: {skill_map['louvain_community_count']}", "- Supported: skill↔skill global PMI, community→skills, skill→recruitment evidence.", "- Derivable: occupation→skills, occupation→communities, context→domain-specific skills, occupation/context-specific co-occurrence.", "- Not supported: prerequisite or learning-order edges.", "", "## Limitations and product boundary", ""] + [f"- {x}" for x in summary["limitations"]] + ["", "This audit performs no LLM calls and does not alter any frozen upstream artifact."]
    REPORT.parent.mkdir(parents=True, exist_ok=True); REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"occupations": len(inventory["occupations"]), "mapped": inventory["mapped_occupation_count"], "unmapped": inventory["unmapped_occupation_count"], "comparison_candidates": comparisons["eligible_count"], "demo_count": len(demos), "pmi_edges": len(pmi.get("relationships", [])), "communities": len(communities.get("communities", [])), "api_calls": 0}, ensure_ascii=False))

if __name__ == "__main__": main()
