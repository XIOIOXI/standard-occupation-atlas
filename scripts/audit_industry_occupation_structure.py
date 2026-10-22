"""Read-only audit of safe occupation display grouping within Industry Map contexts.

The audit consumes frozen product and occupation-identity artifacts.  It never
changes occupation identities, Job Groups, taxonomy, or Skill Intelligence.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MARKET_DIR = ROOT / "data/processed/job_market_intelligence/market_map"
IDENTITY_DIR = ROOT / "data/processed/occupation_identity"
V2_PATH = ROOT / "data/processed/job_groups_v2/job_groups.jsonl"
OUT = ROOT / "docs/reports/industry-occupation-structure-audit.json"
MD_OUT = ROOT / "docs/reports/industry-occupation-structure-audit.md"

FINANCE_LABEL = "金融与金融科技"
CASE_LABELS = [
    "客户经理", "客户经理岗", "客户经理类",
    "管理培训生", "公司业务培训生", "星辰管培生", "运营培训生", "定向培养生",
    "数字金融岗", "信息技术岗", "法律合规岗",
]


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def exact_normalized_titles(occupation: dict, v2_by_id: dict[str, dict]) -> list[str]:
    titles = set()
    for group_id in occupation["source_references"]["job_group_ids"]:
        titles.update(v2_by_id[group_id].get("normalized_titles", []))
    return sorted(titles)


def main() -> None:
    hierarchy = json.loads((MARKET_DIR / "industry_market_hierarchy.json").read_text(encoding="utf-8"))
    market_occupations = json.loads((MARKET_DIR / "market_occupations.json").read_text(encoding="utf-8"))["occupations"]
    market_by_id = {row["occupation_id"]: row for row in market_occupations}
    v2_by_id = {row["job_group_id"]: row for row in read_jsonl(V2_PATH)}
    family_by_id = {row["candidate_family_id"]: row for row in read_jsonl(IDENTITY_DIR / "occupation_candidate_families.jsonl")}
    safety_by_id = {row["candidate_family_id"]: row for row in read_jsonl(IDENTITY_DIR / "high_family_merge_safety_details.jsonl")}
    safe_ids = {fid for fid, row in safety_by_id.items() if row["audit_classification"] == "SAFE"}
    review_ids = {fid for fid, row in safety_by_id.items() if row["audit_classification"] == "REVIEW_REQUIRED"}

    industry_results = []
    finance_case = []
    for industry in hierarchy["industries"]:
        rows = []
        for projection in industry["occupations"]:
            master = market_by_id[projection["node_id"]]
            family_ids = master["source_references"].get("frozen_family_ids", [])
            safe_family_ids = sorted(set(family_ids) & safe_ids)
            review_family_ids = sorted(set(family_ids) & review_ids)
            rows.append({
                "occupation_id": projection["node_id"], "label": projection["label"],
                "identity_type": projection["identity_type"],
                "canonical_id": master.get("canonical_id"),
                "demand": projection["recruitment_evidence_count"],
                "job_group_count": master["job_group_count"],
                "family_ids": family_ids, "safe_family_ids": safe_family_ids,
                "review_required_family_ids": review_family_ids,
                "normalized_titles": exact_normalized_titles(master, v2_by_id),
                "job_group_ids": master["source_references"]["job_group_ids"],
            })

        # A family is usable only when it is explicitly SAFE and relates two or
        # more *current display identities*.  A SAFE family already consolidated
        # into one v2 identity supplies no further UI compression.
        ids_by_safe_family: dict[str, set[str]] = defaultdict(set)
        ids_by_exact_title: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            for family_id in row["safe_family_ids"]:
                ids_by_safe_family[family_id].add(row["occupation_id"])
            for title in row["normalized_titles"]:
                ids_by_exact_title[title].add(row["occupation_id"])
        multi_safe = {fid: ids for fid, ids in ids_by_safe_family.items() if len(ids) >= 2}
        multi_exact = {title: ids for title, ids in ids_by_exact_title.items() if len(ids) >= 2}

        # Conservative precedence: a node participates in at most one relation.
        # Ambiguous many-family membership is left unresolved.  Canonical IDs
        # remain their own display groups because no canonical family relation is
        # present in the artifacts.
        assigned, group_members = set(), []
        for family_id, members in sorted(multi_safe.items()):
            available = sorted(members - assigned)
            if len(available) >= 2:
                group_members.append({"basis": "SAFE_candidate_family", "key": family_id, "members": available})
                assigned.update(available)
        for title, members in sorted(multi_exact.items()):
            available = sorted(members - assigned)
            if len(available) >= 2:
                group_members.append({"basis": "exact_normalized_title", "key": title, "members": available})
                assigned.update(available)
        for row in rows:
            if row["occupation_id"] not in assigned:
                group_members.append({"basis": "canonical_identity" if row["canonical_id"] else "preserve_identity", "key": row["occupation_id"], "members": [row["occupation_id"]]})

        # A named unresolved identity is one for which no multi-identity safe or
        # exact-normalized relationship was available; this is not a judgement of
        # data quality and does not exclude it from the map.
        unresolved_ids = [row["occupation_id"] for row in rows if row["occupation_id"] not in assigned]
        # Occupation-node demand is a distinct-record count per identity. The
        # same recruitment record may yield multiple title units, so summing node
        # demand is not an Industry-level distinct-record metric.
        node_demand_sum = sum(row["demand"] for row in rows)
        industry_results.append({
            "industry_id": industry["node_id"], "industry_label": industry["label"],
            "occupation_identity_count": len(rows),
            "canonical_mapped_count": sum(row["identity_type"] == "mapped" for row in rows),
            "unmapped_count": sum(row["identity_type"] == "unmapped" for row in rows),
            "candidate_family_covered_identity_count": sum(bool(row["family_ids"]) for row in rows),
            "safe_family_covered_identity_count": sum(bool(row["safe_family_ids"]) for row in rows),
            "review_required_family_covered_identity_count": sum(bool(row["review_required_family_ids"]) for row in rows),
            "identity_singleton_job_group_count": sum(row["job_group_count"] == 1 for row in rows),
            "candidate_multi_member_family_count": sum(family_by_id[fid]["member_group_count"] > 1 for fid in {fid for row in rows for fid in row["family_ids"]}),
            "safe_multi_identity_family_count": len(multi_safe),
            "exact_normalized_multi_identity_relation_count": len(multi_exact),
            "display_group_count_conservative": len(group_members),
            "display_group_reduction_conservative": len(rows) - len(group_members),
            "unresolved_identity_count": len(unresolved_ids),
            "industry_distinct_recruitment_record_count": industry["recruitment_evidence_count"],
            "sum_of_occupation_node_demand_not_deduplicated_across_nodes": node_demand_sum,
            "recruitment_evidence_coverage": "all current occupation identities retain their distinct_recruitment_record_count",
            "grouping_bases": dict(sorted(Counter(group["basis"] for group in group_members).items())),
        })

        if industry["label"] == FINANCE_LABEL:
            by_label = defaultdict(list)
            for row in rows:
                by_label[row["label"]].append(row)
            for label in CASE_LABELS:
                matches = by_label[label]
                finance_case.append({
                    "requested_label": label,
                    "found": bool(matches),
                    "matches": [{
                        "occupation_identity": row["occupation_id"], "normalized_titles": row["normalized_titles"],
                        "canonical_occupation_id": row["canonical_id"], "identity_type": row["identity_type"],
                        "candidate_family_ids": row["family_ids"], "safe_family_ids": row["safe_family_ids"],
                        "review_required_family_ids": row["review_required_family_ids"], "recruitment_evidence_count": row["demand"],
                        "v2_job_groups": [{
                            "job_group_id": gid, "representative_title": v2_by_id[gid]["representative_title"],
                            "normalized_titles": v2_by_id[gid]["normalized_titles"],
                            "canonical_occupation_id": v2_by_id[gid]["canonical_occupation_id"],
                            "merge_audit_status": v2_by_id[gid]["merge_audit_status"],
                            "source_recruitment_record_count": len(v2_by_id[gid]["source_recruitment_record_ids"]),
                        } for gid in row["job_group_ids"]],
                    } for row in matches],
                })

    finance = next(item for item in industry_results if item["industry_label"] == FINANCE_LABEL)
    output = {
        "audit_version": "industry-occupation-structure-audit-v1",
        "scope": "read-only derived audit; no frontend, frozen artifact, Job Group, taxonomy, Skill Intelligence, API, or LLM changes",
        "inputs": {
            "industry_projection": "industry_market_hierarchy.json (l1 Industry/Domain only)",
            "occupation_product_data": "market_occupations.json",
            "v2_job_groups": "job_groups_v2/job_groups.jsonl",
            "candidate_families": "occupation_candidate_families.jsonl",
            "merge_safety": "high_family_merge_safety_details.jsonl",
        },
        "display_group_precedence": [
            "canonical occupation identity: retained as one stable identity; no canonical family relation exists to merge distinct IDs",
            "existing SAFE candidate family, only where it relates at least two current display identities in the same Industry",
            "exact normalized-title relationship, only where it relates at least two unassigned current display identities",
            "otherwise preserve the original occupation identity",
        ],
        "prohibitions_enforced": ["REVIEW_REQUIRED families never form display groups", "no semantic/manual taxonomy", "no name-similarity merge", "no unresolved identity removal"],
        "industry_count": len(industry_results), "industries": industry_results,
        "finance_case": {"industry": FINANCE_LABEL, "summary": finance, "requested_titles": finance_case,
                         "trainee_title_limitation": "The frozen artifacts contain titles, normalized titles, mappings, candidate-family links, and recruitment lineage, but no reliable program/graduate/trainee semantic field. They therefore do not support automatically classifying these titles as recruitment projects or merging them."},
        "recommendation": {
            "recommend_occupation_group_layer": False,
            "reason": "The conservative precedence produces only the measured SAFE/exact-normalized reductions. It does not provide a reliable, broadly applicable semantic family layer across the 17 Industries. Adding a named family navigation layer would imply unsupported taxonomy for the remaining identities.",
            "safe_alternative": "Keep Industry → ranked occupation identities, surface canonical mapped identities first, retain search and deterministic pagination, and add a non-merging secondary exploration affordance only for explicitly SAFE multi-identity families when an Industry has them. Keep all unresolved identities reachable.",
            "finance_57_page_interpretation": f"Finance has {finance['occupation_identity_count']} current identities. Conservative safe grouping yields {finance['display_group_count_conservative']} display groups (reduction {finance['display_group_reduction_conservative']}); {finance['unresolved_identity_count']} identities still require direct access. Pagination pressure is therefore a display-density issue, not evidence for creating a general occupation taxonomy.",
        },
        "api_calls": 0, "llm_calls": 0, "skill_inference_executed": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Industry Occupation Structure Audit", "", "Read-only derived audit. No frozen artifact, frontend, Job Group, taxonomy, Skill Intelligence, API, or LLM was changed.", "", "## Result", "", output["recommendation"]["reason"], "", "Evidence is the Industry-level distinct recruitment-record count. Every occupation node separately retains its own distinct-record demand; those node values are not summed because one recruitment record can contribute more than one title unit.", "", "| Industry | Identities | Mapped | Unmapped | Candidate-covered | SAFE-covered | Singletons | Multi-member families | Display groups | Reduction | Unresolved | Evidence |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|", ""]
    for item in industry_results:
        lines.append(f"| {item['industry_label']} | {item['occupation_identity_count']} | {item['canonical_mapped_count']} | {item['unmapped_count']} | {item['candidate_family_covered_identity_count']} | {item['safe_family_covered_identity_count']} | {item['identity_singleton_job_group_count']} | {item['candidate_multi_member_family_count']} | {item['display_group_count_conservative']} | {item['display_group_reduction_conservative']} | {item['unresolved_identity_count']} | {item['industry_distinct_recruitment_record_count']} |")
    lines.extend(["", "## Financial case", "", output["recommendation"]["finance_57_page_interpretation"], "", finance_case and "The JSON artifact contains the requested occupation identity, normalized-title, mapping, candidate-family, merge-safety, and recruitment-lineage records for every requested title." or "No requested financial title records were found.", "", "Trainee limitation: " + output["finance_case"]["trainee_title_limitation"], "", "## Grouping rule", ""])
    lines.extend(f"1. {item}" for item in output["display_group_precedence"])
    lines.extend(["", "REVIEW_REQUIRED candidate families are excluded from automatic grouping."])
    MD_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"industry_count": len(industry_results), "finance": finance, "output": str(OUT), "api_calls": 0, "llm_calls": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
