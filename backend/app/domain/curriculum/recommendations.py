"""Deterministic validation contract for MVP curriculum recommendations."""
from __future__ import annotations

VALID_RECOMMENDATION_TYPES = {
    "strengthen_existing_content",
    "integrate_skill_into_existing_course",
    "assessment_adjustment",
    "learning_outcome_adjustment",
    "optional_module_or_activity",
}
VALID_CONFIDENCE = {"high", "medium", "low"}

RECOMMENDATION_REQUIRED_FIELDS = {
    "recommendation_id", "title", "recommendation_type", "target_courses",
    "target_skills", "rationale", "suggested_change", "market_evidence",
    "curriculum_evidence", "gap_ids", "confidence", "limitations",
}
TOP_LEVEL_REQUIRED_FIELDS = {"program_id", "recommendations", "overall_summary", "limitations"}


def structured_output_schema() -> dict:
    """Responses API strict JSON Schema, deliberately aligned with domain validation."""
    string_array = {"type": "array", "items": {"type": "string"}}
    recommendation = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "recommendation_id": {"type": "string"}, "title": {"type": "string"},
            "recommendation_type": {"type": "string", "enum": sorted(VALID_RECOMMENDATION_TYPES)},
            "target_courses": string_array, "target_skills": string_array,
            "rationale": {"type": "string"}, "suggested_change": {"type": "string"},
            "market_evidence": string_array, "curriculum_evidence": string_array,
            "gap_ids": string_array,
            "confidence": {"type": "string", "enum": sorted(VALID_CONFIDENCE)},
            "limitations": string_array,
        }, "required": sorted(RECOMMENDATION_REQUIRED_FIELDS),
    }
    return {"type": "object", "additionalProperties": False, "properties": {
        "program_id": {"type": "string"},
        "recommendations": {"type": "array", "minItems": 3, "maxItems": 5, "items": recommendation},
        "overall_summary": {"type": "string"}, "limitations": string_array,
    }, "required": sorted(TOP_LEVEL_REQUIRED_FIELDS)}


def validate_structured_schema_locally(output: object) -> list[str]:
    """Small fixture-oriented mirror of the strict schema, with no external dependency."""
    errors: list[str] = []
    if not isinstance(output, dict): return ["top_level must be an object"]
    missing = sorted(TOP_LEVEL_REQUIRED_FIELDS - output.keys())
    if missing: errors.append("top_level missing fields: " + ", ".join(missing))
    extra = sorted(output.keys() - TOP_LEVEL_REQUIRED_FIELDS)
    if extra: errors.append("top_level has unexpected fields: " + ", ".join(extra))
    if "program_id" in output and not isinstance(output["program_id"], str): errors.append("program_id must be a string")
    if "overall_summary" in output and not isinstance(output["overall_summary"], str): errors.append("overall_summary must be a string")
    if "limitations" in output and (not isinstance(output["limitations"], list) or any(not isinstance(x, str) for x in output["limitations"])): errors.append("top_level limitations must be an array of strings")
    recommendations = output.get("recommendations")
    if not isinstance(recommendations, list) or not 3 <= len(recommendations) <= 5:
        return errors + ["recommendations must contain 3 to 5 items"]
    string_fields = {"recommendation_id", "title", "rationale", "suggested_change"}
    array_fields = {"target_courses", "target_skills", "market_evidence", "curriculum_evidence", "gap_ids", "limitations"}
    for index, recommendation in enumerate(recommendations, start=1):
        label = f"recommendation[{index}]"
        if not isinstance(recommendation, dict): errors.append(f"{label} must be an object"); continue
        missing = sorted(RECOMMENDATION_REQUIRED_FIELDS - recommendation.keys())
        extra = sorted(recommendation.keys() - RECOMMENDATION_REQUIRED_FIELDS)
        if missing: errors.append(f"{label} missing fields: {', '.join(missing)}")
        if extra: errors.append(f"{label} has unexpected fields: {', '.join(extra)}")
        for field in string_fields:
            if field in recommendation and not isinstance(recommendation[field], str): errors.append(f"{label} {field} must be a string")
        for field in array_fields:
            if field in recommendation and (not isinstance(recommendation[field], list) or any(not isinstance(x, str) for x in recommendation[field])): errors.append(f"{label} {field} must be an array of strings")
        if "recommendation_type" in recommendation and recommendation["recommendation_type"] not in VALID_RECOMMENDATION_TYPES: errors.append(f"{label} has invalid recommendation_type")
        if "confidence" in recommendation and recommendation["confidence"] not in VALID_CONFIDENCE: errors.append(f"{label} has invalid confidence")
    return errors


def validate_recommendation_output(
    output: object,
    *,
    program_id: str,
    course_ids: set[str],
    skill_names: set[str],
    gap_ids: set[str],
    market_evidence_ids: set[str],
    curriculum_evidence_ids: set[str],
) -> list[str]:
    """Return deterministic, user-safe contract errors without repairing model output."""
    errors: list[str] = []
    if not isinstance(output, dict):
        return ["output must be a JSON object"]
    if output.get("program_id") != program_id:
        errors.append("program_id must match supplied program")
    recommendations = output.get("recommendations")
    if not isinstance(recommendations, list) or not 3 <= len(recommendations) <= 5:
        return errors + ["recommendations must contain 3 to 5 items"]
    if not isinstance(output.get("overall_summary"), str) or not output["overall_summary"].strip():
        errors.append("overall_summary must be a non-empty string")
    if not isinstance(output.get("limitations"), list):
        errors.append("limitations must be a list")
    seen_ids: set[str] = set()
    required = RECOMMENDATION_REQUIRED_FIELDS
    for index, recommendation in enumerate(recommendations, start=1):
        label = f"recommendation[{index}]"
        if not isinstance(recommendation, dict):
            errors.append(f"{label} must be an object")
            continue
        missing = sorted(required - recommendation.keys())
        if missing:
            errors.append(f"{label} missing fields: {', '.join(missing)}")
            continue
        recommendation_id = recommendation["recommendation_id"]
        if not isinstance(recommendation_id, str) or not recommendation_id.strip() or recommendation_id in seen_ids:
            errors.append(f"{label} has invalid or duplicate recommendation_id")
        seen_ids.add(recommendation_id)
        if not isinstance(recommendation["title"], str) or not recommendation["title"].strip():
            errors.append(f"{label} title must be non-empty")
        if recommendation["recommendation_type"] not in VALID_RECOMMENDATION_TYPES:
            errors.append(f"{label} has invalid recommendation_type")
        if recommendation["confidence"] not in VALID_CONFIDENCE:
            errors.append(f"{label} has invalid confidence")
        for field, allowed, require_nonempty in (
            ("target_courses", course_ids, True),
            ("target_skills", skill_names, True),
            ("gap_ids", gap_ids, True),
            ("market_evidence", market_evidence_ids, True),
            ("curriculum_evidence", curriculum_evidence_ids, False),
        ):
            value = recommendation[field]
            if not isinstance(value, list) or (require_nonempty and not value):
                errors.append(f"{label} {field} must be a non-empty list" if require_nonempty else f"{label} {field} must be a list")
            elif any(not isinstance(item, str) or item not in allowed for item in value):
                errors.append(f"{label} contains an unknown {field} reference")
        for field in ("rationale", "suggested_change"):
            if not isinstance(recommendation[field], str) or not recommendation[field].strip():
                errors.append(f"{label} {field} must be non-empty")
        if not isinstance(recommendation["limitations"], list):
            errors.append(f"{label} limitations must be a list")
    return errors
