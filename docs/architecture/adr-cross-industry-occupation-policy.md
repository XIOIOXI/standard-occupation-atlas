# ADR: Cross-industry Occupation Identity and Taxonomy Placement Policy

**Status:** Proposed — policy decision required before the next semantic review.  
**Date:** 2026-09-20  
**Scope:** Reference Taxonomy policy and future data-model design only. This ADR does not modify the Reference Taxonomy workbook, recruitment data, mapping rules, splitter, quality gate, or P0/P1 review outputs.

## Context

The Reference Taxonomy is currently represented as one row per `occupation_id`, with one Level 1, one Level 2, and one Level 3 title. The current workbook contains 452 rows (452 occupation IDs), 20 Level-1 categories, 101 Level-2 domains, and 450 distinct Level-3 titles. Two titles are already represented in more than one row and placement: `运营分析师` and `结构工程师`.

The mapping implementation likewise resolves one `TaxonomyEntry` and writes one `matched_level_1`, `matched_level_2`, and `matched_occupation_id` for a mapped job-title unit. Industry context may disambiguate competing rows, but it does not model a canonical occupation identity separately from its domain placement.

This creates a policy failure mode in P0 semantic review: a candidate can be a credible occupation, yet become `pending_human_review` solely because no *single* Level-1/Level-2 placement is safe. The P0 cases `销售工程师`, `技术支持工程师`, and `项目工程师` illustrate this directly. It is important not to resolve this by forcing a market title into an arbitrary industry, nor by creating a duplicate Level-3 occupation for every industry occurrence.

The governing constraint remains: **Reference Taxonomy defines the classification space; recruitment data is mapped into that space.** A multi-domain policy must make the reference space clearer and more stable; it must not let recruitment-data distribution create its own classifications.

## Decision

Adopt **Option B: canonical occupation identity with one or more applicable taxonomy-domain links** as the target policy.

1. Define the occupational question first: “What occupation is this?”
2. Determine taxonomy placement separately: “In which domain(s) is that occupation canonically or validly applicable?”
3. Preserve the recruitment record's observed industry, company, location, raw title, and future Job Group context. These are mapping/inference context, not replacements for occupation identity.
4. Keep a single canonical placement for presentation and taxonomy navigation when one is defensible, but permit additional, governed `applicable` domain links for genuinely cross-industry occupations.
5. Split a Level-3 occupation by industry only when the industry changes the core occupational identity, principal work object, competency boundary, regulation/safety regime, or curriculum relevance—not merely because the employer industry differs.

Option B is a future architecture policy. It does **not** authorize automatically adding occupations, aliases, domain links, or changing the existing workbook in this phase.

## Options considered

| Option | Description | Benefits | Main limitation | Decision |
|---|---|---|---|---|
| A. Strict single placement | Every Level-3 occupation must have exactly one Level-1/Level-2 placement. | Simple tables and navigation. | Conflates identity with placement; forces arbitrary mapping or unnecessary `pending` outcomes for valid cross-industry roles. | Rejected. |
| B. Canonical identity + multiple applicable domains | One occupation identity may have a canonical domain and zero or more governed applicable domains. | Stable taxonomy, less duplication, preserves industry context, supports explainable mapping and future skill analysis. | Requires a small identity/link model and clear link governance. | **Adopted.** |
| C. Split each occupation by industry | A title becomes a separate Level-3 occupation for every industry in which it occurs. | Highly specific local placement. | Causes taxonomy explosion and duplicates; makes market comparison and curriculum analysis fragmented. | Rejected as the default; retain only as an exception when identities are genuinely different. |

## Identity-versus-placement test

Semantic review must not treat placement uncertainty as identity uncertainty. Reviewers should apply the following sequence.

1. **Occupation identity:** Is there a stable, concrete, reusable occupation concept? Is it an alias of an existing identity, a new identity, too generic, a company programme, or genuinely ambiguous?
2. **Domain applicability:** Is it single-domain, cross-industry with a stable core, context-dependent, or placement-uncertain?
3. **Split exception:** Does a shared market label hide materially different occupations? If yes, retain or propose separate domain-specific occupations rather than one broad identity.

Industry occurrence alone is insufficient to split an occupation. Conversely, a common string alone is insufficient to merge different occupations.

## P0 cross-industry case review

The table below is a policy assessment of the eight requested P0 candidates. It does not revise their existing P0 decisions.

| Candidate | Is the identity stable? | Cross-industry assessment | Does industry alter the core identity? | Default policy direction | Split into industry Level-3s now? |
|---|---|---|---|---|---|
| 客户经理 | Broadly recognisable, but the work boundary can differ substantially. | Common across banking, enterprise sales, and service contexts. | Often yes: a bank customer manager and a B2B account/customer manager can have different client, product, compliance, and skill boundaries. | Treat as **context-dependent**; identify an existing sector-specific identity where evidence is sufficient, otherwise human review. | Not as one generic automatic mapping; sector-specific identities may remain justified. |
| 销售工程师 | Yes: technical pre-/post-sales and solution-facing sales is a stable core. | Naturally cross-industry. | Usually no at the core; product knowledge varies by domain. | Canonical cross-industry occupation with applicable domains; retain domain in the recruitment mapping and Job Group context. | No by default. |
| 测试工程师 | The test/validation function is stable, but the title is underspecified. | Common in software, semiconductors, manufacturing, and other domains. | Frequently yes: software QA, chip test, and industrial validation are materially different competency families. | **Context-dependent identity family**; map only with adequate context or retain review. | Not automatically; retain domain-specific identities where the work boundary differs. |
| 结构工程师 | The string is not reliably one occupation. | Appears in mechanical/product, automotive, medical-device, and civil/construction contexts. | Yes: mechanical structural design and civil structural engineering are distinct core identities. | Treat as an **identity collision**, not merely a placement problem. | Yes where domain-specific identities are already justified; do not collapse them. |
| 产品工程师 | Plausible but underspecified. | Cross-industry. | Sometimes: product/process engineering differs from product-management-adjacent usage. | Context-dependent; needs a clearer occupation definition before canonicalisation. | No automatic split or merge now. |
| 技术支持工程师 | Yes: a stable support/troubleshooting core exists. | Naturally cross-industry. | Usually no at the core; technical stack and product domain vary. | Canonical cross-industry occupation with applicable domains and context-specific skill evidence. | No by default. |
| 项目工程师 | Generally recognisable, but role authority and work object need context. | Cross-industry. | Usually no for the coordination/engineering-project core; high-risk sectors may add distinct boundaries. | Canonical cross-industry occupation with applicable domains, subject to a defined scope. | No by default; split only for materially distinct regulated or technical identities. |
| AI工程师 | No sufficiently stable Level-3 identity at this granularity. | Cross-industry, with large variation in specialisation. | Often yes: algorithm, platform/MLOps, application, and embedded/robotics roles differ. | Keep as **identity clarification / human-review** rather than a placement-only issue. | Do not create a generic Level-3 merely to improve coverage. |

Of these eight cases, **three are primarily placement cases** (`销售工程师`, `技术支持工程师`, `项目工程师`). `客户经理`, `测试工程师`, and `产品工程师` are context-dependent identity-and-placement cases; `结构工程师` is an identity collision; `AI工程师` is too broad to be placement-led. This explains why a policy change can reduce inappropriate `pending` decisions without turning all P0 pending cases into mappings.

## Management-trainee policy

Adopt a **programme/modifier policy**: `管理培训生` / `管培生` describes a recruitment and development pathway, not a standalone canonical Level-3 occupation.

- Retain the raw title and the existing `management_trainee_family` flag.
- If a concrete future occupation is supplied (for example, a finance or sales trainee role), map the occupation separately and record the trainee pathway as a modifier.
- If no concrete occupation is supplied, retain it as programme/policy review; do not create a Level-3 solely for the trainee label.
- Company-branded trainee programmes remain company-specific/program records unless a stable occupation is independently evidenced.

This is deliberately closer to a “D: separate programme dimension” policy than to treating management trainee as either a generic occupation or an automatic domain placement.

## Minimal future data-model impact

The current `occupation_id` row conflates identity and placement. The smallest extension needed for Option B is a canonical occupation identity plus a placement-link relation. Exact physical schema and workbook migration are deferred.

### Canonical occupation fields

| Field | Purpose |
|---|---|
| `canonical_occupation_id` | Stable identity key, independent of a particular placement row. |
| `canonical_standard_title` | Governed canonical Level-3 title. |
| `canonical_definition` | Short boundary statement used in human/LLM review. |
| `canonical_level_1`, `canonical_level_2` | Optional primary navigation placement, if one is justified. |
| `identity_status` | `active`, `proposed`, `deprecated`, or `needs_policy_review`. |

### `occupation_domain_links`

| Field | Purpose |
|---|---|
| `canonical_occupation_id` | Parent occupation identity. |
| `level_1`, `level_2` | Existing Reference Taxonomy domain placement. |
| `link_type` | At minimum `canonical`, `applicable`, or `context_required`. |
| `rationale` | Governed explanation for the link. |
| `taxonomy_version`, `status` | Versioning and review state. |

Future mapping results should retain the existing raw evidence fields and add, rather than replace, fields such as `matched_canonical_occupation_id`, `identity_decision`, `placement_decision`, `placement_status`, and `selected_domain_link`. A mapping can therefore state: “occupation identity confirmed; domain is applicable/contextual,” without pretending that a raw title establishes a single industry fact.

## Consequences for Job Groups, skills, and curriculum analysis

### Job Groups

`JobGroup` remains a recruitment-record aggregation within the same or compatible industry scope. It is not an occupation identity. A cross-industry canonical occupation may be associated with several Job Groups; the Job Group must preserve the member records' observed industry, company, location, occurrence count, and original titles. This avoids collapsing distinct industry contexts merely because they share an occupation identity.

### Offline Skill Inference

The future inference context should contain both the canonical occupation identity (when confirmed) and the selected/applicable domain context, alongside company, raw title, major requirement, and related-role signals. This is important because a cross-industry occupation can retain a common core while requiring different domain skills. It does not change the existing constraints: inference is offline, versioned, cacheable, persistent, and cannot produce market statistics.

### Skill-demand and curriculum-gap reporting

Python must be able to aggregate demand at two explicitly labelled scopes:

1. **Canonical-occupation core demand** — evidence across confirmed Job Groups for the same identity; and
2. **Domain-specific demand** — evidence filtered by the governed taxonomy-domain link and observed recruitment context.

This makes programme-level comparison more useful: a curriculum can be assessed against broad occupational competencies without hiding domain-specific gaps. Reports must never claim that a cross-industry placement is directly observed when it is a taxonomy policy link.

## Semantic-review policy after this ADR

When the architecture is updated, semantic candidate review should output two non-substitutable decisions:

```text
identity_decision:
  alias_of_existing | proposed_new_occupation | too_generic |
  company_specific_or_program | pending_human_review

placement_status:
  single_domain | cross_industry_applicable |
  context_required | placement_uncertain
```

`pending_human_review` should be used for unresolved identity, identity collision, insufficient evidence, or a genuinely missing policy decision—not merely because a valid canonical occupation has more than one applicable domain. A separate placement confidence and rationale retain reviewability.

## Migration and governance guardrails

1. Do not retroactively overwrite raw recruitment titles, records, source industry, P0 results, or coverage outputs.
2. Do not automatically merge current duplicate titles. Reconcile them through a taxonomy steward review using definitions and domain boundaries.
3. Do not derive new Level-1/Level-2 categories from the recruitment dataset.
4. Do not create domain links from a title's frequency alone; each link needs a governed rationale and taxonomy version.
5. Preserve existing single-placement mappings during migration. Only explicitly reviewed occupations receive canonical identity/link treatment.
6. Keep candidate review proposals separate from approved Reference Taxonomy changes.

## Recommended next steps

1. Approve or revise this Option-B policy.
2. Update the architecture and data-model design documents to represent identity separately from placement, without modifying the workbook yet.
3. Re-review the 12 P0 `pending_human_review` cases under the two-step policy, starting with the eight cases in this ADR. This is a policy re-review, not a P1 execution.
4. Validate the revised P0 recommendations with a human taxonomy steward.
5. Only then decide whether P1 should run using the revised semantic-review schema and cache version.

## Non-goals

- No P1 semantic review execution.
- No LLM calls.
- No Reference Taxonomy expansion, alias insertion, or workbook change.
- No splitter, quality-gate, CSV importer, Job Grouping, Skill Inference, Curriculum Mapping, frontend, or recruitment-data change.
