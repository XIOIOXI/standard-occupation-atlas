"""Create a standalone, ID-linked DeepSeek name-only mapping snapshot.

This exporter does not alter the frozen v4 registry or batch artifacts.  It
joins only through ``standard_occupation_id`` / ``occupation_id`` and writes
one new file with exclusive creation so the source links in v4 remain the
authoritative raw-association store.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path("data/processed/record_role_classification_v1")
V4_PATH = ROOT / "name_registry" / "standard_occupation_to_original_names_final_deterministic_v4.json"
RUN_DIR = ROOT / "api_trials" / "deepseek_name_classification_trial_full_v1"
OUTPUT_PATH = RUN_DIR / "full_name_only_mapping_draft_v1.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exclusive_json(path: Path, payload) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> None:
    if OUTPUT_PATH.exists():
        raise FileExistsError(f"Refusing to overwrite existing snapshot: {OUTPUT_PATH}")

    registry = read_json(V4_PATH)
    occupations = registry["occupations"]
    expected_ids = [row["standard_occupation_id"] for row in occupations]
    expected_set = set(expected_ids)

    result_rows = []
    batch_paths = sorted(RUN_DIR.glob("batch_*_classified.json"))
    for path in batch_paths:
        batch = read_json(path)
        batch_number = batch["batch_number"]
        for row in batch["results"]:
            result_rows.append({
                "standard_occupation_id": row["occupation_id"],
                "target_category_id": row["target_category_id"],
                "status": row["status"],
                "reason": row["reason"],
                "processing_method": batch["processing_method"],
                "model_requested": batch["model_requested"],
                "prompt_profile": batch["prompt_profile"],
                "batch_number": batch_number,
            })

    result_ids = [row["standard_occupation_id"] for row in result_rows]
    result_set = set(result_ids)
    duplicates = sorted(identifier for identifier, count in Counter(result_ids).items() if count > 1)
    missing = sorted(expected_set - result_set)
    unexpected = sorted(result_set - expected_set)
    if missing or duplicates or unexpected or len(result_rows) != len(expected_ids):
        raise ValueError(
            "Incomplete or invalid batch set: "
            f"rows={len(result_rows)} expected={len(expected_ids)} "
            f"missing={len(missing)} duplicate={len(duplicates)} unexpected={len(unexpected)}"
        )

    linked_atomic_ids = []
    linked_record_ids = []
    original_group_ids = []
    registry_by_id = {row["standard_occupation_id"]: row for row in occupations}
    for result in result_rows:
        source = registry_by_id[result["standard_occupation_id"]]
        # Direct, stable source linkage: raw associations remain in v4 but are
        # replicated as IDs here for independent audit without API disclosure.
        result["standard_name"] = source["standard_name"]
        result["original_group_ids"] = source["original_group_ids"]
        result["source_atomic_unit_ids"] = source["source_atomic_unit_ids"]
        result["source_record_ids"] = source["source_record_ids"]
        linked_atomic_ids.extend(source["source_atomic_unit_ids"])
        linked_record_ids.extend(source["source_record_ids"])
        original_group_ids.extend(source["original_group_ids"])

    # v4 deliberately excludes malformed/abnormal name groups from the
    # standard-occupation registry.  They must not be falsely reported as
    # missing from a name-only classification; retain them separately and
    # prove that normal + abnormal links cover the source snapshot once.
    normal_atomic_expected = registry["validation"]["normal_atomic_role_count"]
    abnormal_groups = registry["abnormal_groups"]
    abnormal_atomic_ids = [
        atomic_id
        for group in abnormal_groups
        for atomic_id in group["source_atomic_unit_ids"]
    ]
    all_atomic_expected = normal_atomic_expected + registry["validation"]["abnormal_atomic_role_count"]
    atomic_duplicate_count = len(linked_atomic_ids) - len(set(linked_atomic_ids))
    normal_atomic_missing_count = normal_atomic_expected - len(set(linked_atomic_ids))
    abnormal_atomic_duplicate_count = len(abnormal_atomic_ids) - len(set(abnormal_atomic_ids))
    all_atomic_ids = linked_atomic_ids + abnormal_atomic_ids
    all_atomic_missing_count = all_atomic_expected - len(set(all_atomic_ids))
    all_atomic_duplicate_count = len(all_atomic_ids) - len(set(all_atomic_ids))
    if (
        normal_atomic_missing_count != 0
        or atomic_duplicate_count != 0
        or abnormal_atomic_duplicate_count != 0
        or all_atomic_missing_count != 0
        or all_atomic_duplicate_count != 0
    ):
        raise ValueError(
            "Atomic linkage check failed: "
            f"normal_missing={normal_atomic_missing_count}, normal_duplicate={atomic_duplicate_count}, "
            f"abnormal_duplicate={abnormal_atomic_duplicate_count}, "
            f"all_missing={all_atomic_missing_count}, all_duplicate={all_atomic_duplicate_count}"
        )

    payload = {
        "schema_version": "deepseek-name-only-full-mapping-draft-v1",
        "classification_scope": "Occupation names only; no company, industry, recruitment prose, skills, or legacy display mapping was supplied to the API.",
        "input_v4_path": str(V4_PATH),
        "input_v4_sha256": sha256_file(V4_PATH),
        "batch_run_directory": str(RUN_DIR),
        "mapping_count": len(result_rows),
        "status_counts": dict(Counter(row["status"] for row in result_rows)),
        "results": result_rows,
        "unclassified_abnormal_groups": abnormal_groups,
        "source_linkage_validation": {
            "input_standard_occupation_count": len(expected_ids),
            "linked_original_group_count": len(set(original_group_ids)),
            "linked_atomic_role_count": len(set(linked_atomic_ids)),
            "expected_normal_atomic_role_count": normal_atomic_expected,
            "normal_atomic_role_missing_count": normal_atomic_missing_count,
            "normal_atomic_role_duplicate_count": atomic_duplicate_count,
            "unclassified_abnormal_group_count": len(abnormal_groups),
            "unclassified_abnormal_atomic_role_count": len(set(abnormal_atomic_ids)),
            "abnormal_atomic_role_duplicate_count": abnormal_atomic_duplicate_count,
            "all_atomic_role_count": len(set(all_atomic_ids)),
            "expected_all_atomic_role_count": all_atomic_expected,
            "all_atomic_role_missing_count": all_atomic_missing_count,
            "all_atomic_role_duplicate_count": all_atomic_duplicate_count,
            "linked_source_record_count": len(set(linked_record_ids)),
            "abnormal_atomic_roles_preserved_through_v4": registry["validation"]["abnormal_atomic_role_count"],
        },
        "interpretation": {
            "mapped": "Name sufficiently supports the selected frozen level-3 category.",
            "review": "Only the returned level is supportable from the name, or the name remains insufficient for a deeper decision.",
            "taxonomy_gap": "Name is clear but no appropriate frozen taxonomy category was selected.",
            "multi_role": "Name explicitly lists incompatible independent roles and cannot be represented as one occupation.",
        },
        "raw_association_authority": "The frozen v4 registry remains the original normalisation and source-association authority; this draft copies its ID links without changing it.",
    }
    exclusive_json(OUTPUT_PATH, payload)
    print(json.dumps({
        "output": str(OUTPUT_PATH),
        "mapping_count": len(result_rows),
        "status_counts": payload["status_counts"],
        "atomic_role_count": len(set(linked_atomic_ids)),
        "all_atomic_role_count": len(set(all_atomic_ids)),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
