"""Run deterministic Reference Taxonomy coverage analysis for one snapshot."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path

import pandas as pd

from app.domain.taxonomy.coverage import analyse_coverage, load_reference_taxonomy, normalise_title


def _records(connection: sqlite3.Connection, snapshot_id: str) -> list[dict]:
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT record_id, row_number, job_title, company_name, industry_category,
               location, major_requirement, education_requirement
        FROM recruitment_records
        WHERE snapshot_id = ?
          AND eligible_for_market_analysis = 1
          AND record_status != 'duplicate'
        ORDER BY row_number
        """,
        (snapshot_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _single_value(values: pd.Series) -> str | None:
    unique = [value for value in values.dropna().unique().tolist() if value]
    return unique[0] if len(unique) == 1 else None


def _candidate_pool(results: pd.DataFrame) -> pd.DataFrame:
    accepted = results[results["gate_status"] == "accepted"]
    pending = accepted[accepted["match_type"].isin(["unmapped", "semantic_review"])].copy()
    role_markers = (
        r"(?:岗|工程师|经理|专员|主管|顾问|助理|总监|分析师|研究员|培训生|管培生|"
        r"运营|开发|测试|调试|工艺|履约|核算|销售|支持|代表|审核员|人员|"
        r"设计|策划|规划|采购|物流|翻译|编辑|实习|职员|教师|医生|护士|技师|科学家|架构师)$"
    )
    pending = pending[
        pending["job_title_unit"].str.contains(role_markers, regex=True, na=False)
        | (pending["review_status"] == "candidate_reference")
    ].copy()
    if pending.empty:
        return pd.DataFrame()
    pending["candidate_key"] = pending["job_title_unit"].map(normalise_title)
    rows: list[dict] = []
    for _, group in pending.groupby("candidate_key", sort=False):
        industries = Counter(value for value in group["industry_category"].dropna() if value)
        statuses = set(group["review_status"])
        rows.append(
            {
                "candidate_job_title": group["job_title_unit"].iloc[0],
                "candidate_status": "review_required" if "review_required" in statuses else "pending",
                "suggested_level_1": _single_value(group["matched_level_1"]),
                "suggested_level_2": _single_value(group["matched_level_2"]),
                "occurrence_count": len(group),
                "company_count": group["company_name"].dropna().nunique(),
                "location_count": group["location"].dropna().nunique(),
                "industry_distribution": json.dumps(dict(industries.most_common()), ensure_ascii=False),
                "source_record_ids": json.dumps(group["source_record_id"].tolist(), ensure_ascii=False),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["occurrence_count", "company_count", "location_count"], ascending=False
    )


def _coverage_summary(
    results: pd.DataFrame, taxonomy, snapshot_id: str, market_record_count: int, raw_title_count: int
) -> dict:
    accepted = results[results["gate_status"] == "accepted"]
    total = len(accepted)
    level_1_mapped = int(accepted["matched_level_1"].notna().sum())
    level_2_mapped = int(accepted["matched_level_2"].notna().sum())
    l3 = accepted[accepted["matched_occupation_id"].notna()]
    units_by_record = results.groupby("source_record_id").size()
    accepted_by_record = accepted.groupby("source_record_id").size()
    return {
        "analysis_version": "reference-taxonomy-coverage-v3-unit-level-quality-gate",
        "core_principle": "Reference Taxonomy defines the classification space; recruitment data is mapped into that space.",
        "snapshot_id": snapshot_id,
        "market_analysis_record_count": market_record_count,
        "distinct_raw_job_title_count": raw_title_count,
        "generated_title_unit_count": int(len(results)),
        "accepted_title_unit_count": int(total),
        "review_required_title_unit_count": int((results["gate_status"] == "review_required").sum()),
        "rejected_non_job_fragment_title_unit_count": int((results["gate_status"] == "rejected_non_job_fragment").sum()),
        "average_generated_units_per_record": round(len(results) / market_record_count, 4) if market_record_count else 0,
        "average_accepted_units_per_record": round(total / market_record_count, 4) if market_record_count else 0,
        "records_with_more_than_10_generated_units": int((units_by_record > 10).sum()),
        "records_with_more_than_10_accepted_units": int((accepted_by_record > 10).sum()),
        "mapped_title_unit_count": total,
        "taxonomy_level_3_count": len(taxonomy),
        "level_1": {"mapped_count": level_1_mapped, "unmapped_count": total - level_1_mapped, "coverage_rate": round(level_1_mapped / total, 4) if total else 0},
        "level_2": {"mapped_count": level_2_mapped, "unmapped_count": total - level_2_mapped, "coverage_rate": round(level_2_mapped / total, 4) if total else 0},
        "level_3": {
            "exact_standard_mapped": int(l3["match_type"].isin(["exact", "standard"]).sum()),
            "alias_mapped": int((l3["match_type"] == "alias").sum()),
            "semantic_manual_review": int((accepted["match_type"] == "semantic_review").sum()),
            "unmapped": int((accepted["match_type"] == "unmapped").sum()),
            "coverage_rate": round(len(l3) / total, 4) if total else 0,
            "mapped_occupation_count": int(l3["matched_occupation_id"].nunique()),
        },
    }


def _markdown_report(summary: dict, candidates: pd.DataFrame, taxonomy: pd.DataFrame, results: pd.DataFrame) -> str:
    def display(value: object) -> str:
        return "" if pd.isna(value) else str(value)

    lines = [
        "# Taxonomy Coverage Analysis",
        "",
        summary["core_principle"],
        "",
        "## Scope and method",
        "",
        f"- Snapshot: `{summary['snapshot_id']}`",
        f"- Market-eligible, non-duplicate recruitment records: {summary['market_analysis_record_count']:,}",
        f"- Distinct raw job-title fields: {summary['distinct_raw_job_title_count']:,}",
        f"- Reference Taxonomy level-3 occupations: {summary['taxonomy_level_3_count']:,}",
        f"- Generated title units retained for audit: {summary['generated_title_unit_count']:,}",
        f"- Accepted title units used for automatic coverage: {summary['accepted_title_unit_count']:,}",
        f"- Review-required title units retained outside the automatic coverage denominator: {summary['review_required_title_unit_count']:,}",
        f"- Rejected non-job fragments retained outside candidate expansion: {summary['rejected_non_job_fragment_title_unit_count']:,}",
        "- Splitter and quality gate are deterministic. Coverage is calculated only from accepted title units. Review-required and rejected units remain in `taxonomy_mapping_results.csv` for audit.",
        "- Mapping is deterministic. Exact/standard matches use reference level-3 names, aliases (if present), safe formatting cleanup, and industry context only for disambiguation. Fuzzy similarity only produces a review suggestion, never an automatic level-3 assignment.",
        "",
        "## Splitter quality summary",
        "",
        "| Metric | Count |",
        "|---|---:|",
        f"| Generated units | {summary['generated_title_unit_count']:,} |",
        f"| Accepted units | {summary['accepted_title_unit_count']:,} |",
        f"| Review-required units | {summary['review_required_title_unit_count']:,} |",
        f"| Rejected non-job fragments | {summary['rejected_non_job_fragment_title_unit_count']:,} |",
        f"| Average accepted units per record | {summary['average_accepted_units_per_record']:.2f} |",
        f"| Records with >10 generated units | {summary['records_with_more_than_10_generated_units']:,} |",
        f"| Records with >10 accepted units | {summary['records_with_more_than_10_accepted_units']:,} |",
        "",
        "## Coverage summary",
        "",
        "| Level | Mapped | Unmapped | Coverage |",
        "|---|---:|---:|---:|",
        f"| Level 1 | {summary['level_1']['mapped_count']:,} | {summary['level_1']['unmapped_count']:,} | {summary['level_1']['coverage_rate']:.1%} |",
        f"| Level 2 | {summary['level_2']['mapped_count']:,} | {summary['level_2']['unmapped_count']:,} | {summary['level_2']['coverage_rate']:.1%} |",
        f"| Level 3 exact/standard | {summary['level_3']['exact_standard_mapped']:,} | {summary['level_3']['unmapped'] + summary['level_3']['semantic_manual_review']:,} | {summary['level_3']['coverage_rate']:.1%} |",
        "",
        "## Level-3 mapping types",
        "",
        f"- Exact or standard mapped: {summary['level_3']['exact_standard_mapped']:,}",
        f"- Alias mapped: {summary['level_3']['alias_mapped']:,}",
        f"- Semantic/manual-review suggestions: {summary['level_3']['semantic_manual_review']:,}",
        f"- Unmapped: {summary['level_3']['unmapped']:,}",
        "",
        "## Top 30 unmapped or review-required job titles",
        "",
        "| Candidate job title | Status | Occurrences | Companies | Locations | Suggested level 1 | Suggested level 2 |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for _, row in candidates.head(30).iterrows():
        lines.append(
            f"| {row['candidate_job_title']} | {row['candidate_status']} | {row['occurrence_count']:,} | {row['company_count']:,} | {row['location_count']:,} | {display(row['suggested_level_1'])} | {display(row['suggested_level_2'])} |"
        )

    lines.extend(["", "## Coverage by reference level 1", "", "| Level 1 | Taxonomy level-3 roles | Mapped title units | Candidate title-unit occurrences |", "|---|---:|---:|---:|"])
    candidate_counts_l1 = candidates.groupby("suggested_level_1")["occurrence_count"].sum().to_dict() if not candidates.empty else {}
    accepted = results[results["gate_status"] == "accepted"]
    mapped_counts_l1 = accepted[accepted["matched_level_1"].notna()].groupby("matched_level_1").size().to_dict()
    for level_1, group in taxonomy.groupby("一级大行业", sort=False):
        lines.append(f"| {level_1} | {len(group):,} | {mapped_counts_l1.get(level_1, 0):,} | {candidate_counts_l1.get(level_1, 0):,} |")

    lines.extend(["", "## Level-2 review queue", "", "A `review_candidate_present` flag means market titles with a deterministic partial/review association appear under the field. It is not an automatic proposal to add a level-3 role.", "", "| Level 1 | Level 2 | Existing level-3 roles | Mapped title units | Candidate occurrences | Possible level-3 addition review |", "|---|---|---:|---:|---:|---|"])
    mapped_counts_l2 = accepted[accepted["matched_level_2"].notna()].groupby(["matched_level_1", "matched_level_2"]).size().to_dict()
    candidate_counts_l2 = candidates.groupby(["suggested_level_1", "suggested_level_2"])["occurrence_count"].sum().to_dict() if not candidates.empty else {}
    for (level_1, level_2), group in taxonomy.groupby(["一级大行业", "二级行业/职业领域"], sort=False):
        candidate_count = candidate_counts_l2.get((level_1, level_2), 0)
        lines.append(f"| {level_1} | {level_2} | {len(group):,} | {mapped_counts_l2.get((level_1, level_2), 0):,} | {candidate_count:,} | {'review_candidate_present' if candidate_count else ''} |")
    lines.extend(["", "## Interpretation boundary", "", "Only accepted title units are included in automatic coverage and the occupation candidate pool. Review-required units remain audit evidence, and rejected non-job fragments are explicitly excluded from candidate expansion. This analysis does not add aliases or occupations, does not modify the reference workbook, and does not replace any raw recruitment job title with a standard occupation name."])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic taxonomy coverage analysis.")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--snapshot-id")
    args = parser.parse_args()

    with sqlite3.connect(args.database) as connection:
        snapshot_id = args.snapshot_id or connection.execute(
            "SELECT snapshot_id FROM dataset_snapshots ORDER BY imported_at DESC LIMIT 1"
        ).fetchone()[0]
        records = _records(connection, snapshot_id)
        raw_title_count = connection.execute(
            """SELECT COUNT(DISTINCT job_title) FROM recruitment_records
               WHERE snapshot_id = ? AND eligible_for_market_analysis = 1 AND record_status != 'duplicate'""",
            (snapshot_id,),
        ).fetchone()[0]

    entries, _ = load_reference_taxonomy(args.taxonomy)
    results = analyse_coverage(records, args.taxonomy)
    candidates = _candidate_pool(results)
    summary = _coverage_summary(results, entries, snapshot_id, len(records), raw_title_count)
    taxonomy_frame = pd.read_excel(args.taxonomy, sheet_name="occupation_taxonomy")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.output_dir / "taxonomy_mapping_results.csv", index=False, encoding="utf-8-sig")
    candidates.to_csv(args.output_dir / "unmapped_occupation_candidates.csv", index=False, encoding="utf-8-sig")
    (args.output_dir / "taxonomy_coverage_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    args.report.write_text(_markdown_report(summary, candidates, taxonomy_frame, results), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
