from __future__ import annotations

import unittest

from app.domain.job_groups.occupation_identity import (
    has_specialisation_conflict,
    medium_identity_key,
    strict_identity_key,
)


class OccupationIdentityCandidateTests(unittest.TestCase):
    def test_candidate_generation_is_deterministic_for_safe_developer_variants(self) -> None:
        self.assertEqual(strict_identity_key("Java工程师"), strict_identity_key("Java开发工程师"))
        self.assertEqual(strict_identity_key("后端工程师"), strict_identity_key("服务端开发工程师"))

    def test_specialisation_protection_retains_testing_and_hardware_boundaries(self) -> None:
        groups = [{"representative_title": "硬件开发工程师"}, {"representative_title": "硬件测试工程师"}]
        self.assertTrue(has_specialisation_conflict(groups))
        self.assertNotEqual(strict_identity_key("软件开发工程师"), strict_identity_key("软件测试工程师"))

    def test_recruitment_modifiers_do_not_change_medium_identity_candidate(self) -> None:
        self.assertEqual(medium_identity_key("校招Java开发工程师"), medium_identity_key("Java开发工程师"))

    def test_generic_title_is_not_a_strict_identity_candidate(self) -> None:
        self.assertIsNone(strict_identity_key("工程师"))
        self.assertIsNone(strict_identity_key("管理培训生"))


if __name__ == "__main__":
    unittest.main()
