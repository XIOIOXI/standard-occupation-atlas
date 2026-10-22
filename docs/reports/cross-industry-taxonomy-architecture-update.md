# Cross-industry Taxonomy Architecture Update

**Date:** 2026-09-20  
**Policy source:** [ADR: Cross-industry Occupation Identity and Taxonomy Placement Policy](../architecture/adr-cross-industry-occupation-policy.md)  
**Scope:** Architecture, model contracts, and P0 semantic re-review preparation only.

## Completed changes

The project now adopts the target architecture:

```text
Recruitment Record
  -> Candidate / Occupation Mapping
  -> Canonical Occupation
  -> Governed Domain Context
  -> Job Group (same or compatible industry scope)
  -> Offline Skill Inference
  -> Deterministic Skill Demand
  -> Curriculum Mapping
```

This is a design and contract change. The current Reference Taxonomy workbook, raw recruitment records, coverage results, candidate pool, splitter, and quality gate were not changed.

## Model contracts

### CanonicalOccupation

`CanonicalOccupation` represents what an occupation is, independently of where it is placed in the taxonomy.

| Field | Meaning |
|---|---|
| `canonical_occupation_id` | Stable occupation identity key |
| `standard_title` | Governed standard occupation title |
| `definition` | Optional boundary statement |
| `aliases` | Governed aliases only |
| `status` | Lifecycle/status value |
| `taxonomy_version` | Version provenance |
| `domain_links` | One canonical and optional applicable placements |

It requires exactly one `canonical` domain link. Additional domain links are additive rather than copied occupation identities.

### OccupationDomainLink

| Field | Meaning |
|---|---|
| `occupation_id` | Parent canonical occupation identity |
| `level_1` | Existing Reference Taxonomy Level 1 |
| `level_2` | Existing Reference Taxonomy Level 2 |
| `relationship_type` | `canonical` or `applicable` |

## Semantic Candidate Review v2

The new v2 review contract has two independent decisions.

| Field | Allowed values |
|---|---|
| `identity_decision` | `alias_of_existing`, `proposed_new_occupation`, `merge_with_candidate`, `too_generic`, `company_specific_or_program`, `pending_identity_review` |
| `placement_status` | `single_domain`, `cross_industry`, `context_dependent`, `placement_review_required` |

It also supports `canonical_level_1`, `canonical_level_2`, and zero or more `applicable_domains`. Therefore, a stable occupation can be proposed or confirmed while placement remains `placement_review_required`; placement ambiguity no longer requires an identity-pending outcome.

`career_or_program_modifiers` is an independent field. It currently supports `management_trainee`. A management-trainee title is not a canonical Level-3 occupation: when an underlying occupation is known, preserve it separately and apply the modifier; otherwise retain identity/context review.

## Compatibility with the current Reference Taxonomy

No migration was performed. The compatibility adapter treats every existing workbook row as follows:

```text
existing occupation_id -> canonical_occupation_id
existing Level-3 title -> standard_title
existing Level-1 + Level-2 -> one canonical OccupationDomainLink
```

Consequently, all current 452 rows/occupation IDs remain valid and the existing workbook reader and coverage mapper are unchanged. Future applicable-domain links require separate taxonomy governance and a versioned migration; they must not be inferred automatically from recruitment occurrence data.

## Job Group and Skill Inference boundaries

A cross-industry Canonical Occupation does not combine Job Groups across industries. A Job Group continues to use similar titles, compatible industry scope, and source recruitment context.

Future offline Skill Inference can receive canonical occupation identity, governed domain context, Job Group context, and source recruitment context together. This permits future reporting of `occupation_core_skills` and `domain_specific_skills`, while retaining all existing evidence, caching, and deterministic-statistics restrictions.

## P0 v2 re-review readiness

`semantic-review-v2` and `semantic-candidate-review-prompt-v2` are reserved in a preparation-only contract. Its independent output target is:

```text
data/processed/taxonomy_expansion/semantic_review_p0_v2_results.jsonl
```

The preparation check confirmed the frozen queue still contains exactly 22 P0 families and all 12 intended re-review titles:

- 测试工程师、客户经理、销售工程师、结构工程师、产品工程师、技术支持工程师
- 财务专员、销售经理、项目工程师、AI工程师、项目助理、运维工程师

The check did not call an LLM and did not create the v2 results file. The existing v1 file remains an immutable input at `data/processed/taxonomy_expansion/semantic_review_p0_results.jsonl`.

## Validation

- Full test suite: **36 passed**.
- Coverage and CSV-import tests remain green.
- New tests cover multiple applicable domains, canonical versus applicable placement, independent identity/placement decisions, stable identity with placement uncertainty, management-trainee modifier representation, legacy workbook compatibility, and v1 non-overwrite behaviour.

## Explicit non-actions

- No LLM was called.
- P0 was not re-reviewed and P1 was not executed.
- No Reference Taxonomy Excel or taxonomy occupation content was changed.
- No recruitment data, splitter, quality gate, Job Grouping, Skill Inference, Curriculum Mapping, frontend, or formal Taxonomy Expansion was changed.
