"""Generate a deterministic, non-mutating Reference Taxonomy expansion proposal."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from app.domain.taxonomy.coverage import load_reference_taxonomy, normalise_title


PROGRAM_PATTERN = re.compile(r"(?:校招生|星计划|菁英|菁鲤|优\+|金种子|英才生|管培生|培训生|储备生)")
GENERIC_PATTERN = re.compile(r"^(?:财务|信息技术|综合管理|技术研发|市场营销|人力资源|运营|管理|研发|测试|销售|产品|业务|项目)(?:岗|岗位)?$")

# Strictly curated deterministic recommendations. They are proposals, not taxonomy edits.
ALIASES = {
    "软件开发工程师": ("软件工程师", "信息技术与数字产业", "软件开发与工程"),
    "嵌入式开发工程师": ("嵌入式软件工程师", "电子信息与通信产业", "电子硬件与嵌入式"),
    "硬件技术工程师": ("硬件工程师", "电子信息与通信产业", "电子硬件与嵌入式"),
}
NEW_OCCUPATIONS = {
    "算法工程师": ("算法工程师", "信息技术与数字产业", "人工智能与机器学习"),
    "AI应用工程师": ("AI应用工程师", "信息技术与数字产业", "人工智能与机器学习"),
    "AI模型工程师": ("AI模型工程师", "信息技术与数字产业", "生成式AI与大模型"),
    "AI Infra工程师": ("AI基础设施工程师", "信息技术与数字产业", "生成式AI与大模型"),
    "AI安全与隐私工程师": ("AI安全与隐私工程师", "信息技术与数字产业", "网络与信息安全"),
    "AI应用研究员": ("AI应用研究员", "信息技术与数字产业", "人工智能与机器学习"),
    "AI模型研究员": ("AI模型研究员", "信息技术与数字产业", "生成式AI与大模型"),
    "算法研究员": ("算法研究员", "信息技术与数字产业", "人工智能与机器学习"),
}
MERGES = {
    "管培生": ("管理培训生", "", ""),
    "财务管培生": ("管理培训生", "", ""),
    "营销管培生": ("管理培训生", "", ""),
    "销售管培生": ("管理培训生", "", ""),
    "生产管培生": ("管理培训生", "", ""),
}


def _industry_distribution(row: dict[str, str]) -> dict[str, int]:
    try:
        return json.loads(row["industry_distribution"])
    except json.JSONDecodeError:
        return {}


def _cross_industry(row: dict[str, str]) -> bool:
    distribution = _industry_distribution(row)
    total = sum(distribution.values())
    return len(distribution) >= 3 and total and max(distribution.values()) / total < 0.7


def _surface_forms(title: str) -> set[str]:
    forms = {normalise_title(title)}
    stripped = re.sub(r"(?:岗位|岗)$", "", title).strip()
    forms.add(normalise_title(stripped))
    return {form for form in forms if form}


def _review(row: dict[str, str], canonical: dict[str, list], aliases: dict[str, list]) -> dict[str, str | bool]:
    title = row["candidate_job_title"]
    forms = _surface_forms(title)
    existing = [entry for form in forms for entry in canonical.get(form, []) + aliases.get(form, [])]
    existing = list(dict.fromkeys(existing))
    cross_industry = _cross_industry(row)
    base = {
        "matched_existing_occupation": "",
        "recommended_standard_title": "",
        "recommended_level_1": "",
        "recommended_level_2": "",
        "proposed_aliases": "",
        "cross_industry": cross_industry,
        "taxonomy_structure_review_required": False,
        "reason": "",
        "confidence": "low",
    }
    if title in ALIASES:
        standard, level_1, level_2 = ALIASES[title]
        return base | {"review_status": "alias_of_existing", "matched_existing_occupation": standard,
                       "recommended_standard_title": standard, "recommended_level_1": level_1,
                       "recommended_level_2": level_2, "proposed_aliases": title,
                       "reason": "Curated surface/suffix variant of an existing occupation.", "confidence": "high"}
    if len(existing) == 1:
        entry = existing[0]
        return base | {"review_status": "alias_of_existing", "matched_existing_occupation": entry.level_3,
                       "recommended_standard_title": entry.level_3, "recommended_level_1": entry.level_1,
                       "recommended_level_2": entry.level_2, "proposed_aliases": title,
                       "reason": "Exact or suffix-normalised surface variant of one existing occupation.", "confidence": "high"}
    if title in NEW_OCCUPATIONS:
        standard, level_1, level_2 = NEW_OCCUPATIONS[title]
        return base | {"review_status": "proposed_new_occupation", "recommended_standard_title": standard,
                       "recommended_level_1": level_1, "recommended_level_2": level_2,
                       "proposed_aliases": title if title != standard else "",
                       "reason": "Curated, market-generic emerging role with a reusable placement in an existing field.", "confidence": "medium"}
    if title in MERGES:
        standard, level_1, level_2 = MERGES[title]
        return base | {"review_status": "merge_with_candidate", "recommended_standard_title": standard,
                       "recommended_level_1": level_1, "recommended_level_2": level_2,
                       "proposed_aliases": title, "taxonomy_structure_review_required": True,
                       "reason": "Variant of the same management-trainee candidate family; no existing level-2 placement is proposed.", "confidence": "medium"}
    if PROGRAM_PATTERN.search(title):
        return base | {"review_status": "company_specific_or_program", "reason": "Training/recruitment programme wording is not a reusable occupation.", "confidence": "high"}
    if GENERIC_PATTERN.fullmatch(title):
        return base | {"review_status": "too_generic", "reason": "Broad function/category lacks a sufficiently specific level-3 occupational scope.", "confidence": "high"}
    if len(existing) > 1:
        return base | {"review_status": "pending_review", "reason": "Surface form corresponds to multiple existing occupations; industry context is insufficient for a single placement.", "confidence": "medium"}
    return base | {"review_status": "pending_review", "reason": "No safe deterministic equivalence or reusable placement was established.", "confidence": "low"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    entries, _ = load_reference_taxonomy(args.taxonomy)
    canonical: dict[str, list] = defaultdict(list)
    aliases: dict[str, list] = defaultdict(list)
    for entry in entries:
        canonical[normalise_title(entry.level_3)].append(entry)
        for alias in entry.aliases:
            aliases[normalise_title(alias)].append(entry)
    with args.candidates.open(encoding="utf-8-sig", newline="") as handle:
        candidates = list(csv.DictReader(handle))
    proposal = []
    for row in candidates:
        proposal.append(row | _review(row, canonical, aliases))
    proposal.sort(key=lambda row: (-int(row["occurrence_count"]), -int(row["company_count"]), row["candidate_job_title"]))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    fields = ["candidate_title", "occurrence_count", "company_count", "location_count", "review_status", "matched_existing_occupation", "recommended_standard_title", "recommended_level_1", "recommended_level_2", "proposed_aliases", "cross_industry", "taxonomy_structure_review_required", "reason", "confidence"]
    with (args.output_dir / "taxonomy_expansion_proposal.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in proposal:
            writer.writerow({"candidate_title": row["candidate_job_title"], **{field: row[field] for field in fields[1:]}})
    status_counts = Counter(row["review_status"] for row in proposal)
    coverable = [row for row in proposal if row["review_status"] in {"alias_of_existing", "proposed_new_occupation", "merge_with_candidate"}]
    standard_titles = {row["recommended_standard_title"] for row in coverable if row["recommended_standard_title"]}
    alias_titles = {row["candidate_job_title"] for row in proposal if row["review_status"] == "alias_of_existing"}
    covered_units = sum(int(row["occurrence_count"]) for row in coverable)
    summary = {"total_candidates_reviewed": len(proposal), **status_counts,
               "estimated_new_standard_occupations": len({row["recommended_standard_title"] for row in proposal if row["review_status"] == "proposed_new_occupation"}),
               "estimated_new_aliases": len(alias_titles), "estimated_candidate_titles_covered": len(coverable),
               "estimated_accepted_units_covered": covered_units, "estimated_level_3_coverage": round((1741 + covered_units) / 20964, 4),
               "estimate_note": "Deterministic proposal estimate only; not a rerun of Coverage Analysis and does not modify the taxonomy."}
    (args.output_dir / "taxonomy_expansion_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    def section(status: str, limit: int) -> list[dict]: return [row for row in proposal if row["review_status"] == status][:limit]
    lines = ["# Reference Taxonomy Expansion Proposal", "", "Reference Taxonomy defines the classification space; this report proposes review actions only and does not modify the workbook.", "", "## Baseline", "", "- Baseline Level-3 coverage: 8.30%.", "- Accepted candidate titles reviewed: " + f"{len(proposal):,}.", "", "## Review status", "", "| Status | Count |", "|---|---:|"]
    for status in ["alias_of_existing", "proposed_new_occupation", "merge_with_candidate", "too_generic", "company_specific_or_program", "pending_review"]:
        lines.append(f"| {status} | {status_counts[status]:,} |")
    for heading, status, limit in [("Top proposed new occupations", "proposed_new_occupation", 30), ("Top alias mappings", "alias_of_existing", 20), ("Top candidate merges", "merge_with_candidate", 20), ("Too-generic examples", "too_generic", 15), ("Company-specific/program examples", "company_specific_or_program", 15), ("Pending-review examples", "pending_review", 15)]:
        lines += ["", f"## {heading}", "", "| Candidate | Occurrences | Companies | Recommendation | Placement | Reason |", "|---|---:|---:|---|---|---|"]
        for row in section(status, limit):
            lines.append(f"| {row['candidate_job_title']} | {row['occurrence_count']} | {row['company_count']} | {row['recommended_standard_title']} | {row['recommended_level_1']} / {row['recommended_level_2']} | {row['reason']} |")
    lines += ["", "## Estimate if proposal is adopted", "", f"- Candidate titles covered: {len(coverable):,}", f"- Accepted title-unit occurrences covered: {covered_units:,}", f"- Estimated Level-3 coverage: 8.30% → {summary['estimated_level_3_coverage']:.2%}.", "- This is an estimate only. It is not a formal Coverage Analysis rerun.", "", "## Cross-industry and structure notes", "", "- Cross-industry is flagged when no single raw industry label dominates the candidate evidence. Such candidates require placement review before an industry-specific interpretation.", "- No new Level 1 or Level 2 is proposed automatically; unresolved placements remain pending review."]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
