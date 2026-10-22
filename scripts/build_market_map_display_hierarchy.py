"""Build a read-only display hierarchy from existing Market Map data.

This is a UI projection only. It neither reruns the Market Map pipeline nor
modifies frozen artifacts, identity decisions, or skill inference outputs.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data/processed/job_market_intelligence/market_map"
GROUPS = ROOT / "data/processed/job_groups_v2/job_groups.jsonl"
FAMILIES = ROOT / "data/processed/occupation_identity/occupation_candidate_families.jsonl"
OUT = MARKET / "display_hierarchy.json"
VERSION = "market-map-display-hierarchy-v1"
DEMAND_METRIC = "distinct_recruitment_record_count"
L0_PAGE_SIZE, L1_PAGE_SIZE, L2_PAGE_SIZE = 12, 12, 25


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def context_id(label: str) -> str:
    return "context:" + label


def main() -> None:
    catalog = read_json(MARKET / "market_occupations.json")["occupations"]
    summary = read_json(MARKET / "market_map_summary.json")
    groups = read_jsonl(GROUPS)
    families = read_jsonl(FAMILIES)

    by_group = {group["job_group_id"]: group for group in groups}
    occupation_by_group = {}
    occupations = {occupation["occupation_id"]: occupation for occupation in catalog}
    for occupation in catalog:
        for group_id in occupation["source_references"]["job_group_ids"]:
            if group_id in occupation_by_group:
                raise ValueError(f"Job Group appears under two occupation identities: {group_id}")
            occupation_by_group[group_id] = occupation["occupation_id"]
    if set(occupation_by_group) != set(by_group):
        raise ValueError("Display hierarchy requires every Market Map Job Group exactly once")

    family_by_v1_group = {
        source_id: family["candidate_family_id"]
        for family in families
        for source_id in family["source_job_group_ids"]
    }

    groups_by_context = defaultdict(list)
    groups_by_context_occupation = defaultdict(lambda: defaultdict(list))
    for group in groups:
        label = group["industry_domain_context"]
        groups_by_context[label].append(group)
        groups_by_context_occupation[label][occupation_by_group[group["job_group_id"]]].append(group)

    def record_count(group_rows):
        return len({record_id for group in group_rows for record_id in group["source_recruitment_record_ids"]})

    def node_for_context(label: str):
        rows = groups_by_context[label]
        return {
            "node_id": context_id(label),
            "label": label.split(":", 1)[1] if ":" in label else label,
            "source_context": label,
            "classification": "taxonomy_domain" if label.startswith("l1:") else "raw_source_context",
            "demand_metric": DEMAND_METRIC,
            "recruitment_evidence_count": record_count(rows),
            "job_group_count": len(rows),
            "occupation_count": len(groups_by_context_occupation[label]),
        }

    standardized_contexts = sorted(
        (label for label in groups_by_context if label.startswith("l1:")),
        key=lambda label: (-record_count(groups_by_context[label]), label),
    )
    raw_contexts = sorted(
        (label for label in groups_by_context if not label.startswith("l1:")),
        key=lambda label: (-record_count(groups_by_context[label]), label),
    )
    raw_rows = [group for label in raw_contexts for group in groups_by_context[label]]
    level0 = [
        {
            "node_id": "major:standardized-domains",
            "label": "标准化行业域",
            "description": "已存在的 l1 industry/domain contexts",
            "child_level": "contexts",
            "classification": "source_context_prefix:l1",
            "demand_metric": DEMAND_METRIC,
            "recruitment_evidence_count": record_count([group for label in standardized_contexts for group in groups_by_context[label]]),
            "context_count": len(standardized_contexts),
        },
        {
            "node_id": "major:raw-source-contexts",
            "label": "原始来源分类",
            "description": "未标准化的 frozen source context labels",
            "child_level": "contexts",
            "classification": "source_context_prefix:raw",
            "demand_metric": DEMAND_METRIC,
            "recruitment_evidence_count": record_count(raw_rows),
            "context_count": len(raw_contexts),
        },
    ]

    occupation_lists = {}
    route_candidates = defaultdict(list)
    for label, by_occupation in groups_by_context_occupation.items():
        rows = []
        for occupation_id, occupation_groups in by_occupation.items():
            occupation = occupations[occupation_id]
            family_ids = sorted({
                family_by_v1_group.get(source_id)
                for group in occupation_groups
                for source_id in group["source_v1_job_group_ids"]
                if family_by_v1_group.get(source_id)
            })
            count = record_count(occupation_groups)
            row = {
                "node_id": occupation_id,
                "label": occupation["display_name"],
                "identity_type": occupation["identity_type"],
                "identity_uncertainty": occupation["identity_uncertainty"],
                "demand_metric": DEMAND_METRIC,
                "recruitment_evidence_count": count,
                "job_group_count": len(occupation_groups),
                "skill_intelligence_available": occupation["skill_intelligence_available"],
                "detail_file": occupation["detail_file"],
                "frozen_candidate_family_ids": family_ids,
                "source_context": label,
            }
            rows.append(row)
            route_candidates[occupation_id].append((count, label))
        occupation_lists[context_id(label)] = sorted(rows, key=lambda row: (-row["recruitment_evidence_count"], row["label"], row["node_id"]))

    search_index = []
    for occupation_id, candidates in sorted(route_candidates.items()):
        count, label = sorted(candidates, key=lambda item: (-item[0], item[1]))[0]
        parent = "major:standardized-domains" if label.startswith("l1:") else "major:raw-source-contexts"
        ordered = occupation_lists[context_id(label)]
        index = next(index for index, row in enumerate(ordered) if row["node_id"] == occupation_id)
        occupation = occupations[occupation_id]
        search_index.append({
            "occupation_id": occupation_id,
            "display_name": occupation["display_name"],
            "searchable_aliases": occupation["searchable_aliases"],
            "identity_type": occupation["identity_type"],
            "recruitment_evidence_count": occupation["recruitment_evidence_count"],
            "route": {"major_id": parent, "context_id": context_id(label), "occupation_page": index // L2_PAGE_SIZE},
        })

    output = {
        "schema_version": VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "demand_metric": DEMAND_METRIC,
        "display_budgets": {"level_0": L0_PAGE_SIZE, "level_1": L1_PAGE_SIZE, "level_2": L2_PAGE_SIZE},
        "levels": {
            "level_0": {"nodes": level0},
            "level_1": {
                "nodes_by_parent": {
                    "major:standardized-domains": [node_for_context(label) for label in standardized_contexts],
                    "major:raw-source-contexts": [node_for_context(label) for label in raw_contexts],
                },
            },
            "level_2": {"occupations_by_context": occupation_lists},
        },
        "search_index": search_index,
        "relationship_policy": {
            "rendered_hierarchy": "major source-context class -> frozen source context -> concrete occupation identity",
            "candidate_family_policy": "Frozen candidate family IDs are retained as L2 metadata only. They are cross-context, incomplete, and do not define a universal parent relationship for all occupation identities.",
            "canonical_policy": "Existing canonical occupation IDs remain concrete occupation identities; no new parent taxonomy is inferred.",
        },
        "limitations": [
            "Only two reliable major source-context classes are available: l1 taxonomy-domain labels and raw source labels.",
            "No frozen artifact supports a complete, non-overlapping occupation-family hierarchy across all 11,669 identities.",
            "Pagination controls display density; they do not remove occupations or change demand statistics.",
        ],
        "source_references": [
            {"path": path.relative_to(ROOT).as_posix(), "sha256": digest(path)}
            for path in (MARKET / "market_occupations.json", MARKET / "market_map_summary.json", GROUPS, FAMILIES)
        ],
        "validation": {
            "all_job_groups_accounted_for": len(occupation_by_group) == len(by_group),
            "market_job_group_count": summary["total_job_groups"],
            "api_calls": 0,
            "llm_calls": 0,
        },
    }
    OUT.write_text(json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({"level_0_nodes": len(level0), "standardized_contexts": len(standardized_contexts), "raw_contexts": len(raw_contexts), "searchable_occupations": len(search_index), "api_calls": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
