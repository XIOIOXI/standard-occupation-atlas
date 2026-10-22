import unittest
from app.domain.curriculum.recommendations import validate_recommendation_output, validate_structured_schema_locally


def valid_output():
    recommendation = {
        "recommendation_id": "rec-1", "title": "Strengthen secure development practice",
        "recommendation_type": "integrate_skill_into_existing_course", "target_courses": ["IFN711-demo"],
        "target_skills": ["网络安全与隐私保护"], "rationale": "Evidence-linked rationale.",
        "suggested_change": "Add a bounded activity.", "market_evidence": ["market-gap-01"],
        "curriculum_evidence": ["curriculum-01"], "gap_ids": ["gap-01"],
        "confidence": "medium", "limitations": ["Demo content only."],
    }
    return {"program_id": "program-1", "recommendations": [recommendation | {"recommendation_id": f"rec-{index}"} for index in range(1, 4)], "overall_summary": "Summary.", "limitations": ["Decision support only."]}


class RecommendationContractTests(unittest.TestCase):
    def kwargs(self):
        return {"program_id": "program-1", "course_ids": {"IFN711-demo"}, "skill_names": {"网络安全与隐私保护"}, "gap_ids": {"gap-01"}, "market_evidence_ids": {"market-gap-01"}, "curriculum_evidence_ids": {"curriculum-01"}}

    def test_valid_contract(self):
        self.assertEqual(validate_recommendation_output(valid_output(), **self.kwargs()), [])

    def test_unknown_course_rejected(self):
        value = valid_output(); value["recommendations"][0]["target_courses"] = ["unknown"]
        self.assertTrue(validate_recommendation_output(value, **self.kwargs()))

    def test_unknown_evidence_rejected(self):
        value = valid_output(); value["recommendations"][0]["market_evidence"] = ["invented"]
        self.assertTrue(validate_recommendation_output(value, **self.kwargs()))

    def test_recommendation_count_is_bounded(self):
        value = valid_output(); value["recommendations"] = value["recommendations"][:2]
        self.assertIn("recommendations must contain 3 to 5 items", validate_recommendation_output(value, **self.kwargs()))

    def test_local_schema_valid_fixture(self):
        self.assertEqual(validate_structured_schema_locally(valid_output()), [])

    def test_local_schema_rejects_missing_program_id(self):
        value = valid_output(); del value["program_id"]
        self.assertTrue(validate_structured_schema_locally(value))

    def test_local_schema_rejects_missing_title(self):
        value = valid_output(); del value["recommendations"][0]["title"]
        self.assertTrue(validate_structured_schema_locally(value))

    def test_local_schema_rejects_limitations_string(self):
        value = valid_output(); value["recommendations"][0]["limitations"] = "not an array"
        self.assertTrue(validate_structured_schema_locally(value))

    def test_domain_rejects_invalid_skill_gap_confidence_and_type(self):
        for field, invalid in (("target_skills", ["unknown"]), ("gap_ids", ["unknown"]), ("confidence", "unknown"), ("recommendation_type", "unknown")):
            value = valid_output(); value["recommendations"][0][field] = invalid
            self.assertTrue(validate_recommendation_output(value, **self.kwargs()), field)

    def test_local_schema_rejects_more_than_five_recommendations(self):
        value = valid_output(); value["recommendations"] += [value["recommendations"][0] | {"recommendation_id": "rec-4"}] * 3
        self.assertTrue(validate_structured_schema_locally(value))
