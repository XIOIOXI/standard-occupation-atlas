"""Execute the approved v2 semantic re-review for the 12 frozen P0 pending families.

This is a bounded, versioned semantic-review artifact generator.  It never
updates the Reference Taxonomy, coverage mapping, candidate queue, or v1
results, and it refuses to process P1 or the other ten P0 families.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.domain.taxonomy.coverage import load_reference_taxonomy
from app.domain.taxonomy.models import OccupationDomainLink, SemanticCandidateReviewV2
from app.domain.taxonomy.semantic_review_v2 import (
    P0_REVIEW_TARGETS,
    PROMPT_VERSION,
    SEMANTIC_REVIEW_VERSION,
)


MODEL = "gpt-5 (Codex runtime)"

# These bounded semantic interpretations are the approved P0 re-review scope.
# They are recommendations only and are intentionally kept separate from the
# Reference Taxonomy and deterministic market statistics.
REVIEW_PLAN: dict[str, dict[str, Any]] = {
    "测试工程师": {
        "identity_decision": "pending_identity_review", "placement_status": "context_dependent",
        "title": None, "canonical": None, "domains": [],
        "reason": "The title covers software, semiconductor, and industrial validation contexts in the supplied evidence; those contexts can denote materially different occupation identities, not merely different placements.",
    },
    "客户经理": {
        "identity_decision": "pending_identity_review", "placement_status": "context_dependent",
        "title": None, "canonical": None, "domains": [],
        "reason": "The supplied market contexts span banking and non-banking settings, while the current taxonomy contains bank-specific customer-manager identities. The generic title alone does not establish one reusable identity.",
    },
    "销售工程师": {
        "identity_decision": "proposed_new_occupation", "placement_status": "placement_review_required",
        "title": "销售工程师", "canonical": None, "domains": [],
        "reason": "The title is a specific, reusable occupation label across many companies. The current taxonomy has no demonstrated generic equivalent, but the supplied evidence does not justify one canonical Level-1/Level-2 placement yet.",
    },
    "结构工程师": {
        "identity_decision": "pending_identity_review", "placement_status": "context_dependent",
        "title": None, "canonical": None, "domains": [],
        "reason": "Existing entries use the same label for mechanical and civil-structure contexts, with additional automotive and medical-device variants. This is an identity collision, not only a multi-domain placement question.",
    },
    "产品工程师": {
        "identity_decision": "pending_identity_review", "placement_status": "context_dependent",
        "title": None, "canonical": None, "domains": [],
        "reason": "The evidence establishes market use across product and industrial contexts but does not delimit one stable occupation from product/process-engineering or product-management-adjacent meanings.",
    },
    "技术支持工程师": {
        "identity_decision": "proposed_new_occupation", "placement_status": "cross_industry",
        "title": "技术支持工程师", "canonical": ("信息技术与数字产业", "信息化与IT服务"),
        "domains": [
            ("信息技术与数字产业", "信息化与IT服务", "canonical"),
            ("电子信息与通信产业", "通信网络", "applicable"),
            ("先进材料与化工", "新材料产业化", "applicable"),
        ],
        "reason": "The title has a stable technical-support identity across many companies. Existing taxonomy entries evidence telecommunications and materials-specific support, while the supplied market evidence also spans IT and manufacturing; domain context should refine, not erase, the proposed identity.",
    },
    "财务专员": {
        "identity_decision": "proposed_new_occupation", "placement_status": "single_domain",
        "title": "财务专员", "canonical": ("金融与金融科技", "财务与会计"),
        "domains": [("金融与金融科技", "财务与会计", "canonical")],
        "reason": "The title is a concrete, reusable finance occupation label across multiple companies. It is not equivalent by name or stated boundary to the existing accountant, financial analyst, or finance-manager entries.",
    },
    "销售经理": {
        "identity_decision": "proposed_new_occupation", "placement_status": "placement_review_required",
        "title": "销售经理", "canonical": None, "domains": [],
        "reason": "The title expresses a stable, reusable management occupation and no equivalent generic Level-3 entry was identified. The available contexts span multiple sectors without supporting one canonical domain placement.",
    },
    "项目工程师": {
        "identity_decision": "proposed_new_occupation", "placement_status": "cross_industry",
        "title": "项目工程师", "canonical": ("商业与企业服务", "项目管理"),
        "domains": [
            ("商业与企业服务", "项目管理", "canonical"),
            ("新能源与能源产业", "储能", "applicable"),
            ("建筑与房地产", "工程管理", "applicable"),
        ],
        "reason": "The title is distinct from the existing project-manager titles and recurs across companies. It has a stable project-engineering identity; the energy and construction contexts are applicable domains rather than grounds to duplicate the occupation.",
    },
    "AI工程师": {
        "identity_decision": "too_generic", "placement_status": "context_dependent",
        "title": None, "canonical": None, "domains": [],
        "reason": "The title does not distinguish among existing AI algorithm, generative-AI, application, or embedded-AI occupation identities. High occurrence does not make this umbrella label a canonical Level-3 occupation.",
    },
    "项目助理": {
        "identity_decision": "pending_identity_review", "placement_status": "placement_review_required",
        "title": None, "canonical": None, "domains": [],
        "reason": "The supplied title signals assistance but does not establish whether the underlying work is project management, engineering delivery, consulting, or another project context. It cannot safely be equated with project-management specialist.",
    },
    "运维工程师": {
        "identity_decision": "pending_identity_review", "placement_status": "context_dependent",
        "title": None, "canonical": None, "domains": [],
        "reason": "The available contexts include IT operations, energy operations, and industrial maintenance. Existing IT-operations and wind-operations entries demonstrate that the shared label can hide different occupation identities.",
    },
}


def _domain_rows(family_id: str, domains: list[tuple[str, str, str]]) -> tuple[OccupationDomainLink, ...]:
    return tuple(
        OccupationDomainLink(
            occupation_id=f"PROPOSED-{family_id}", level_1=level_1, level_2=level_2,
            relationship_type=relationship_type,
        )
        for level_1, level_2, relationship_type in domains
    )


def _result_domains(domains: tuple[OccupationDomainLink, ...]) -> list[dict[str, str]]:
    return [
        {"level_1": domain.level_1, "level_2": domain.level_2, "relationship_type": domain.relationship_type}
        for domain in domains
    ]


def _validate_domain_pairs(domains: tuple[OccupationDomainLink, ...], known_pairs: set[tuple[str, str]]) -> None:
    invalid = [(domain.level_1, domain.level_2) for domain in domains if (domain.level_1, domain.level_2) not in known_pairs]
    if invalid:
        raise ValueError(f"Applicable domains not present in Reference Taxonomy: {invalid}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--v1-results", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    if args.results.exists():
        raise SystemExit(f"Refusing to overwrite existing v2 results: {args.results}")
    queue = [json.loads(line) for line in args.queue.read_text(encoding="utf-8").splitlines() if line.strip()]
    p0_by_title = {row["representative_title"]: row for row in queue if row.get("priority_tier") == "P0"}
    if len(p0_by_title) != 22 or set(REVIEW_PLAN) != set(P0_REVIEW_TARGETS):
        raise SystemExit("Frozen P0/v2 target scope is inconsistent; no review executed.")
    if not set(P0_REVIEW_TARGETS).issubset(p0_by_title):
        raise SystemExit("One or more required v2 P0 targets are absent from the frozen P0 queue.")

    legacy = [json.loads(line) for line in args.v1_results.read_text(encoding="utf-8").splitlines() if line.strip()]
    v1_by_title = {row["representative_title"]: row for row in legacy}
    if any(v1_by_title.get(title, {}).get("review_decision") != "pending_human_review" for title in P0_REVIEW_TARGETS):
        raise SystemExit("V2 scope must be exactly the twelve v1 pending_human_review P0 families.")

    entries, _ = load_reference_taxonomy(args.taxonomy)
    by_id = {entry.occupation_id: entry for entry in entries}
    known_pairs = {(entry.level_1, entry.level_2) for entry in entries}
    reviewed_at = datetime.now(timezone.utc).isoformat()
    results: list[dict[str, Any]] = []

    for title in P0_REVIEW_TARGETS:
        family = p0_by_title[title]
        legacy_result = v1_by_title[title]
        plan = REVIEW_PLAN[title]
        domain_links = _domain_rows(family["family_id"], plan["domains"])
        _validate_domain_pairs(domain_links, known_pairs)
        canonical = plan["canonical"]
        review = SemanticCandidateReviewV2(
            family_id=family["family_id"], representative_title=title,
            identity_decision=plan["identity_decision"], placement_status=plan["placement_status"],
            matched_existing_canonical_occupation_id=None,
            matched_existing_canonical_occupation_title=None,
            recommended_standard_title=plan["title"],
            canonical_level_1=canonical[0] if canonical else None,
            canonical_level_2=canonical[1] if canonical else None,
            applicable_domains=domain_links,
            career_or_program_modifiers=(),
        )
        result = {
            "family_id": review.family_id,
            "representative_title": review.representative_title,
            "identity_decision": review.identity_decision,
            "placement_status": review.placement_status,
            "matched_existing_occupation_id": review.matched_existing_canonical_occupation_id,
            "matched_existing_occupation_title": review.matched_existing_canonical_occupation_title,
            "recommended_standard_title": review.recommended_standard_title,
            "canonical_level_1": review.canonical_level_1,
            "canonical_level_2": review.canonical_level_2,
            "applicable_domains": _result_domains(review.applicable_domains),
            "career_or_program_modifiers": list(review.career_or_program_modifiers),
            "confidence": "medium" if review.identity_decision == "proposed_new_occupation" else "high",
            "v1_review_decision": legacy_result["review_decision"],
            "observed_evidence": {
                "candidate_title": title,
                "member_titles": json.loads(family["member_titles"]),
                "occurrence_count": int(family["aggregate_occurrence_count"]),
                "company_count": int(family["aggregate_company_count"]),
                "location_count": int(family["aggregate_location_count"]),
                "industry_distribution": json.loads(family["industry_distribution"]),
                "source_contexts": json.loads(family["representative_source_contexts"]),
                "possible_existing_taxonomy_matches": json.loads(family["existing_taxonomy_possible_matches"]),
            },
            "semantic_interpretation": plan["reason"],
            "taxonomy_structure_review_required": review.placement_status == "placement_review_required",
            "semantic_review_version": review.semantic_review_version,
            "prompt_version": review.prompt_version,
            "model": MODEL,
            "reviewed_at": reviewed_at,
        }
        results.append(result)

    if len(results) != 12 or len({result["family_id"] for result in results}) != 12:
        raise ValueError("Expected twelve unique v2 results.")
    for result in results:
        occupation_id = result["matched_existing_occupation_id"]
        if occupation_id and occupation_id not in by_id:
            raise ValueError(f"Unknown existing occupation ID: {occupation_id}")

    args.results.parent.mkdir(parents=True, exist_ok=True)
    args.results.write_text("\n".join(json.dumps(result, ensure_ascii=False) for result in results) + "\n", encoding="utf-8")
    identity_counts = Counter(result["identity_decision"] for result in results)
    placement_counts = Counter(result["placement_status"] for result in results)
    summary = {
        "review_scope": "Only twelve semantic-review-v1 pending_human_review P0 families",
        "p0_v2_reviewed_count": len(results),
        "identity_decision_counts": dict(identity_counts),
        "placement_status_counts": dict(placement_counts),
        "semantic_review_version": SEMANTIC_REVIEW_VERSION,
        "prompt_version": PROMPT_VERSION,
        "model": MODEL,
        "cache_key": "family_id + semantic_review_version",
        "validation": {
            "unique_family_ids": True,
            "existing_occupation_ids_valid": True,
            "applicable_domains_exist_in_reference_taxonomy": True,
            "v1_results_written": False,
            "p1_reviewed": False,
            "reference_taxonomy_modified": False,
        },
    }
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    rows = [
        "# Taxonomy Semantic Review — P0 v2 Re-review", "",
        "Scope: only the twelve `pending_human_review` P0 families from semantic-review-v1. "
        "This version independently assesses occupation identity and taxonomy placement. It is a proposal; the Reference Taxonomy was not modified.", "",
        f"- Model: `{MODEL}`", f"- Semantic review version: `{SEMANTIC_REVIEW_VERSION}`", f"- Prompt version: `{PROMPT_VERSION}`", "",
        "## Distribution", "", "| Identity decision | Count |", "|---|---:|",
    ]
    for decision in ["alias_of_existing", "proposed_new_occupation", "merge_with_candidate", "too_generic", "company_specific_or_program", "pending_identity_review"]:
        rows.append(f"| {decision} | {identity_counts[decision]} |")
    rows += ["", "| Placement status | Count |", "|---|---:|"]
    for status in ["single_domain", "cross_industry", "context_dependent", "placement_review_required"]:
        rows.append(f"| {status} | {placement_counts[status]} |")
    rows += ["", "## v1 to v2 comparison", "", "| Candidate | v1 decision | v2 identity | v2 placement | Semantic interpretation |", "|---|---|---|---|---|"]
    for result in results:
        rows.append(
            f"| {result['representative_title']} | {result['v1_review_decision']} | "
            f"{result['identity_decision']} | {result['placement_status']} | {result['semantic_interpretation']} |"
        )
    rows += ["", "## Proposed identities with domain treatment", "", "| Candidate | Canonical domain | Applicable domains |", "|---|---|---|"]
    for result in results:
        if result["identity_decision"] == "proposed_new_occupation":
            canonical = " / ".join(filter(None, [result["canonical_level_1"], result["canonical_level_2"]])) or "placement review required"
            domains = "; ".join(
                f"{domain['level_1']} / {domain['level_2']} ({domain['relationship_type']})"
                for domain in result["applicable_domains"]
            ) or "none proposed"
            rows.append(f"| {result['representative_title']} | {canonical} | {domains} |")
    rows += ["", "## ADR validation", "", "- `销售工程师` resolves to a proposed occupation with `placement_review_required`; its identity is no longer pending solely because one placement is unavailable.", "- `技术支持工程师` resolves to a proposed cross-industry occupation with governed canonical/applicable domain context.", "- `项目工程师` resolves to a proposed cross-industry occupation with governed canonical/applicable domain context.", "- Context-dependent titles remain identity-pending only where the supplied evidence indicates a materially different occupation boundary, rather than merely multiple industries.", "", "## Validation", "", "- 12/12 target families have one v2 result and unique family IDs.", "- Existing occupation IDs were checked against the Reference Taxonomy; this bounded re-review produced no alias mapping claims.", "- Every emitted applicable domain pair exists in the current Reference Taxonomy.", "- semantic-review-v1 results, P1 families, the Reference Taxonomy workbook, recruitment records, splitter, and gate were not modified."]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
