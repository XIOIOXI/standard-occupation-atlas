# MVP Development Constraints and Implementation Order

## Non-negotiable constraints

1. Do not scrape recruitment websites or attempt to obtain missing job descriptions.
2. Do not introduce RAG, vector databases, custom model training, multi-agent architecture, accounts, payment, social features, or a mobile app.
3. Do not run Skill Inference during interactive viewing, industry analysis, curriculum analysis, or report generation.
4. Do not bulk-call an LLM in the current architecture/design stage.
5. Do not treat inferred skills as direct recruitment evidence.
6. Do not allow an LLM to produce or modify market statistics or curriculum-gap numbers.
7. Do not read or analyse the entire recruitment dataset in this stage.
8. Keep `CanonicalOccupation` identity separate from governed Level-1/Level-2 placement. A cross-industry occupation may use multiple applicable domain links; it must not cause cross-industry Job Group merging.
9. Semantic review must return independent identity and placement decisions. Do not label a stable occupation as identity-pending solely because its placement requires review.
10. `management_trainee` is a career/programme modifier, not a canonical Level-3 occupation. Preserve the raw title and decide the underlying occupation separately.
11. The approved MVP runtime taxonomy is frozen at `mvp-taxonomy-v4.1-frozen`. Do not execute P2/P3 review or add occupations/aliases during MVP unless a demonstrated systemic taxonomy bug reopens the policy.

## Modules that must reserve interfaces

| Module | Interface to reserve now | Current implementation boundary |
|---|---|---|
| CSV import | Schema mapping, snapshot creation, validation report | No full-dataset import/analysis in this stage |
| Normalisation | Title, major requirement, company type, and industry canonicalisation | Rules can be designed before execution |
| Job group service | Similar-title grouping within compatible industries, linked-record context aggregation, status transitions | No grouping algorithm or batch group construction yet |
| Inference service | Versioned cache lookup, context snapshot builder, request contract, persistence contract | No LLM client or batch invocation yet |
| Skill repository | Separate observed and inferred queries, evidence filters, version filters | No skill extraction required now |
| Deterministic analysis | Inputs limited to persisted skill records and versioned parameters | No market analysis required now |
| Curriculum domain | Programme, curriculum, course, description, learning outcome relationships | No automatic syllabus parsing |
| Reporting | Evidence labels and inference provenance in its result schema | No final report generation required now |
| Taxonomy policy | Canonical occupation identity, governed canonical/applicable domain links, and independent semantic-review identity/placement decisions | Do not change the current workbook or manufacture links from recruitment data |

## Recommended implementation order

1. Create the documented schema and migration plan for snapshots, recruitment records, job groups, inference runs, observed skills, inferred skills, and the MVP curriculum hierarchy.
2. Implement small-sample CSV schema validation and field mapping only; do not process the full dataset.
3. Specify and test the deterministic Job Group similarity and compatible-industry policy before implementing grouping; do not reduce it to a title-only normalisation key.
4. Implement persistence, state transitions, versioning, context-hash calculation, and the unique constraint for inference caching.
5. Implement read-only repositories that expose persisted observed/inferred skills with their evidence metadata.
6. Implement deterministic aggregation contracts and test them with synthetic fixtures.
7. Implement programme/course/learning-outcome input and curriculum-skill mapping.
8. Implement structural-gap calculations and the evidence-pack schema.
9. Only after explicit approval, implement a small, manually triggered offline Skill Inference path for a few Job Groups.
10. Only after inference quality and cache behaviour are validated, add the single-agent recommendation workflow and teacher-facing report.
11. Before any further semantic candidate review, use the versioned review schema that separates identity from placement; preserve earlier review versions as immutable inputs.

## Acceptance checks for a later inference implementation

- Same profile plus same inference version yields a cache hit and no LLM request.
- Different inference version produces a separate immutable run, without overwriting history.
- Failed and low-context profiles remain visibly identifiable and are not retried by page views.
- Every inferred result retains model, prompt version, context snapshot/hash, confidence, and timestamp.
- Every final demand/gap value can be recomputed from stored skill evidence and deterministic analysis parameters.
- A report never describes an inferred skill as a directly observed requirement.
