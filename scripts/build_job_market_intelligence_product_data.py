"""Build deterministic frontend-ready Job Market Intelligence product data."""
from __future__ import annotations
import hashlib, itertools, json, sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, "backend")
from app.domain.job_market.feasibility import build_comparison_candidates, build_occupation_inventory

ROOT = Path("data/processed")
SELECTED = ROOT / "skill_inference_v2/selective_mini_1000/selected_inputs.jsonl"
RESULTS = ROOT / "skill_inference_v2/selective_mini_1000/results.jsonl"
NORMALIZATION = ROOT / "skill_inference_v2/selective_mini_1000/normalization_v2_comparison.jsonl"
PROFILE = ROOT / "skill_demand_profile/skill_demand_profile.json"
PMI = ROOT / "skill_demand_profile/skill_cooccurrence_pmi.json"
COMMUNITIES = ROOT / "skill_demand_profile/skill_communities.json"
OUT = ROOT / "job_market_intelligence/product"
REPORT = Path("docs/reports/job-market-intelligence-product-data-layer.md")
VERSION = "job-market-product-v1"

def read_jsonl(path): return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
def stable(prefix, value): return prefix + hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
def evidence_strength(evidence, groups):
    if evidence >= 10 and groups >= 3: return "strong"
    if evidence >= 3 or groups >= 1: return "moderate"
    return "limited"

def main():
    selected = read_jsonl(SELECTED); results = {x["job_group_id"]: x for x in read_jsonl(RESULTS)}
    normalization = {(x["job_group_id"], x["raw_skill_name"]): x["v2_normalized_skill"] for x in read_jsonl(NORMALIZATION)}
    if len(selected) != 1000: raise SystemExit("product builder requires the frozen selective-1000 input")
    inventory = build_occupation_inventory(selected, results); comparison = build_comparison_candidates(inventory)
    profile = json.loads(PROFILE.read_text(encoding="utf-8")); pmi = json.loads(PMI.read_text(encoding="utf-8")); communities = json.loads(COMMUNITIES.read_text(encoding="utf-8"))
    community_by_skill = defaultdict(list)
    for community in communities.get("communities", []):
        for skill in community.get("member_skills", []): community_by_skill[skill].append(community["community_id"])
    group_to_occ = {}; occ_groups = defaultdict(list); occ_context_groups = defaultdict(lambda: defaultdict(list))
    for group in selected:
        prepared = group["prepared_inference_input"]; cid = prepared.get("canonical_occupation_id")
        key = f"canonical:{cid}" if cid else f"candidate:{group.get('representative_title','').strip().casefold()}"
        display = prepared.get("canonical_occupation_title") or group.get("representative_title", "")
        oid = cid or stable("candidate-", display.casefold())
        context = prepared.get("industry_domain_context") or "unknown"
        group_to_occ[group["job_group_id"]] = (key, oid, display, context); occ_groups[key].append(group); occ_context_groups[key][context].append(group)
    result_by_occ_skill = defaultdict(lambda: defaultdict(lambda: {"groups": set(), "evidence": 0, "types": set(), "scopes": set(), "contexts": set()}))
    for group in selected:
        key, oid, display, context = group_to_occ[group["job_group_id"]]; result = results.get(group["job_group_id"], {})
        evidence = len(group["prepared_inference_input"].get("source_recruitment_record_ids", [])) or int(group.get("occurrence_count", 0) or 0)
        for skill in result.get("hard_skills", []) + result.get("soft_skills", []):
            name = normalization.get((group["job_group_id"], skill.get("raw_skill_name", "")), skill.get("normalized_skill_name") or skill.get("normalized_skill"))
            if not name: continue
            item = result_by_occ_skill[key][name]; item["groups"].add(group["job_group_id"]); item["evidence"] += evidence; item["types"].add(skill.get("skill_type")); item["scopes"].add(skill.get("skill_scope")); item["contexts"].add(context)
    pmi_by_skill = defaultdict(list)
    for edge in pmi.get("relationships", []):
        pmi_by_skill[edge["skill_a"]].append({"skill": edge["skill_b"], "pmi": edge["pmi"], "supporting_job_group_count": edge["supporting_job_group_count"], "edge_type": "global_pmi"})
        pmi_by_skill[edge["skill_b"]].append({"skill": edge["skill_a"], "pmi": edge["pmi"], "supporting_job_group_count": edge["supporting_job_group_count"], "edge_type": "global_pmi"})
    catalog = []; details = {}; contexts_out = {}; all_skills = defaultdict(lambda: {"groups": set(), "evidence": 0, "types": set(), "scopes": set(), "contexts": set(), "occupation_ids": set()})
    eligible_keys = {x["occupation_key"] for x in comparison["candidates"]}
    for item in inventory["occupations"]:
        key = item["occupation_key"]; groups = occ_groups[key]; oid = group_to_occ[groups[0]["job_group_id"]][1]; display = item["occupation_label"]
        skill_objects = []
        for skill, metrics in sorted(result_by_occ_skill[key].items()):
            skill_objects.append({"skill_id": stable("skill-", skill.casefold()), "display_name": skill, "skill_type": sorted(metrics["types"]), "scope": sorted(metrics["scopes"]), "supporting_group_count": len(metrics["groups"]), "recruitment_evidence_count": metrics["evidence"], "contexts": sorted(metrics["contexts"]), "community_ids": sorted(community_by_skill.get(skill, [])), "global_pmi_relationships": pmi_by_skill.get(skill, [])[:20], "evidence_references": {"job_group_ids": sorted(metrics["groups"])[:20], "source": "selective_mini_1000/results.jsonl", "inference_source": "llm_inference", "normalization_version": "skill-normalization-v2"}})
            agg = all_skills[skill]; agg["groups"].update(metrics["groups"]); agg["evidence"] += metrics["evidence"]; agg["types"].update(metrics["types"]); agg["scopes"].update(metrics["scopes"]); agg["contexts"].update(metrics["contexts"]); agg["occupation_ids"].add(oid)
        context_objects = []
        for context, cgroups in sorted(occ_context_groups[key].items()):
            skill_names = set(); core = set(); domain = set(); evidence = 0; completed = 0
            for group in cgroups:
                evidence += len(group["prepared_inference_input"].get("source_recruitment_record_ids", [])) or int(group.get("occurrence_count", 0) or 0)
                result = results.get(group["job_group_id"], {}); completed += int(result.get("inference_status") == "completed")
                for skill in result.get("hard_skills", []) + result.get("soft_skills", []):
                    name = normalization.get((group["job_group_id"], skill.get("raw_skill_name", "")), skill.get("normalized_skill_name") or skill.get("normalized_skill"))
                    if name: skill_names.add(name); (core if skill.get("skill_scope") == "occupation_core" else domain).add(name)
            context_id = stable("context-", oid + "|" + context)
            contexts_out[context_id] = {"context_id": context_id, "context_name": context, "occupation_id": oid, "job_group_ids": [g["job_group_id"] for g in cgroups], "completed_inference_group_count": completed, "recruitment_evidence_count": evidence, "normalized_skills": sorted(skill_names), "occupation_core_skills": sorted(core), "domain_specific_skills": sorted(domain), "evidence_strength": evidence_strength(evidence, completed), "evidence_references": {"job_group_ids": [g["job_group_id"] for g in cgroups][:20]}}
            context_objects.append(contexts_out[context_id])
        catalog.append({"occupation_id": oid, "display_name": display, "identity_type": "mapped" if item["mapped"] else "unmapped", "canonical_id": item["canonical_occupation_id"], "job_group_count": len(groups), "completed_group_count": item["completed_inference_group_count"], "context_count": len(context_objects), "recruitment_evidence_count": item["recruitment_evidence_count"], "unique_skill_count": len(skill_objects), "hard_skill_count": item["hard_skill_count"], "soft_skill_count": item["soft_skill_count"], "comparison_eligible": key in eligible_keys, "evidence_strength": evidence_strength(item["recruitment_evidence_count"], item["completed_inference_group_count"]), "searchable_aliases": sorted({g.get("representative_title", "") for g in groups if g.get("representative_title")}), "provenance": {"grouping_version": "job-grouping-v2-occupation-safe", "inference_version": "skill-inference-v2", "normalization_version": "skill-normalization-v2", "source_job_group_ids": [g["job_group_id"] for g in groups][:50]}})
        details[oid] = {"occupation": catalog[-1], "market_summary": {"recruitment_evidence_count": item["recruitment_evidence_count"], "job_group_count": len(groups), "completed_inference_group_count": item["completed_inference_group_count"], "context_count": len(context_objects), "skill_count": len(skill_objects)}, "skills": skill_objects, "contexts": context_objects}
    skill_catalog = []
    for name, metrics in sorted(all_skills.items()):
        skill_catalog.append({"skill_id": stable("skill-", name.casefold()), "display_name": name, "skill_type": sorted(metrics["types"]), "scope": sorted(metrics["scopes"]), "supporting_group_count": len(metrics["groups"]), "recruitment_evidence_count": metrics["evidence"], "contexts": sorted(metrics["contexts"]), "community_ids": sorted(community_by_skill.get(name, [])), "global_pmi_relationships": pmi_by_skill.get(name, [])[:20], "evidence_references": {"job_group_ids": sorted(metrics["groups"])[:20], "inference_source": "llm_inference", "normalization_version": "skill-normalization-v2"}})
    graph_nodes = []; graph_edges = []
    for item in catalog: graph_nodes.append({"node_id": item["occupation_id"], "node_type": "occupation_root", "label": item["display_name"], "metadata": {"identity_type": item["identity_type"], "evidence_strength": item["evidence_strength"]}})
    for skill in skill_catalog: graph_nodes.append({"node_id": skill["skill_id"], "node_type": "skill", "label": skill["display_name"], "skill_type": skill["skill_type"], "scope": skill["scope"], "community_id": skill["community_ids"], "metadata": {"evidence_strength": evidence_strength(skill["recruitment_evidence_count"], skill["supporting_group_count"]), "supporting_group_count": skill["supporting_group_count"]}})
    for community in communities.get("communities", []): graph_nodes.append({"node_id": community["community_id"], "node_type": "skill_community", "label": f"Skill Cluster {str(community['community_id']).split('-')[-1]}", "metadata": {"ui_fallback_label": True, "member_count": community.get("skill_count", len(community.get("member_skills", [])))}})
    for item in details.values():
        oid = item["occupation"]["occupation_id"]
        for skill in item["skills"]: graph_edges.append({"edge_id": stable("edge-", oid + "|" + skill["skill_id"]), "source": oid, "target": skill["skill_id"], "edge_type": "occupation_has_skill", "evidence": {"supporting_group_count": skill["supporting_group_count"]}, "provenance": "deterministic from completed selective inference"})
    for skill in skill_catalog:
        for community_id in skill["community_ids"]: graph_edges.append({"edge_id": stable("edge-", community_id + "|" + skill["skill_id"]), "source": community_id, "target": skill["skill_id"], "edge_type": "community_contains_skill", "weight": 1, "evidence": {"community_id": community_id}, "provenance": "frozen Louvain community"})
    for edge in pmi.get("relationships", []):
        a = stable("skill-", edge["skill_a"].casefold()); b = stable("skill-", edge["skill_b"].casefold()); graph_edges.append({"edge_id": stable("edge-", "pmi|" + a + "|" + b), "source": a, "target": b, "edge_type": "skill_pmi_related_to_skill", "weight": edge["pmi"], "evidence": {"supporting_job_group_count": edge["supporting_job_group_count"], "weighted_evidence_count": edge.get("weighted_evidence_count")}, "provenance": "global market co-occurrence; not prerequisite or causal"})
    for context_id, context in contexts_out.items():
        for skill in context["domain_specific_skills"]: graph_edges.append({"edge_id": stable("edge-", context_id + "|" + stable("skill-", skill.casefold())), "source": context_id, "target": stable("skill-", skill.casefold()), "edge_type": "context_has_domain_skill", "evidence": {"recruitment_evidence_count": context["recruitment_evidence_count"]}, "provenance": "deterministic context aggregation"})
    comparison_data = []
    for candidate in comparison["candidates"]:
        detail = details.get(next((x["occupation_id"] for x in catalog if x["occupation_id"] == (next((g["canonical_occupation_id"] for g in selected if False), None))), None))
        occ = next((x for x in catalog if x["display_name"] == candidate["occupation_label"] and x["comparison_eligible"]), None)
        if not occ: occ = next((x for x in catalog if x["comparison_eligible"] and x["occupation_id"].startswith("candidate-") and x["display_name"] == candidate["occupation_label"]), None)
        if not occ: continue
        ctxmap = {c["context_name"]: c for c in details[occ["occupation_id"]]["contexts"]}; pairs = []
        for a, b in itertools.combinations(sorted(ctxmap), 2):
            sa, sb = set(ctxmap[a]["normalized_skills"]), set(ctxmap[b]["normalized_skills"]); pairs.append({"context_a": ctxmap[a]["context_id"], "context_b": ctxmap[b]["context_id"], "shared_skills": sorted(sa & sb), "context_a_distinctive_skills": sorted(sa - sb), "context_b_distinctive_skills": sorted(sb - sa), "context_a_evidence_count": ctxmap[a]["recruitment_evidence_count"], "context_b_evidence_count": ctxmap[b]["recruitment_evidence_count"]})
        comparison_data.append({"occupation_id": occ["occupation_id"], "occupation_name": occ["display_name"], "contexts": [c["context_id"] for c in ctxmap.values()], "context_pairs": pairs, "eligibility_rule": comparison["eligibility_rule"]})
    product_manager = next((x for x in catalog if x["canonical_id"] == "OCC0289"), None)
    pm_detail = details.get(product_manager["occupation_id"]) if product_manager else None
    pm_compare = next((x for x in comparison_data if x["occupation_id"] == product_manager["occupation_id"]), None) if product_manager else None
    product_manager_demo = {"occupation": pm_detail, "skill_graph": {"nodes": [n for n in graph_nodes if n["node_id"] == product_manager["occupation_id"] or n["node_id"] in {s["skill_id"] for s in pm_detail["skills"]}], "edges": [e for e in graph_edges if e["source"] == product_manager["occupation_id"] or e["target"] in {s["skill_id"] for s in pm_detail["skills"]}]}, "comparison": pm_compare, "evidence_drawer_contract": {"skill_references": "occupation detail skills.evidence_references", "market_source": "selective_mini_1000/results.jsonl"}}
    manifest = {"product_data_version": VERSION, "generated_at": datetime.now(timezone.utc).isoformat(), "source_dataset": "2026 recruitment selective-mini-1000", "source_versions": {"grouping": "job-grouping-v2-occupation-safe", "inference": "skill-inference-v2", "normalization": "skill-normalization-v2", "taxonomy": "mvp-taxonomy-v4.1-frozen"}, "occupation_count": len(catalog), "mapped_occupation_count": sum(x["identity_type"] == "mapped" for x in catalog), "unmapped_occupation_count": sum(x["identity_type"] == "unmapped" for x in catalog), "comparison_eligible_count": len(comparison_data), "skill_count": len(skill_catalog), "global_pmi_edge_count": len(pmi.get("relationships", [])), "community_count": len(communities.get("communities", [])), "hero_demo_occupation": "OCC0289", "limitations": ["Selective-1000 is not full 15,622-group inference coverage.", "Unmapped labels are candidate labels, not canonical taxonomy occupations.", "PMI and communities are global market structure, not prerequisite order."]}
    OUT.mkdir(parents=True, exist_ok=True)
    outputs = {"occupation_catalog.json": {"occupations": catalog}, "occupation_details.json": {"occupations": details}, "context_catalog.json": {"contexts": contexts_out}, "comparison_data.json": {"comparisons": comparison_data}, "skill_catalog.json": {"skills": skill_catalog}, "skill_graph.json": {"nodes": graph_nodes, "edges": graph_edges, "edge_semantics": {"global_pmi": "co-occurrence only", "occupation_has_skill": "deterministic aggregation", "context_has_domain_skill": "deterministic aggregation"}}, "product_manager_demo.json": product_manager_demo, "manifest.json": manifest}
    for name, value in outputs.items(): (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Job Market Intelligence Product Data Layer", "", "Deterministic, read-only product artifacts derived from frozen selective-1000 market data. No upstream analysis is rerun.", "", f"- Occupations: {len(catalog)} ({manifest['mapped_occupation_count']} mapped, {manifest['unmapped_occupation_count']} unmapped)", f"- Comparison-eligible occupations: {len(comparison_data)}", f"- Skills: {len(skill_catalog)}", f"- Graph nodes / edges: {len(graph_nodes)} / {len(graph_edges)}", f"- PMI edges: {manifest['global_pmi_edge_count']}; Louvain communities: {manifest['community_count']}", "", "## Semantics", "", "PMI edges are global market co-occurrence relationships, not prerequisites or learning order. Louvain labels are UI fallback labels only. Occupation/context edges are deterministic derivations from completed inference groups.", "", "## Product Manager hero demo", "", f"OCC0289 is {'available' if product_manager_demo['occupation'] else 'not available'} with {len(pm_detail['contexts']) if pm_detail else 0} contexts and {len(pm_detail['skills']) if pm_detail else 0} skills; its detail, graph subset, context comparison and evidence references are in `product_manager_demo.json`.", "", "## Limitations", "", "- Selective-1000 is not complete 15,622-group inference coverage.", "- Unmapped records remain candidate labels and must not be presented as canonical occupations.", "- No unsupported prerequisite/causal edges are generated."]
    REPORT.parent.mkdir(parents=True, exist_ok=True); REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"occupations": len(catalog), "comparison_eligible": len(comparison_data), "skills": len(skill_catalog), "graph_nodes": len(graph_nodes), "graph_edges": len(graph_edges), "api_calls": 0}, ensure_ascii=False))

if __name__ == "__main__": main()
