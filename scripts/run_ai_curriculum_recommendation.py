"""One-request, evidence-bounded MVP curriculum recommendation runner."""
from __future__ import annotations
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "backend")
from app.domain.curriculum.recommendations import structured_output_schema, validate_recommendation_output, validate_structured_schema_locally
from run_skill_inference_v2_pilot import ENDPOINT, extract_response_text, extract_usage, load_project_dotenv, classify_exception

MODEL = "gpt-4.1-mini"
PROMPT_VERSION = "curriculum-recommendation-prompt-v2-structured"
OUTPUT_DIR = Path("data/processed/recommendations")
PROGRAM_PATH = Path("data/demo/curriculum/demo_program.json")
PROFILE_PATH = Path("data/processed/curriculum/curriculum_skill_profile.json")
GAP_PATH = Path("data/processed/curriculum/curriculum_gap_analysis.json")
REPORT_PATH = Path("docs/reports/ai-curriculum-recommendation.md")

INSTRUCTIONS = """You produce evidence-bounded curriculum decision-support suggestions for a demo IT programme. Return the result as a json object that exactly follows the supplied strict schema. Populate every required field: program_id, overall_summary, and every recommendation field. Use recommendation_id values REC-001, REC-002, and so on. limitations must always be JSON arrays of strings; use [] if none apply. Use only course IDs, target skill names, gap IDs, market evidence IDs, and curriculum evidence IDs supplied in the input. Do not invent courses, learning outcomes, demand weights, evidence, skills, or gap IDs. Market skills are candidate skills inferred from recruitment role context, not directly stated job requirements. A curriculum status of not_observed means no skill evidence was observed in the supplied demo text; it does not prove absence from teaching. Treat the programme content as demo/sample rather than an official syllabus. Prioritise bounded modifications to existing courses; do not recommend adding every market skill. recommendation_type must be exactly one of strengthen_existing_content, integrate_skill_into_existing_course, assessment_adjustment, learning_outcome_adjustment, optional_module_or_activity. confidence must be exactly high, medium, or low. Each recommendation must contain non-empty target_courses, target_skills, gap_ids, and market_evidence. curriculum_evidence may be empty only where no supplied evidence is relevant."""


def bounded(values, size):
    return list(values or [])[:size]


def build_input():
    program = json.loads(PROGRAM_PATH.read_text(encoding="utf-8"))
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    gap = json.loads(GAP_PATH.read_text(encoding="utf-8"))
    course_ids = {course["course_id"] for course in program["courses"]}
    curriculum_evidence = []
    for index, item in enumerate(profile["covered_skills"], start=1):
        curriculum_evidence.append({
            "curriculum_evidence_id": f"curriculum-{index:02d}", "normalized_skill": item["normalized_skill"],
            "supporting_course_ids": bounded(item.get("supporting_course_ids"), 3),
            "supporting_learning_outcomes": bounded(item.get("supporting_learning_outcomes"), 2),
            "evidence_count": item["evidence_count"],
        })
    gaps = []
    market_evidence = []
    for index, item in enumerate(gap["final_actionable_candidates"], start=1):
        gap_id = f"gap-{index:02d}"; market_id = f"market-gap-{index:02d}"
        evidence = item["market_evidence_summary"]
        market_evidence.append({
            "market_evidence_id": market_id, "normalized_skill": item["normalized_skill"], "skill_type": item["skill_type"],
            "skill_scope": item["skill_scope"], "demand_weight": item["market_demand_weight"],
            "supporting_job_group_count": evidence["supporting_job_group_count"],
            "representative_job_group_ids": bounded(evidence.get("representative_job_group_ids"), 5),
            "representative_domains": bounded(evidence.get("representative_domains"), 3),
        })
        gaps.append({
            "gap_id": gap_id, "market_evidence_id": market_id, "normalized_skill": item["normalized_skill"],
            "skill_type": item["skill_type"], "skill_scope": item["skill_scope"], "priority": item["priority"],
            "market_demand_weight": item["market_demand_weight"], "program_relevance": item["program_relevance"],
            "curriculum_status": item["curriculum_status"], "reason_codes": item["reason_codes"],
            "curriculum_evidence_count": item["curriculum_evidence_summary"]["evidence_count"],
        })
    result = {
        "input_schema_version": "curriculum-recommendation-input-v1",
        "program": {"program_id": program["program_id"], "program_name": program["program_name"], "description": program["description"], "provenance": program["provenance"], "courses": [{"course_id": c["course_id"], "course_name": c["course_name"], "learning_outcomes": c["learning_outcomes"], "assessments": c.get("assessments", [])} for c in program["courses"]]},
        "market_evidence": market_evidence, "curriculum_evidence": curriculum_evidence, "structural_gaps": gaps,
        "evidence_boundary": {"market_skills": "Candidate skills inferred from recruitment role context; demand weights were calculated deterministically from persisted results.", "curriculum": "MVP demo/sample curriculum content, not an official syllabus.", "not_observed": "No supplied curriculum-text evidence was observed; this does not confirm absence from teaching.", "recommendations": "Decision-support suggestions, not authoritative curriculum decisions."},
    }
    refs = {"program_id": program["program_id"], "course_ids": course_ids, "skill_names": {x["normalized_skill"] for x in market_evidence} | {x["normalized_skill"] for x in curriculum_evidence}, "gap_ids": {x["gap_id"] for x in gaps}, "market_evidence_ids": {x["market_evidence_id"] for x in market_evidence}, "curriculum_evidence_ids": {x["curriculum_evidence_id"] for x in curriculum_evidence}}
    return result, refs


def make_request(compact_input):
    actual_input = "Return the following curriculum recommendation as a json object.\n" + json.dumps(compact_input, ensure_ascii=False, separators=(",", ":"))
    return {"model": MODEL, "instructions": INSTRUCTIONS, "input": actual_input, "text": {"format": {"type": "json_schema", "name": "curriculum_recommendation", "strict": True, "schema": structured_output_schema()}}, "store": False}


def preflight(body):
    errors = []
    if body.get("model") != MODEL: errors.append("model contract failed")
    if not ENDPOINT.endswith("/v1/responses"): errors.append("endpoint contract failed")
    if not body.get("instructions") or not body.get("input"): errors.append("instructions/input required")
    fmt = ((body.get("text") or {}).get("format") or {})
    if fmt.get("type") != "json_schema" or fmt.get("strict") is not True or not isinstance(fmt.get("schema"), dict): errors.append("strict json_schema format required")
    if fmt.get("schema") != structured_output_schema(): errors.append("request schema differs from local contract")
    if not PROMPT_VERSION: errors.append("prompt version required")
    return errors


def call_once(body):
    request = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode("utf-8"), headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"], "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.loads(response.read())


def report(result):
    meta = result["metadata"]; lines = ["# AI Curriculum Recommendation MVP", "", "## Evidence boundary", "", "- Recruitment skills are candidate skills inferred from job-group context, not stated recruitment requirements.", "- Curriculum content is MVP demo/sample material, not an official syllabus.", "- `not_observed` means no supplied curriculum-text evidence was observed; it does not prove absence from teaching.", "- Recommendations are decision-support suggestions, not authoritative curriculum decisions.", "", "## Execution", "", f"- Model: `{meta['model']}`", f"- Prompt version: `{meta['prompt_version']}`", f"- API request attempts: {meta['api_request_attempts']}", f"- Validation status: `{meta['validation_status']}`"]
    if meta["validation_status"] == "passed":
        lines += ["", "## Recommendations", ""]
        for item in result["recommendation_output"]["recommendations"]:
            lines.append(f"- **{item['title']}** ({item['recommendation_type']}) — target skills: {', '.join(item['target_skills'])}; gaps: {', '.join(item['gap_ids'])}; market refs: {', '.join(item['market_evidence'])}; curriculum refs: {', '.join(item['curriculum_evidence']) or 'none'}.")
    else: lines += ["", "## Failure", "", "No recommendation was accepted because the single response did not pass deterministic validation. No retry was made."]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True); REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_contract_diff():
    raw_path = OUTPUT_DIR / "raw_model_output.json"
    if not raw_path.exists(): return
    actual = json.loads(raw_path.read_text(encoding="utf-8"))
    diff = {"source": "first recommendation API response", "structured_schema_errors": validate_structured_schema_locally(actual), "domain_validation_errors": []}
    try:
        _, refs = build_input(); diff["domain_validation_errors"] = validate_recommendation_output(actual, **refs)
    except Exception as error: diff["domain_validation_errors"] = [f"offline diff failed: {type(error).__name__}"]
    (OUTPUT_DIR / "first_attempt_contract_diff.json").write_text(json.dumps(diff, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    load_project_dotenv(); compact_input, refs = build_input(); OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fingerprint = hashlib.sha256(json.dumps(compact_input, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    input_artifact = {"metadata": {"model": MODEL, "prompt_version": PROMPT_VERSION, "input_fingerprint": fingerprint, "api_request_limit": 1}, "input": compact_input}
    (OUTPUT_DIR / "recommendation_input.json").write_text(json.dumps(input_artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_contract_diff()
    body = make_request(compact_input); errors = preflight(body)
    metadata = {"model": MODEL, "prompt_version": PROMPT_VERSION, "input_fingerprint": fingerprint, "api_request_attempts": 0, "api_successful_responses": 0, "validation_status": "not_started", "token_usage": {"input_tokens": None, "output_tokens": None, "total_tokens": None, "estimated_cost": None}, "created_at": datetime.now(timezone.utc).isoformat()}
    if errors or not os.environ.get("OPENAI_API_KEY"):
        metadata["validation_status"] = "local_preflight_failed"; metadata["errors"] = errors or ["OPENAI_API_KEY not detected"]
        result = {"metadata": metadata}; (OUTPUT_DIR / "recommendation_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); report(result); print(json.dumps(metadata, ensure_ascii=False)); return
    metadata["api_request_attempts"] = 1
    try:
        response = call_once(body); metadata["api_successful_responses"] = 1; metadata["token_usage"] = extract_usage(response)
        raw_text = extract_response_text(response); raw = json.loads(raw_text)
        (OUTPUT_DIR / "raw_model_output.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception as error:
        metadata["validation_status"] = "failed"; metadata["diagnostic"] = classify_exception(error, request_stage="recommendation_request", validation_stage="response_extraction_or_json_parse", response_received=not isinstance(error, (urllib.error.HTTPError, urllib.error.URLError)))
        result = {"metadata": metadata}; (OUTPUT_DIR / "recommendation_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); report(result); print(json.dumps(metadata, ensure_ascii=False)); return
    schema_errors = validate_structured_schema_locally(raw)
    contract_errors = validate_recommendation_output(raw, **refs) if not schema_errors else []
    all_errors = schema_errors + contract_errors
    metadata["validation_status"] = "passed" if not all_errors else "failed"
    if all_errors: metadata["validation_errors"] = all_errors
    result = {"metadata": metadata, "recommendation_output": raw}
    (OUTPUT_DIR / "recommendation_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); report(result); print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
