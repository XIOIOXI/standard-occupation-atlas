"""Create a fixed, stratified, name-only quality-audit sample.

This script selects audit rows only.  It makes no judgement about whether a
classification is correct and never changes the mapping draft.
"""

from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path("data/processed/record_role_classification_v1")
MAPPING_PATH = ROOT / "api_trials" / "deepseek_name_classification_trial_full_v1" / "full_name_only_mapping_draft_v1.json"
TAXONOMY_PATH = ROOT / "catalog_mappings" / "taxonomy_embedding_texts_v1.json"
OUTPUT_DIR = ROOT / "quality_audits" / "name_only_stratified_v1"
OUTPUT_PATH = OUTPUT_DIR / "sample_manifest.json"
SEED = 20261012
QUOTAS = {"mapped": 200, "review": 50, "multi_role": 30, "taxonomy_gap": 20}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def exclusive_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def sample_mapped(rows: list[dict], count: int, rng: random.Random) -> list[dict]:
    """Cover level-2 domains first, then fill the remaining quota randomly."""
    by_l2: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        # L1/L2 are attached below from the frozen taxonomy, never inferred.
        key = f"{row['current_level_1']} / {row['current_level_2']}"
        by_l2[key].append(row)
    selected: list[dict] = []
    # Shuffle domain order deterministically to avoid privileging catalog order.
    domain_keys = list(by_l2)
    rng.shuffle(domain_keys)
    for key in domain_keys:
        if len(selected) >= count:
            break
        selected.append(rng.choice(by_l2[key]))
    remaining = [row for row in rows if row["standard_occupation_id"] not in {x["standard_occupation_id"] for x in selected}]
    rng.shuffle(remaining)
    selected.extend(remaining[: count - len(selected)])
    if len(selected) != count:
        raise ValueError("Could not fill mapped sample quota")
    return selected


def main() -> None:
    if OUTPUT_PATH.exists():
        raise FileExistsError(f"Refusing to overwrite sample manifest: {OUTPUT_PATH}")
    mapping = read_json(MAPPING_PATH)
    taxonomy = read_json(TAXONOMY_PATH)
    categories = {row["category_id"]: row for row in taxonomy["rows"]}
    occupations = {row["standard_occupation_id"]: row for row in read_json(Path(mapping["input_v4_path"]))["occupations"]}
    by_status: dict[str, list[dict]] = defaultdict(list)
    for mapping_row in mapping["results"]:
        occupation = occupations[mapping_row["standard_occupation_id"]]
        current_category = categories.get(mapping_row["target_category_id"])
        audit_row = {
            "audit_item_id": f"AQ-{mapping_row['standard_occupation_id'][4:]}",
            "standard_occupation_id": mapping_row["standard_occupation_id"],
            "standard_name": mapping_row["standard_name"],
            "original_names": occupation["original_names"],
            "current_status": mapping_row["status"],
            "current_category_id": mapping_row["target_category_id"],
            "current_level_1": current_category["level_1"] if current_category else None,
            "current_level_2": current_category["level_2"] if current_category else None,
            "current_level_3": current_category["level_3"] if current_category else None,
            "current_category_boundary": current_category["matching_text"] if current_category else None,
            "current_reason": mapping_row["reason"],
        }
        by_status[audit_row["current_status"]].append(audit_row)

    rng = random.Random(SEED)
    selected: list[dict] = []
    selected.extend(sample_mapped(by_status["mapped"], QUOTAS["mapped"], rng))
    for status in ("review", "multi_role", "taxonomy_gap"):
        candidates = list(by_status[status])
        rng.shuffle(candidates)
        if len(candidates) < QUOTAS[status]:
            raise ValueError(f"Not enough {status} rows for quota")
        selected.extend(candidates[: QUOTAS[status]])
    rng.shuffle(selected)
    if len(selected) != sum(QUOTAS.values()) or len({row["audit_item_id"] for row in selected}) != len(selected):
        raise ValueError("Sample is not exactly 300 unique audit rows")

    payload = {
        "schema_version": "name-only-mapping-quality-sample-v1",
        "source_mapping_path": str(MAPPING_PATH),
        "source_taxonomy_path": str(TAXONOMY_PATH),
        "sampling_seed": SEED,
        "quotas": QUOTAS,
        "sample_count": len(selected),
        "sample_status_counts": dict(Counter(row["current_status"] for row in selected)),
        "mapped_coverage": {
            "level_1_count": len({row["current_level_1"] for row in selected if row["current_status"] == "mapped"}),
            "level_2_count": len({(row["current_level_1"], row["current_level_2"]) for row in selected if row["current_status"] == "mapped"}),
        },
        "selection_method": "Mapped rows cover available level-2 domains first, then are deterministically filled; other status strata are deterministic random samples.",
        "items": selected,
    }
    exclusive_json(OUTPUT_PATH, payload)
    print(json.dumps({
        "output": str(OUTPUT_PATH),
        "sample_count": len(selected),
        "status_counts": payload["sample_status_counts"],
        "mapped_coverage": payload["mapped_coverage"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
