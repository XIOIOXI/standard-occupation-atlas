from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.domain.taxonomy.coverage import analyse_coverage, load_reference_taxonomy, split_title_units, split_title_units_with_quality
from app.domain.taxonomy.models import (
    CanonicalOccupation,
    OccupationDomainLink,
    SemanticCandidateReviewV2,
    canonical_occupations_from_legacy_entries,
)
from app.domain.taxonomy.semantic_review_v2 import P0_REVIEW_TARGETS, prepare_p0_v2_re_review


TAXONOMY = "data/taxonomy/China_Employment_Taxonomy_3Level_v4_with_Candidates.xlsx"


class TaxonomyCoverageTests(unittest.TestCase):
    def test_preserves_raw_title_and_maps_exact_reference_occupation(self) -> None:
        results = analyse_coverage(
            [{"record_id": "r1", "row_number": 1, "job_title": "软件工程师", "company_name": "A", "industry_category": "互联网", "location": "上海", "major_requirement": None, "education_requirement": None}],
            TAXONOMY,
        )
        self.assertEqual(results.iloc[0]["raw_job_title"], "软件工程师")
        self.assertEqual(results.iloc[0]["matched_occupation_name"], "软件工程师")
        self.assertEqual(results.iloc[0]["match_type"], "exact")

    def test_reference_candidate_remains_unmapped_with_partial_context(self) -> None:
        results = analyse_coverage(
            [{"record_id": "r2", "row_number": 2, "job_title": "卫星互联网产品经理", "company_name": "B", "industry_category": "航空运营", "location": "北京", "major_requirement": None, "education_requirement": None}],
            TAXONOMY,
        )
        self.assertEqual(results.iloc[0]["match_type"], "unmapped")
        self.assertEqual(results.iloc[0]["matched_occupation_id"], None)
        self.assertEqual(results.iloc[0]["matched_level_2"], "卫星与空间信息")

    def test_colon_title_is_not_split_into_requirement_fragments(self) -> None:
        title = "金融业务类通用岗员工：经济、金融、财会"
        self.assertEqual(split_title_units(title), [title])
        gated = split_title_units_with_quality(title)
        self.assertEqual(gated[0].gate_status, "review_required")

    def test_single_normal_job_is_accepted(self) -> None:
        gated = split_title_units_with_quality("人工智能算法研发工程师")
        self.assertEqual([item.unit for item in gated], ["人工智能算法研发工程师"])
        self.assertEqual(gated[0].gate_status, "accepted")

    def test_normal_multi_job_list_is_split_and_accepted(self) -> None:
        gated = split_title_units_with_quality("软件工程师、测试工程师、运维工程师")
        self.assertEqual([item.unit for item in gated], ["软件工程师", "测试工程师", "运维工程师"])
        self.assertTrue(all(item.gate_status == "accepted" for item in gated))

    def test_parenthesized_locations_are_not_split_into_units(self) -> None:
        gated = split_title_units_with_quality("解决方案工程师（上海、苏州、广州，本科）;系统集成工程师（北京、成都，本科）")
        self.assertEqual([item.unit for item in gated], ["解决方案工程师（上海、苏州、广州，本科）", "系统集成工程师（北京、成都，本科）"])
        self.assertTrue(all(item.gate_status == "accepted" for item in gated))

    def test_parenthesized_major_or_education_context_is_not_split(self) -> None:
        gated = split_title_units_with_quality("专业技术类岗位（计算机类、人工智能、数据科学专业）")
        self.assertEqual([item.unit for item in gated], ["专业技术类岗位（计算机类、人工智能、数据科学专业）"])
        self.assertEqual(gated[0].gate_status, "review_required")

    def test_department_plus_job_is_kept_as_review_when_role_is_unclear(self) -> None:
        gated = split_title_units_with_quality("市场营销中心专业技术类岗位（工商管理类、应用经济学类专业）")
        self.assertEqual(len(gated), 1)
        self.assertEqual(gated[0].gate_status, "review_required")

    def test_job_with_business_direction_can_be_accepted(self) -> None:
        gated = split_title_units_with_quality("技术支持工程师-AR方向")
        self.assertEqual(gated[0].gate_status, "accepted")

    def test_very_long_job_catalog_accepts_clear_job_units(self) -> None:
        title = "、".join(f"软件开发工程师{i}" for i in range(12))
        gated = split_title_units_with_quality(title)
        self.assertEqual(len(gated), 12)
        self.assertTrue(all(item.gate_status == "accepted" for item in gated))

    def test_category_label_with_long_job_catalog_excludes_labels_and_accepts_jobs(self) -> None:
        title = "技术类：算法工程师、软件开发工程师、测试工程师；产品类：产品经理、产品运营"
        gated = split_title_units_with_quality(title)
        self.assertEqual(
            [item.unit for item in gated],
            ["算法工程师", "软件开发工程师", "测试工程师", "产品经理", "产品运营"],
        )
        self.assertTrue(all(item.gate_status == "accepted" for item in gated))

    def test_clear_role_structure_without_old_marker_is_accepted(self) -> None:
        for title in ["工程调试", "产品工艺", "合同履约", "销售代表"]:
            with self.subTest(title=title):
                gated = split_title_units_with_quality(title)
                self.assertEqual(gated[0].gate_status, "accepted")
                self.assertEqual(gated[0].gate_reason, "clear_role_structure")

    def test_colon_requirement_context_is_not_parsed_as_job_list(self) -> None:
        title = "专业要求：计算机类、数学类、统计学类"
        gated = split_title_units_with_quality(title)
        self.assertEqual([item.unit for item in gated], [title])
        self.assertEqual(gated[0].gate_status, "review_required")

    def test_parenthesized_major_context_is_removed_from_role_body(self) -> None:
        gated = split_title_units_with_quality("项目经理（相关专业：计算机类、管理类，本科）")
        self.assertEqual(len(gated), 1)
        self.assertEqual(gated[0].unit, "项目经理")
        self.assertEqual(gated[0].gate_status, "accepted")

    def test_department_or_business_direction_is_not_accepted_as_a_job(self) -> None:
        for title in ["研发中心", "人工智能方向", "产品类", "工商管理"]:
            with self.subTest(title=title):
                gated = split_title_units_with_quality(title)
                self.assertNotEqual(gated[0].gate_status, "accepted")

    def test_concatenated_chinese_role_tokens_are_split_atomically(self) -> None:
        gated = split_title_units_with_quality("算法工程师软件开发工程师测试工程师")
        self.assertEqual([item.unit for item in gated], ["算法工程师", "软件开发工程师", "测试工程师"])
        self.assertTrue(all(item.gate_status == "accepted" for item in gated))

    def test_concatenated_roles_with_spaces_are_split_atomically(self) -> None:
        gated = split_title_units_with_quality("硬件研发工程师 技术支持工程师 销售工程师")
        self.assertEqual([item.unit for item in gated], ["硬件研发工程师", "技术支持工程师", "销售工程师"])

    def test_role_with_parenthesized_direction_remains_atomic(self) -> None:
        gated = split_title_units_with_quality("高级软件开发工程师（Java方向）")
        self.assertEqual([item.unit for item in gated], ["高级软件开发工程师（Java方向）"])
        self.assertEqual(gated[0].gate_status, "accepted")

    def test_ambiguous_unsplittable_multi_job_text_stays_review(self) -> None:
        gated = split_title_units_with_quality("销售管培生（国内、售前管培生（海外）、人力资源管培生")
        self.assertEqual(len(gated), 1)
        self.assertEqual(gated[0].gate_status, "review_required")
        self.assertEqual(gated[0].gate_reason, "ambiguous_multi_job_concatenation")

    def test_colon_followed_by_multi_job_list_can_split(self) -> None:
        gated = split_title_units_with_quality("招聘岗位：软件工程师、测试工程师、产品经理")
        self.assertEqual([item.unit for item in gated], ["软件工程师", "测试工程师", "产品经理"])
        self.assertTrue(all(item.gate_status == "accepted" for item in gated))

    def test_non_job_fragments_are_rejected(self) -> None:
        gated = split_title_units_with_quality("北京、硕士、计算机类、软件工程师")
        self.assertEqual([item.gate_status for item in gated], ["rejected_non_job_fragment", "rejected_non_job_fragment", "rejected_non_job_fragment", "accepted"])

    def test_mixed_chinese_english_title_is_accepted(self) -> None:
        gated = split_title_units_with_quality("AI Infra工程师")
        self.assertEqual(gated[0].gate_status, "accepted")

    def test_appended_top_level_major_requirement_is_not_a_position_list(self) -> None:
        gated = split_title_units_with_quality(
            "销售管培生,操作管培生,客服管培生专业不限、国际贸易、物流、商务英语、外语"
        )
        self.assertEqual([item.unit for item in gated], ["销售管培生", "操作管培生", "客服管培生"])
        self.assertTrue(all(item.gate_status == "accepted" for item in gated))

    def test_english_design_role_list_is_split_and_accepted(self) -> None:
        gated = split_title_units_with_quality(
            "Headquarters Trainee、Womenswear Design、Menswear Design、Accessories Design、Spatial Design、Graphic Des"
        )
        self.assertEqual(
            [item.unit for item in gated],
            ["Headquarters Trainee", "Womenswear Design", "Menswear Design", "Accessories Design", "Spatial Design", "Graphic Des"],
        )
        self.assertTrue(all(item.gate_status == "accepted" for item in gated))

    def test_english_role_markers_not_limited_to_the_final_word(self) -> None:
        gated = split_title_units_with_quality(
            "Customer Operations Officer、Planning & Delivery Leader、Management Trainee - Sales"
        )
        self.assertTrue(all(item.gate_status == "accepted" for item in gated))

    def test_quality_gate_rows_are_retained_but_not_mapped(self) -> None:
        results = analyse_coverage(
            [{"record_id": "r3", "row_number": 3, "job_title": "北京、软件工程师", "company_name": "A", "industry_category": "互联网", "location": "上海", "major_requirement": None, "education_requirement": None}],
            TAXONOMY,
        )
        self.assertEqual(len(results), 2)
        rejected = results[results["gate_status"] == "rejected_non_job_fragment"].iloc[0]
        accepted = results[results["gate_status"] == "accepted"].iloc[0]
        self.assertEqual(rejected["job_title_unit"], "北京")
        self.assertEqual(rejected["match_type"], "not_mapped_quality_gate")
        self.assertEqual(accepted["matched_occupation_name"], "软件工程师")


class CrossIndustryTaxonomyModelTests(unittest.TestCase):
    def test_occupation_can_have_canonical_and_multiple_applicable_domains(self) -> None:
        occupation = CanonicalOccupation(
            canonical_occupation_id="OCC-X",
            standard_title="销售工程师",
            definition="提供技术方案支持的销售职业。",
            aliases=("技术销售工程师",),
            status="proposed",
            taxonomy_version="v-next",
            domain_links=(
                OccupationDomainLink("OCC-X", "商业与企业服务", "销售与客户成功", "canonical"),
                OccupationDomainLink("OCC-X", "智能制造与工业", "机械设计与装备", "applicable"),
            ),
        )
        self.assertEqual(occupation.canonical_domain.relationship_type, "canonical")
        self.assertEqual(len(occupation.domain_links), 2)
        self.assertEqual({link.occupation_id for link in occupation.domain_links}, {"OCC-X"})

    def test_identity_and_placement_are_independent(self) -> None:
        review = SemanticCandidateReviewV2(
            family_id="PCF-X",
            representative_title="销售工程师",
            identity_decision="proposed_new_occupation",
            placement_status="placement_review_required",
            matched_existing_canonical_occupation_id=None,
            matched_existing_canonical_occupation_title=None,
            recommended_standard_title="销售工程师",
            canonical_level_1=None,
            canonical_level_2=None,
            applicable_domains=(),
            career_or_program_modifiers=(),
        )
        self.assertEqual(review.identity_decision, "proposed_new_occupation")
        self.assertEqual(review.placement_status, "placement_review_required")

    def test_cross_industry_does_not_duplicate_occupation_id(self) -> None:
        review = SemanticCandidateReviewV2(
            family_id="PCF-Y",
            representative_title="技术支持工程师",
            identity_decision="proposed_new_occupation",
            placement_status="cross_industry",
            matched_existing_canonical_occupation_id=None,
            matched_existing_canonical_occupation_title=None,
            recommended_standard_title="技术支持工程师",
            canonical_level_1="信息技术与数字产业",
            canonical_level_2="IT服务与运维",
            applicable_domains=(
                OccupationDomainLink("OCC-Y", "信息技术与数字产业", "IT服务与运维", "canonical"),
                OccupationDomainLink("OCC-Y", "电子信息与通信产业", "通信网络", "applicable"),
            ),
            career_or_program_modifiers=("management_trainee",),
        )
        self.assertEqual(len({link.occupation_id for link in review.applicable_domains}), 1)
        self.assertEqual(review.career_or_program_modifiers, ("management_trainee",))

    def test_legacy_taxonomy_adapts_without_changing_reader_contract(self) -> None:
        entries, _ = load_reference_taxonomy(TAXONOMY)
        occupations = canonical_occupations_from_legacy_entries(entries, taxonomy_version="legacy-v4")
        self.assertEqual(len(occupations), 452)
        self.assertEqual(occupations[0].canonical_occupation_id, entries[0].occupation_id)
        self.assertEqual(occupations[0].canonical_domain.level_1, entries[0].level_1)
        self.assertEqual(occupations[0].canonical_domain.relationship_type, "canonical")

    def test_v2_preparation_preserves_v1_and_targets_all_pending_cases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            queue_path = directory / "queue.jsonl"
            queue_rows = [
                {"priority_tier": "P0", "representative_title": title}
                for title in P0_REVIEW_TARGETS
            ]
            queue_rows.extend(
                {"priority_tier": "P0", "representative_title": f"other-{index}"}
                for index in range(10)
            )
            queue_path.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in queue_rows) + "\n",
                encoding="utf-8",
            )
            v1_path = directory / "semantic_review_p0_results.jsonl"
            v1_payload = '{"semantic_review_version":"semantic-review-v1"}\n'
            v1_path.write_text(v1_payload, encoding="utf-8")
            v2_path = directory / "semantic_review_p0_v2_results.jsonl"

            plan = prepare_p0_v2_re_review(queue_path, v1_path, v2_path)

            self.assertEqual(plan.queued_p0_family_count, 22)
            self.assertEqual(plan.p0_pending_identity_or_placement_titles, P0_REVIEW_TARGETS)
            self.assertEqual(v1_path.read_text(encoding="utf-8"), v1_payload)
            self.assertFalse(v2_path.exists())


if __name__ == "__main__":
    unittest.main()
