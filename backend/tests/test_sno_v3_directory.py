import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "data" / "taxonomy" / "sno_v3" / "sno_occupation_catalog_v3.json"


def test_sno_v3_catalog_has_expected_shape_and_no_duplicate_primary_ids():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))

    assert catalog["taxonomy_version"] == "sno-v3-directory-design"
    assert catalog["status"] == "directory_design_pending_data_validation"
    assert catalog["counts"] == {
        "level_1": 32,
        "level_2": 262,
        "level_3": 204,
        "level_2_direct_only": 183,
    }

    level_2_ids = []
    level_3_ids = []
    for level_1 in catalog["taxonomy"]:
        for level_2 in level_1["level_2"]:
            assert level_2["level_2_id"].startswith(f"{level_1['level_1_id']}-")
            level_2_ids.append(level_2["level_2_id"])
            for level_3 in level_2["level_3"]:
                assert level_3["level_3_id"].startswith(f"{level_2['level_2_id']}-")
                level_3_ids.append(level_3["level_3_id"])

    assert len(level_2_ids) == len(set(level_2_ids)) == 262
    assert len(level_3_ids) == len(set(level_3_ids)) == 204


def test_sno_v3_contract_prevents_duplicate_primary_bubble_mappings():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    contract = catalog["classification_contract"]

    assert contract["one_primary_level_2_per_atomic_role"] is True
    assert contract["level_1_is_derived_from_level_2"] is True
    assert contract["industry_technology_and_seniority_are_tags_not_directory_nodes"] is True
