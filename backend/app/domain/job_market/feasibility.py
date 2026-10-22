"""Small deterministic aggregations used by the Job Market Intelligence audit."""
from __future__ import annotations
from collections import Counter, defaultdict


def occupation_key(group: dict) -> tuple[str, str, bool]:
    prepared = group.get("prepared_inference_input", {})
    canonical_id = prepared.get("canonical_occupation_id")
    canonical_title = prepared.get("canonical_occupation_title")
    if canonical_id:
        return f"canonical:{canonical_id}", canonical_title or group.get("representative_title", ""), True
    title = group.get("representative_title", "").strip()
    return f"candidate:{title.casefold()}", title, False


def build_occupation_inventory(groups: list[dict], results_by_id: dict[str, dict]) -> dict:
    records: dict[str, dict] = {}
    for group in groups:
        key, label, mapped = occupation_key(group)
        prepared = group.get("prepared_inference_input", {})
        result = results_by_id.get(group["job_group_id"], {})
        item = records.setdefault(key, {"occupation_key": key, "occupation_label": label, "canonical_occupation_id": prepared.get("canonical_occupation_id"), "mapped": mapped, "job_group_ids": [], "contexts": {}, "skill_names": set(), "hard_skills": set(), "soft_skills": set(), "context_quality": Counter(), "recruitment_evidence_count": 0, "completed_inference_group_count": 0})
        item["job_group_ids"].append(group["job_group_id"])
        context = prepared.get("industry_domain_context") or "unknown"
        context_item = item["contexts"].setdefault(context, {"context": context, "job_group_ids": [], "recruitment_evidence_count": 0, "completed_inference_group_count": 0, "skills": set(), "core_skills": set(), "domain_specific_skills": set()})
        context_item["job_group_ids"].append(group["job_group_id"])
        record_ids = prepared.get("source_recruitment_record_ids", [])
        evidence_count = len(record_ids) or int(group.get("occurrence_count", 0) or 0)
        item["recruitment_evidence_count"] += evidence_count; context_item["recruitment_evidence_count"] += evidence_count
        quality = prepared.get("context_quality", "unknown"); item["context_quality"][quality] += 1
        if result.get("inference_status") == "completed":
            item["completed_inference_group_count"] += 1; context_item["completed_inference_group_count"] += 1
        for skill in result.get("hard_skills", []) + result.get("soft_skills", []):
            name = skill.get("normalized_skill_name") or skill.get("normalized_skill")
            if not name: continue
            item["skill_names"].add(name); context_item["skills"].add(name)
            if skill.get("skill_type") == "hard": item["hard_skills"].add(name)
            elif skill.get("skill_type") == "soft": item["soft_skills"].add(name)
            if skill.get("skill_scope") == "occupation_core": context_item["core_skills"].add(name)
            elif skill.get("skill_scope") == "domain_specific": context_item["domain_specific_skills"].add(name)
    def clean(item):
        item = dict(item); item["context_quality"] = dict(item["context_quality"])
        for field in ("skill_names", "hard_skills", "soft_skills"): item[field] = sorted(item[field])
        contexts = []
        for context, data in sorted(item.pop("contexts").items()):
            data = dict(data); data["skills"] = sorted(data["skills"]); data["core_skills"] = sorted(data["core_skills"]); data["domain_specific_skills"] = sorted(data["domain_specific_skills"]); contexts.append(data)
        item["contexts"] = contexts; item["industry_domain_context_count"] = len(contexts); item["job_group_count"] = len(item["job_group_ids"]); item["normalized_unique_skill_count"] = len(item["skill_names"]); item["hard_skill_count"] = len(item["hard_skills"]); item["soft_skill_count"] = len(item["soft_skills"])
        return item
    cleaned = [clean(item) for item in records.values()]
    return {"occupations": sorted(cleaned, key=lambda x: (-x["recruitment_evidence_count"], x["occupation_label"])), "mapped_occupation_count": sum(x["mapped"] for x in cleaned), "unmapped_occupation_count": sum(not x["mapped"] for x in cleaned)}


def build_comparison_candidates(inventory: dict, *, min_skills_per_context: int = 3) -> dict:
    candidates = []
    for occupation in inventory["occupations"]:
        contexts = occupation["contexts"]
        if len(contexts) < 2: continue
        if any(c["completed_inference_group_count"] < 1 or c["recruitment_evidence_count"] < 1 or len(c["skills"]) < min_skills_per_context for c in contexts): continue
        shared = set(contexts[0]["skills"])
        for context in contexts[1:]: shared &= set(context["skills"])
        union = set().union(*(set(c["skills"]) for c in contexts))
        distinctive = {c["context"]: sorted(set(c["skills"]) - (union - set(c["skills"]))) for c in contexts}
        if not shared or not any(distinctive.values()): continue
        candidates.append({"occupation_key": occupation["occupation_key"], "occupation_label": occupation["occupation_label"], "mapped": occupation["mapped"], "contexts": [{"context": c["context"], "recruitment_evidence_count": c["recruitment_evidence_count"], "completed_inference_group_count": c["completed_inference_group_count"], "skill_count": len(c["skills"])} for c in contexts], "shared_skills": sorted(shared), "context_specific_skills": distinctive, "eligibility_rule": {"minimum_contexts": 2, "minimum_completed_groups_per_context": 1, "minimum_recruitment_evidence_per_context": 1, "minimum_skills_per_context": min_skills_per_context, "requires_shared_and_distinctive_skills": True}})
    return {"eligibility_rule": {"minimum_contexts": 2, "minimum_completed_groups_per_context": 1, "minimum_recruitment_evidence_per_context": 1, "minimum_skills_per_context": min_skills_per_context, "requires_shared_and_distinctive_skills": True}, "eligible_count": len(candidates), "candidates": sorted(candidates, key=lambda x: (-len(x["shared_skills"]), x["occupation_label"]))}


def select_demo_occupations(inventory: dict, comparisons: dict, limit: int = 10) -> list[dict]:
    eligible = {x["occupation_key"]: x for x in comparisons["candidates"]}
    rows = []
    for occupation in inventory["occupations"]:
        if occupation["occupation_key"] not in eligible: continue
        comparison = eligible[occupation["occupation_key"]]
        distinctive_count = sum(len(value) for value in comparison["context_specific_skills"].values())
        score = len(occupation["contexts"]) * 100 + min(occupation["recruitment_evidence_count"], 100) + occupation["completed_inference_group_count"] * 5 + occupation["normalized_unique_skill_count"] * 2 + len(comparison["shared_skills"]) * 10 + distinctive_count * 5
        rows.append({"occupation": occupation["occupation_label"], "occupation_key": occupation["occupation_key"], "contexts": [c["context"] for c in occupation["contexts"]], "evidence_volume": occupation["recruitment_evidence_count"], "completed_inference_groups": occupation["completed_inference_group_count"], "skill_count": occupation["normalized_unique_skill_count"], "shared_skills": comparison["shared_skills"], "distinctive_skills_by_context": comparison["context_specific_skills"], "deterministic_demo_score": score, "selection_basis": "context_count + evidence + completed inference + shared/distinctive skill structure"})
    return sorted(rows, key=lambda x: (-x["deterministic_demo_score"], x["occupation"]))[:limit]
