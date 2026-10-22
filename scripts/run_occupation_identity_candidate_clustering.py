"""Read-only candidate occupation-family generation for unmapped Job Groups."""
from __future__ import annotations

import argparse, hashlib, json
from collections import Counter, defaultdict
from pathlib import Path

from app.domain.job_groups.occupation_identity import (
    blocked_clusters, has_specialisation_conflict, medium_identity_key,
    specialisation_signals, strict_identity_key,
)

VERSION = "occupation-identity-candidate-v1"


def family_id(confidence: str, member_ids: list[str]) -> str:
    digest = hashlib.sha256((VERSION + "|" + confidence + "|" + "|".join(sorted(member_ids))).encode()).hexdigest()[:16]
    return f"OCF-{digest}"


def make_family(groups: list[dict], confidence: str, key: str, conflicts: list[str]) -> dict:
    groups = sorted(groups, key=lambda group: group["job_group_id"])
    title_counts = Counter(group["representative_title"] for group in groups)
    representative = sorted(title_counts, key=lambda title: (-title_counts[title], title))[0]
    signals = sorted({signal for group in groups for signal in specialisation_signals(group["representative_title"])})
    return {
        "candidate_family_id": family_id(confidence, [group["job_group_id"] for group in groups]),
        "representative_title": representative,
        "member_titles": sorted(title_counts),
        "source_job_group_ids": [group["job_group_id"] for group in groups],
        "member_group_count": len(groups),
        "atomic_unit_count": sum(group["occurrence_count"] for group in groups),
        "industry_contexts": sorted({group["industry_domain_context"] for group in groups}),
        "shared_identity_signals": [key, *signals],
        "specialization_conflicts": conflicts,
        "confidence_for_review": confidence,
        "candidate_generation_version": VERSION,
        "review_eligible": confidence in {"high", "medium"},
    }


def sample(families: list[dict], confidence: str, count: int = 50) -> list[dict]:
    selected = [family for family in families if family["confidence_for_review"] == confidence]
    return sorted(selected, key=lambda family: hashlib.sha256((confidence + family["candidate_family_id"]).encode()).hexdigest())[:count]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--groups", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    all_groups = [json.loads(line) for line in args.groups.read_text(encoding="utf-8").splitlines() if line]
    unmapped = [group for group in all_groups if group["taxonomy_mapping_status"] == "unmapped"]
    assigned: set[str] = set()
    families: list[dict] = []

    # High: same strict occupation-bearing expression after narrowly safe wording cleanup.
    for key, members in sorted(blocked_clusters(unmapped, strict_identity_key).items()):
        if has_specialisation_conflict(members):
            continue
        families.append(make_family(members, "high", f"strict:{key}", []))
        assigned.update(member["job_group_id"] for member in members)

    # Medium: remaining groups share a role root but differ in role label/modifier.
    remaining = [group for group in unmapped if group["job_group_id"] not in assigned]
    for key, members in sorted(blocked_clusters(remaining, medium_identity_key).items()):
        conflicts = has_specialisation_conflict(members)
        if conflicts:
            continue
        families.append(make_family(members, "medium", f"role_root:{key}", []))
        assigned.update(member["job_group_id"] for member in members)

    # Low: conflicts share a broad root, retained for review but never recommended as merge evidence.
    remaining = [group for group in unmapped if group["job_group_id"] not in assigned]
    for key, members in sorted(blocked_clusters(remaining, medium_identity_key).items()):
        conflicts = has_specialisation_conflict(members)
        if conflicts:
            families.append(make_family(members, "low", f"conflicted_role_root:{key}", conflicts))
            assigned.update(member["job_group_id"] for member in members)

    unresolved = [group for group in unmapped if group["job_group_id"] not in assigned]
    families.sort(key=lambda family: family["candidate_family_id"])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "occupation_candidate_families.jsonl").write_text(
        "\n".join(json.dumps(family, ensure_ascii=False) for family in families) + "\n", encoding="utf-8"
    )
    singleton_samples = sorted(unresolved, key=lambda group: hashlib.sha256(("unresolved" + group["job_group_id"]).encode()).hexdigest())[:50]
    samples = []
    for confidence in ("high", "medium", "low"):
        samples.extend({"sample_set": f"{confidence}_confidence", **family} for family in sample(families, confidence))
    samples.extend({
        "sample_set": "unresolved_singleton",
        "candidate_family_id": None,
        "representative_title": group["representative_title"],
        "member_titles": [group["representative_title"]],
        "source_job_group_ids": [group["job_group_id"]],
        "member_group_count": 1,
        "atomic_unit_count": group["occurrence_count"],
        "industry_contexts": [group["industry_domain_context"]],
        "shared_identity_signals": [],
        "specialization_conflicts": [],
        "confidence_for_review": "unresolved",
    } for group in singleton_samples)
    (args.output_dir / "occupation_candidate_review_samples.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in samples) + "\n", encoding="utf-8"
    )
    counts = Counter(family["confidence_for_review"] for family in families)
    sizes = Counter(family["member_group_count"] for family in families)
    high_reduction = sum(family["member_group_count"] - 1 for family in families if family["confidence_for_review"] == "high")
    high_medium_reduction = sum(family["member_group_count"] - 1 for family in families if family["confidence_for_review"] in {"high", "medium"})
    summary = {
        "candidate_generation_version": VERSION,
        "baseline_job_group_count": len(all_groups),
        "unmapped_job_group_count": len(unmapped),
        "candidate_family_count": len(families),
        "unresolved_singleton_count": len(unresolved),
        "confidence_counts": dict(counts),
        "family_size_distribution": {str(size): count for size, count in sorted(sizes.items())},
        "families_over_2": sum(family["member_group_count"] > 2 for family in families),
        "families_over_5": sum(family["member_group_count"] > 5 for family in families),
        "families_over_10": sum(family["member_group_count"] > 10 for family in families),
        "families_over_20": sum(family["member_group_count"] > 20 for family in families),
        "high_only_simulated_job_group_count": len(all_groups) - high_reduction,
        "high_medium_upper_bound_simulated_job_group_count": len(all_groups) - high_medium_reduction,
        "semantic_review_candidate_family_count": counts["high"] + counts["medium"],
        "validation": {
            "no_duplicate_group_membership": sum(family["member_group_count"] for family in families) == len(assigned),
            "job_groups_mutated": False,
            "taxonomy_modified": False,
            "skill_inference_executed": False,
        },
    }
    (args.output_dir / "occupation_candidate_family_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    largest = sorted(families, key=lambda family: (-family["member_group_count"], family["candidate_family_id"]))[:50]
    lines = ["# Occupation Identity Candidate Clustering", "", "This is a deterministic candidate-generation and compression simulation only. No Job Group, Taxonomy, or inference result was changed.", "", "## Summary", ""]
    for key, value in summary.items():
        if key not in {"family_size_distribution", "validation"}:
            lines.append(f"- {key}: {value}")
    lines += ["", "## Largest candidate families", "", "| Representative title | Confidence | Groups | Industries | Conflict signals |", "|---|---|---:|---:|---|"]
    for family in largest:
        lines.append(f"| {family['representative_title']} | {family['confidence_for_review']} | {family['member_group_count']} | {len(family['industry_contexts'])} | {', '.join(family['specialization_conflicts']) or '-'} |")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
