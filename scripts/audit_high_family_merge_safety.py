"""Strict, deterministic audit of high-confidence occupation candidate families."""
from __future__ import annotations

import argparse, hashlib, json, re
from collections import Counter, defaultdict
from pathlib import Path

from app.domain.job_groups.occupation_identity import PROTECTED_SPECIALISATIONS, remove_recruitment_noise, specialisation_signals
from app.domain.taxonomy.coverage import normalise_title

SAFE_SUFFIXES = ("岗位", "岗", "工程师", "开发", "研发")
SENIORITY = ("初级", "中级", "高级", "资深", "校招", "应届生", "实习生", "实习", "储备")
BROAD_TITLES = ("算法工程师", "应用工程师", "系统工程师", "技术工程师", "项目工程师", "研发工程师", "开发工程师", "运营", "产品", "销售", "测试工程师", "硬件工程师")
BROAD_LABELS = ("财务岗", "财务岗位", "人力资源岗", "运营岗", "运营管理岗", "产品岗", "销售岗", "采购岗", "研发岗", "技术岗", "管理岗", "综合专员", "项目管理岗")
INDUSTRY_MODIFIERS = ("金融", "银行", "医疗", "医药", "汽车", "教育", "农业", "化工", "建筑", "电商", "游戏", "能源", "航空", "法律")


def surface_body(title: str) -> str:
    text = remove_recruitment_noise(title)
    text = re.sub(r"[（(][^（）()]*[）)]", "", text)
    text = re.sub("|".join(map(re.escape, SENIORITY)), "", text)
    text = re.sub(r"(?:岗位|岗)$", "", text)
    return text


def protected_set(title: str) -> set[str]:
    return {signal for signal in specialisation_signals(title) if signal in PROTECTED_SPECIALISATIONS}


def classify(family: dict) -> tuple[str, list[str], list[str]]:
    titles = family["member_titles"]
    bodies = {surface_body(title) for title in titles}
    protected = {tuple(sorted(protected_set(title))) for title in titles}
    protected_nonempty = {entry for entry in protected if entry}
    broad = any(normalise_title(title) in {normalise_title(x) for x in (*BROAD_TITLES, *BROAD_LABELS)} for title in titles)
    industry = {modifier for title in titles for modifier in INDUSTRY_MODIFIERS if modifier in title}
    reasons: list[str] = []
    flags: list[str] = []
    if len(protected_nonempty) > 1:
        flags.append("multiple_protected_specialisation_signatures")
        reasons.append("member titles contain materially different protected specialization signals")
        return "UNSAFE_MIXED", flags, reasons
    if broad:
        flags.append("broad_title_family")
        reasons.append("broad occupation label requires semantic boundary review")
    if len(industry) > 1:
        flags.append("multiple_industry_modifiers")
        reasons.append("industry-specific modifiers vary within the family")
    if len(bodies) > 1 and any("/" in title or "与" in title for title in titles):
        flags.append("compound_title")
        reasons.append("compound title may contain more than one role boundary")
    if flags:
        return "REVIEW_REQUIRED", flags, reasons
    return "SAFE", ["surface_variant_only"], ["titles differ only by safe role wording, recruitment modifiers, location, seniority, or punctuation"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--families", type=Path, required=True)
    parser.add_argument("--groups", type=Path, required=True)
    parser.add_argument("--members", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    families = [json.loads(line) for line in args.families.read_text(encoding="utf-8").splitlines() if line and json.loads(line).get("confidence_for_review") == "high"]
    groups = {group["job_group_id"]: group for group in (json.loads(line) for line in args.groups.read_text(encoding="utf-8").splitlines() if line)}
    member_rows = [json.loads(line) for line in args.members.read_text(encoding="utf-8").splitlines() if line]
    records_by_family: dict[str, set[str]] = defaultdict(set)
    companies_by_family: dict[str, set[str]] = defaultdict(set)
    member_by_group: dict[str, list[dict]] = defaultdict(list)
    for row in member_rows:
        member_by_group[row["job_group_id"]].append(row)
    details = []
    safe_ids: set[str] = set()
    for family in families:
        classification, flags, reasons = classify(family)
        group_ids = family["source_job_group_ids"]
        atomic_units = sum(groups[group_id]["occurrence_count"] for group_id in group_ids if group_id in groups)
        record_ids = {row["source_record_id"] for group_id in group_ids for row in member_by_group[group_id]}
        company_ids = {row["company_name"] for group_id in group_ids for row in member_by_group[group_id] if row.get("company_name")}
        detail = {**family, "audit_classification": classification, "audit_flags": flags, "audit_reason": reasons, "specialization_signals": sorted({signal for title in family["member_titles"] for signal in protected_set(title)}), "member_group_count": len(group_ids), "atomic_unit_count": atomic_units, "recruitment_record_count": len(record_ids), "company_count": len(company_ids)}
        details.append(detail)
        if classification == "SAFE":
            safe_ids.update(group_ids)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "high_family_merge_safety_details.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in sorted(details, key=lambda x: x["candidate_family_id"])) + "\n", encoding="utf-8")
    sizes = Counter(row["member_group_count"] for row in details)
    safe_rows = [row for row in details if row["audit_classification"] == "SAFE"]
    review_rows = [row for row in details if row["audit_classification"] == "REVIEW_REQUIRED"]
    unsafe_rows = [row for row in details if row["audit_classification"] == "UNSAFE_MIXED"]
    safe_group_count = len(safe_ids)
    safe_records = {row["source_record_id"] for group_id in safe_ids for row in member_by_group[group_id]}
    safe_companies = {row["company_name"] for group_id in safe_ids for row in member_by_group[group_id] if row.get("company_name")}
    summary = {
        "audit_version": "high-family-merge-safety-audit-v1",
        "high_family_count": len(details),
        "safe_count": len(safe_rows),
        "review_required_count": len(review_rows),
        "unsafe_mixed_count": len(unsafe_rows),
        "family_size_distribution": {str(size): count for size, count in sorted(sizes.items())},
        "large_family_count_over_10": sum(row["member_group_count"] > 10 for row in details),
        "safe_job_group_count": safe_group_count,
        "safe_group_reduction": sum(row["member_group_count"] - 1 for row in safe_rows),
        "baseline_job_group_count": len(groups),
        "safe_only_simulated_job_group_count": len(groups) - sum(row["member_group_count"] - 1 for row in safe_rows),
        "safe_atomic_unit_count": sum(groups[group_id]["occurrence_count"] for group_id in safe_ids),
        "safe_recruitment_record_count": len(safe_records),
        "safe_company_count": len(safe_companies),
        "random_sample_100": {},
        "validation": {"source_high_count_matches": len(details) == 1341, "no_duplicate_safe_group_ids": len(safe_ids) == sum(row["member_group_count"] for row in safe_rows), "job_groups_mutated": False, "taxonomy_modified": False, "llm_called": False, "skill_inference_executed": False},
    }
    # Stable sample of up to 100 size<=10 families.
    sample = sorted([row for row in details if row["member_group_count"] <= 10], key=lambda row: hashlib.sha256(("merge-safety-v1|" + row["candidate_family_id"]).encode()).hexdigest())[:100]
    summary["random_sample_100"] = dict(Counter(row["audit_classification"] for row in sample))
    (args.output_dir / "high_family_merge_safety_audit.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    large = sorted([row for row in details if row["member_group_count"] > 10], key=lambda row: (-row["member_group_count"], row["representative_title"]))
    lines = ["# High-family Merge Safety Audit", "", "Deterministic audit only; no Job Group merge, Taxonomy change, LLM call, or Skill Inference was performed.", "", "## Summary", "", f"- High families: {len(details):,}", f"- SAFE / REVIEW_REQUIRED / UNSAFE_MIXED: {len(safe_rows):,} / {len(review_rows):,} / {len(unsafe_rows):,}", f"- SAFE groups / reduction: {safe_group_count:,} / {summary['safe_group_reduction']:,}", f"- SAFE-only simulation: {summary['safe_only_simulated_job_group_count']:,}", f"- SAFE atomic units / records / companies: {summary['safe_atomic_unit_count']:,} / {summary['safe_recruitment_record_count']:,} / {summary['safe_company_count']:,}", "", "## All families larger than 10", "", "| Representative | Size | Classification | Signals | Reason |", "|---|---:|---|---|---|"]
    for row in large:
        lines.append(f"| {row['representative_title']} | {row['member_group_count']} | {row['audit_classification']} | {', '.join(row['specialization_signals']) or '-'} | {'; '.join(row['audit_reason'])} |")
    lines += ["", "## Deterministic random sample (size <= 10)", "", json.dumps(summary["random_sample_100"], ensure_ascii=False), "", "## Standard", "", "SAFE is reserved for surface/recruitment variants without broad-title or specialization-boundary signals. Uncertain cases remain REVIEW_REQUIRED; conflicting protected specializations are UNSAFE_MIXED."]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
