"""Write a read-only comparison between the independently audited v2/v3 trials."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path("data/processed/record_role_classification_v1")
V2 = ROOT / "api_trials" / "deepseek_name_classification_trial_v2"
V3 = ROOT / "api_trials" / "deepseek_name_classification_trial_v3"
V4 = ROOT / "name_registry" / "standard_occupation_to_original_names_final_deterministic_v4.json"
OUT = V3 / "v2_v3_comparison.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"Refusing to overwrite existing comparison: {OUT}")
    v2_rows = load(V2 / "manual_semantic_audit_100.json")["rows"]
    v3_rows = load(V3 / "manual_semantic_audit_100.json")["rows"]
    v2_cost = load(V2 / "cost_report.json")
    v3_cost = load(V3 / "cost_report.json")
    v4 = load(V4)
    by_v2 = {row["standard_occupation_id"]: row for row in v2_rows}
    by_v3 = {row["occupation_id"]: row for row in v3_rows}
    if set(by_v2) != set(by_v3) or len(by_v2) != 100:
        raise ValueError("v2 and v3 do not audit the exact same 100 occupation IDs")
    transitions = Counter()
    status_transitions = Counter()
    error_improvements = []
    regressions = []
    all_changes = []
    for occupation_id in sorted(by_v2):
        before = by_v2[occupation_id]
        after = by_v3[occupation_id]
        left = before["audit_verdict"]
        right = after["audit_verdict"]
        transitions[f"{left} -> {right}"] += 1
        status_transitions[f"{before['api_result']['status']} -> {after['api_result']['status']}"] += 1
        row = {
            "occupation_id": occupation_id,
            "occupation_name": after["occupation_name"],
            "v2_audit_verdict": left,
            "v3_audit_verdict": right,
            "v2_api_status": before["api_result"]["status"],
            "v3_api_status": after["api_result"]["status"],
            "v2_target_category_id": before["api_result"]["target_category_id"],
            "v3_target_category_id": after["api_result"]["target_category_id"],
        }
        if left == "error" and right != "error":
            error_improvements.append(row)
        if left != "error" and right == "error":
            regressions.append(row)
        if left != right or row["v2_api_status"] != row["v3_api_status"] or row["v2_target_category_id"] != row["v3_target_category_id"]:
            all_changes.append(row)
    payload = {
        "schema_version": "deepseek-name-classification-trial-v2-v3-comparison-v1",
        "same_sample_validation": {"same_occupation_id_set": True, "sample_size": 100},
        "v2": {
            "audit_verdict_counts": dict(Counter(row["audit_verdict"] for row in v2_rows)),
            "api_status_counts": dict(Counter(row["api_result"]["status"] for row in v2_rows)),
            "estimated_cost_usd": v2_cost["estimated_cost_usd"],
            "usage": v2_cost["usage"],
        },
        "v3": {
            "audit_verdict_counts": dict(Counter(row["audit_verdict"] for row in v3_rows)),
            "api_status_counts": dict(Counter(row["api_result"]["status"] for row in v3_rows)),
            "estimated_cost_usd": v3_cost["estimated_cost_usd"],
            "usage": v3_cost["usage"],
        },
        "comparison": {
            "audit_verdict_transitions": dict(transitions),
            "api_status_transitions": dict(status_transitions),
            "v2_error_count": sum(row["audit_verdict"] == "error" for row in v2_rows),
            "v3_error_count": sum(row["audit_verdict"] == "error" for row in v3_rows),
            "v2_errors_resolved_in_v3": len(error_improvements),
            "new_v3_errors_from_prior_nonerror": len(regressions),
            "all_changed_api_or_audit_rows": len(all_changes),
        },
        "resolved_prior_errors": error_improvements,
        "new_regressions": regressions,
        "changed_rows": all_changes,
        "v4_atomic_linkage_validation": v4["validation"],
        "scope_note": "Neither pilot is a formal full mapping. The v4 source registry remains read-only and retains all original group, atomic-role, and source-record associations.",
    }
    with OUT.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps(payload["comparison"], ensure_ascii=False))


if __name__ == "__main__":
    main()
