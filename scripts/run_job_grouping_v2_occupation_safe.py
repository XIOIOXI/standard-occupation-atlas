"""Create a versioned v2 Job Group run from audited SAFE occupation families only."""
from __future__ import annotations

import argparse, hashlib, json, statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from app.domain.taxonomy.coverage import normalise_title
from app.infrastructure.sqlite_job_group_repository import SqliteJobGroupRepository

VERSION = "job-grouping-v2-occupation-safe"


def v2_key(source_group: dict, safe_by_v1_group: dict[str, dict]) -> tuple[str, str | None]:
    family = safe_by_v1_group.get(source_group["job_group_id"])
    if not family:
        return f"passthrough:{source_group['job_group_id']}", None
    # Existing v1 industry compatibility is deliberately retained: a family never crosses it.
    return f"safe:{family['candidate_family_id']}|{source_group['industry_domain_context']}", family["candidate_family_id"]


def group_id(key: str) -> str:
    return "JG2-" + hashlib.sha256((VERSION + "|" + key).encode()).hexdigest()[:16]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v1-groups", type=Path, required=True)
    parser.add_argument("--v1-members", type=Path, required=True)
    parser.add_argument("--v1-summary", type=Path, required=True)
    parser.add_argument("--safety-details", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    v1_groups = [json.loads(line) for line in args.v1_groups.read_text(encoding="utf-8").splitlines() if line]
    v1_members = [json.loads(line) for line in args.v1_members.read_text(encoding="utf-8").splitlines() if line]
    v1_summary = json.loads(args.v1_summary.read_text(encoding="utf-8"))
    safety = [json.loads(line) for line in args.safety_details.read_text(encoding="utf-8").splitlines() if line]
    safe_families = [family for family in safety if family["audit_classification"] == "SAFE" and family["confidence_for_review"] == "high"]
    safe_by_v1_group = {group_id: family for family in safe_families for group_id in family["source_job_group_ids"]}
    if len(safe_by_v1_group) != sum(family["member_group_count"] for family in safe_families):
        raise ValueError("SAFE source v1 Job Groups are not uniquely assigned")
    members_by_v1 = defaultdict(list)
    for member in v1_members:
        members_by_v1[member["job_group_id"]].append(member)
    buckets = defaultdict(list)
    for source in v1_groups:
        key, family_id = v2_key(source, safe_by_v1_group)
        buckets[key].append((source, family_id))
    v2_groups, v2_members = [], []
    for key, entries in sorted(buckets.items()):
        source_groups = [entry[0] for entry in entries]
        family_id = entries[0][1]
        gid = group_id(key)
        member_rows = [member for source in source_groups for member in members_by_v1[source["job_group_id"]]]
        for member in member_rows:
            copied = {**member, "source_v1_job_group_id": member["job_group_id"], "job_group_id": gid, "grouping_version": VERSION}
            v2_members.append(copied)
        titles = Counter(member["job_title_unit"] for member in member_rows)
        representative = sorted(titles, key=lambda title: (-titles[title], title))[0]
        source_ids = sorted(source["job_group_id"] for source in source_groups)
        company_distribution = dict(sorted(Counter(member["company_name"] for member in member_rows if member.get("company_name")).items()))
        canonical_ids = {source.get("canonical_occupation_id") for source in source_groups if source.get("canonical_occupation_id")}
        if len(canonical_ids) > 1:
            raise ValueError("Incompatible canonical identities in a v2 group")
        is_safe_merge = family_id is not None
        v2_groups.append({
            "job_group_id": gid,
            "grouping_version": VERSION,
            "occupation_identity_family_id": family_id,
            "canonical_occupation_id": next(iter(canonical_ids), None),
            "canonical_occupation_title": source_groups[0].get("canonical_occupation_title") if canonical_ids else None,
            "representative_title": representative,
            "normalized_titles": sorted({normalise_title(member["job_title_unit"]) for member in member_rows}),
            "industry_domain_context": source_groups[0]["industry_domain_context"],
            "industry_contexts": sorted({source["industry_domain_context"] for source in source_groups}),
            "occurrence_count": len(member_rows),
            "member_count": len(member_rows),
            "company_count": len(company_distribution),
            "company_distribution": company_distribution,
            "location_count": len({member["location"] for member in member_rows if member.get("location")}),
            "original_job_titles": sorted({member["raw_job_title"] for member in member_rows}),
            "source_v1_job_group_ids": source_ids,
            "source_recruitment_record_ids": sorted({member["source_record_id"] for member in member_rows}),
            "source_atomic_unit_ids": sorted({member["source_atomic_unit_id"] for member in member_rows}),
            "taxonomy_mapping_status": "mapped" if canonical_ids else "unmapped",
            "grouping_method": "safe_occupation_identity_and_existing_industry_context" if is_safe_merge else "v1_passthrough_not_safe_for_merge",
            "merge_provenance": {"audit_status": "SAFE", "candidate_family_id": family_id, "source_grouping_version": "job-grouping-v1"} if is_safe_merge else {"audit_status": "NOT_APPLIED", "source_grouping_version": "job-grouping-v1"},
            "merge_confidence": "high" if is_safe_merge else None,
            "merge_audit_status": "SAFE" if is_safe_merge else "NOT_APPLIED",
        })
    sizes = [group["member_count"] for group in v2_groups]
    source_v1_ids = [group_id for group in v2_groups for group_id in group["source_v1_job_group_ids"]]
    v1_record_ids = {member["source_record_id"] for member in v1_members}
    v2_record_ids = {member["source_record_id"] for member in v2_members}
    v1_atomic_ids = {member["source_atomic_unit_id"] for member in v1_members}
    v2_atomic_ids = {member["source_atomic_unit_id"] for member in v2_members}
    applied_families = {group["occupation_identity_family_id"] for group in v2_groups if group["occupation_identity_family_id"]}
    summary = {
        "snapshot_id": v1_summary["snapshot_id"], "grouping_version": VERSION, "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_grouping_version": "job-grouping-v1", "v1_job_group_count": len(v1_groups), "job_group_count": len(v2_groups),
        "reduction_from_v1": len(v1_groups) - len(v2_groups), "singleton_group_count": sum(size == 1 for size in sizes),
        "mapped_job_group_count": sum(group["taxonomy_mapping_status"] == "mapped" for group in v2_groups), "unmapped_job_group_count": sum(group["taxonomy_mapping_status"] == "unmapped" for group in v2_groups),
        "average_members_per_group": round(sum(sizes) / len(sizes), 4), "median_members_per_group": statistics.median(sizes),
        "groups_over_10_members": sum(size > 10 for size in sizes), "groups_over_50_members": sum(size > 50 for size in sizes),
        "safe_family_count_available": len(safe_families), "safe_family_count_applied": len(applied_families),
        "theoretical_cross_industry_agnostic_count": 12957,
        "validation": {
            "review_required_families_applied": False,
            "no_cross_industry_context_merge": all(len(group["industry_contexts"]) == 1 for group in v2_groups),
            "source_v1_job_group_ids_unique": len(source_v1_ids) == len(set(source_v1_ids)) == len(v1_groups),
            "atomic_unit_coverage_equal": v1_atomic_ids == v2_atomic_ids,
            "recruitment_record_coverage_equal": v1_record_ids == v2_record_ids,
            "safe_family_count_matches_audit": len(applied_families) == len(safe_families),
            "taxonomy_modified": False, "skill_inference_executed": False,
        },
    }
    repo = SqliteJobGroupRepository(args.database)
    repo.save(summary["snapshot_id"], VERSION, summary, v2_groups, v2_members)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for filename, rows in (("job_groups.jsonl", v2_groups), ("job_group_members.jsonl", v2_members)):
        (args.output_dir / filename).write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
    (args.output_dir / "job_group_v2_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    largest = sorted(v2_groups, key=lambda group: (-group["member_count"], group["job_group_id"]))[:30]
    safe_samples = sorted([group for group in v2_groups if group["merge_audit_status"] == "SAFE"], key=lambda group: hashlib.sha256(group["job_group_id"].encode()).hexdigest())[:100]
    audit_rows = [{"sample_set": "largest_30", **group} for group in largest] + [{"sample_set": "safe_deterministic_100", **group} for group in safe_samples]
    (args.output_dir / "job_group_v2_audit_samples.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in audit_rows) + "\n", encoding="utf-8")
    lines = ["# Job Grouping v2 — Occupation-safe", "", "Only high-confidence candidate families classified SAFE by the merge-safety audit were applied. v1 remains unchanged.", "", f"- v1 → v2 groups: {len(v1_groups):,} → {len(v2_groups):,} (reduction {summary['reduction_from_v1']:,})", f"- SAFE families applied: {len(applied_families):,}", f"- Singleton / mapped / unmapped: {summary['singleton_group_count']:,} / {summary['mapped_job_group_count']:,} / {summary['unmapped_job_group_count']:,}", f"- Atomic / record lineage preserved: {summary['validation']['atomic_unit_coverage_equal']} / {summary['validation']['recruitment_record_coverage_equal']}", "", "## Largest v2 groups", "", "| Title | Members | Source v1 groups | Merge status | Industry context |", "|---|---:|---:|---|---|"]
    for group in largest[:20]:
        lines.append(f"| {group['representative_title']} | {group['member_count']} | {len(group['source_v1_job_group_ids'])} | {group['merge_audit_status']} | {group['industry_domain_context']} |")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
