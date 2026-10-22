"""Create a non-destructive summary for the completed DeepSeek name-only trial."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path("data/processed/record_role_classification_v1")
TRIAL = ROOT / "api_trials" / "deepseek_name_classification_trial_v2"
V4 = ROOT / "name_registry" / "standard_occupation_to_original_names_final_deterministic_v4.json"
OUT = TRIAL / "trial_report.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"Refusing to overwrite existing report: {OUT}")
    v4 = load(V4)
    mappings = load(TRIAL / "trial_100_mappings.json")
    audit = load(TRIAL / "manual_semantic_audit_100.json")
    costs = load(TRIAL / "cost_report.json")
    selected_ids = {item["standard_occupation_id"] for item in mappings["results"]}
    audited_ids = {item["standard_occupation_id"] for item in audit["rows"]}
    report = {
        "schema_version": "deepseek-name-classification-trial-report-v1",
        "scope": "A 100-standard-occupation name-only API trial; it is not a full mapping run.",
        "input": {
            "v4_path": str(V4),
            "v4_standard_occupation_count": len(v4["occupations"]),
            "v4_atomic_coverage_validation": v4["validation"],
            "api_privacy_scope": "API inputs contain only standard_occupation_id, standard_name, and frozen taxonomy directory. No company, industry, recruitment prose, skills, atomic IDs, or source record IDs are sent.",
        },
        "api_trial": {
            "model_requested": costs["model_requested"],
            "connection_probe": "passed in non-thinking JSON mode",
            "classified_standard_occupation_count": len(mappings["results"]),
            "api_status_counts": mappings["status_counts"],
            "token_usage": costs["usage"],
            "estimated_cost_usd": costs["estimated_cost_usd"],
            "full_10998_linear_estimate_usd": costs["full_10998_linear_estimate_usd"],
            "cost_limit_usd": costs["stop_budget_usd"],
        },
        "manual_audit": {
            "audited_count": len(audit["rows"]),
            "audit_verdict_counts": audit["summary"]["audit_verdict_counts"],
            "model_output_handling_counts": audit["summary"]["model_output_handling_counts"],
            "method": audit["audit_method"],
        },
        "integrity": {
            "selected_ids_unique": len(selected_ids) == len(mappings["results"]),
            "audited_ids_exactly_match_trial": selected_ids == audited_ids,
            "v4_not_modified": True,
            "atomic_links_note": "The sample output joins v4 by standard_occupation_id; all original group, atomic-role, and source-record links remain only in the read-only v4 input.",
        },
        "known_issue_and_fix": {
            "raw_v2_review_parent_ids": "The first v2 prompt incorrectly derived some parent IDs by splitting slash-containing level-1 labels, so affected review targets are preserved as raw outputs and are not formal mappings.",
            "future_runner_fix": "The runner now derives level-2 parents by removing only the final level-3 ID segment and takes level-1 IDs from the frozen level-1 label.",
        },
        "artifacts": {
            "selection": "selection_manifest.json",
            "per_batch_api_inputs": "batch_001_api_input.json through batch_005_api_input.json",
            "per_batch_api_outputs": "batch_001_api_output.json through batch_005_api_output.json",
            "classified_results": "trial_100_mappings.json",
            "manual_audit": "manual_semantic_audit_100.json",
            "cost_report": "cost_report.json",
        },
    }
    with OUT.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"report": str(OUT), "classified": len(mappings["results"]), "audited": len(audit["rows"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
