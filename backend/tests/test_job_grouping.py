from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from app.domain.taxonomy.coverage import normalise_title
from app.infrastructure.sqlite_job_group_repository import SqliteJobGroupRepository


SCRIPT = Path("scripts/run_job_grouping_v1.py")
SPEC = importlib.util.spec_from_file_location("job_grouping_v1", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

AUDIT_SPEC = importlib.util.spec_from_file_location("singleton_audit", Path("scripts/audit_job_group_singleton_undermerge.py"))
assert AUDIT_SPEC and AUDIT_SPEC.loader
AUDIT = importlib.util.module_from_spec(AUDIT_SPEC)
AUDIT_SPEC.loader.exec_module(AUDIT)

V2_SPEC = importlib.util.spec_from_file_location("job_grouping_v2", Path("scripts/run_job_grouping_v2_occupation_safe.py"))
assert V2_SPEC and V2_SPEC.loader
V2 = importlib.util.module_from_spec(V2_SPEC)
V2_SPEC.loader.exec_module(V2)


class JobGroupingTests(unittest.TestCase):
    def test_same_mapped_occupation_does_not_merge_incompatible_industries(self) -> None:
        software = MODULE.grouping_key("OCC0001", "软件工程师", "互联网")
        finance = MODULE.grouping_key("OCC0001", "软件工程师", "银行/金融")
        self.assertNotEqual(software, finance)

    def test_unmapped_title_groups_only_by_normalised_title_and_industry(self) -> None:
        first = MODULE.grouping_key(None, "稳定 未映射工程师", "制造业")
        second = MODULE.grouping_key(None, "稳定未映射工程师", "制造业")
        self.assertEqual(first, second)
        self.assertIn(normalise_title("稳定未映射工程师"), first)

    def test_grouping_versioned_persistence_preserves_member_traceability(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "groups.sqlite"
            repository = SqliteJobGroupRepository(database)
            summary = {"generated_at": "2026-09-20T00:00:00+00:00"}
            group = {"job_group_id": "JG-test", "representative_title": "软件工程师"}
            member = {"job_group_id": "JG-test", "source_record_id": "record-1", "source_atomic_unit_id": "unit-1"}
            repository.save("snapshot-1", "job-grouping-v1", summary, [group], [member])
            with self.assertRaises(ValueError):
                repository.save("snapshot-1", "job-grouping-v1", summary, [group], [member])

    def test_approved_runtime_taxonomy_contains_only_approved_additions(self) -> None:
        artifact = Path("data/processed/taxonomy/mvp_taxonomy_v4_1_frozen.json")
        data = json.loads(artifact.read_text(encoding="utf-8"))
        titles = {item["level_3"]: item for item in data["occupations"]}
        self.assertEqual(data["status"], "FROZEN")
        self.assertEqual(titles["财务专员"]["occupation_id"], "OCC0453")
        self.assertEqual(titles["技术服务工程师"]["occupation_id"], "OCC0454")
        self.assertNotIn("技术支持工程师", titles)

    def test_audit_surface_key_only_removes_safe_job_suffixes(self) -> None:
        self.assertEqual(AUDIT.safe_surface_key("软件工程师岗"), AUDIT.safe_surface_key("软件工程师"))
        self.assertNotEqual(AUDIT.possible_stem("软件测试工程师"), AUDIT.possible_stem("硬件测试工程师"))

    def test_v2_safe_family_respects_existing_industry_context(self) -> None:
        family = {"candidate_family_id": "OCF-safe"}
        first = {"job_group_id": "JG-v1-a", "industry_domain_context": "l1:信息技术"}
        second = {"job_group_id": "JG-v1-b", "industry_domain_context": "l1:金融"}
        first_key, _ = V2.v2_key(first, {"JG-v1-a": family})
        second_key, _ = V2.v2_key(second, {"JG-v1-b": family})
        self.assertNotEqual(first_key, second_key)

    def test_v2_passthrough_group_gets_its_own_stable_key(self) -> None:
        group = {"job_group_id": "JG-v1-a", "industry_domain_context": "l1:信息技术"}
        key, family = V2.v2_key(group, {})
        self.assertEqual(key, "passthrough:JG-v1-a")
        self.assertIsNone(family)


if __name__ == "__main__":
    unittest.main()
