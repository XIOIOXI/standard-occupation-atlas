# Graduate Job Search Workbench - Project Constraints

## Product scope

The product is an online job-search workbench for graduating students. Its current primary path is:

`Manually supplied recruitment file -> Local validation / incremental comparison -> Atomic job extraction -> Governed occupation mapping -> Career-directory and daily-update browsing`

The current MVP includes recruitment-information organisation, SNO occupation-directory browsing, daily newly-added jobs, source-detail traceability, and a locally operated incremental-update Agent. The update Agent is a single, constrained tool-using Agent: deterministic code validates files, compares all imported data, deduplicates, validates model outputs, writes data, and calculates statistics; the LLM may only select bounded next actions for a newly detected job.

The MVP is not restricted to IT occupations. Existing IT-focused data and modules may remain, but must not limit recruitment coverage or create an IT-only product assumption. It does not implement job-site scraping, automatic downloading or scheduled monitoring, user accounts, payments, social features, a mobile application, multi-agent orchestration, model training, vector databases, RAG, or automated syllabus parsing.

Deterministic job search and company/location/industry/session/status/date filtering are current MVP capabilities. Resume-to-job matching, a personal application workspace, and a conversational job-search assistant are planned capabilities, not current implementation. University programme, course, learning-outcome, curriculum-skill mapping, and curriculum-gap analysis are retained only as optional future capabilities and are outside the current MVP.

## Recruitment data policy

- The 2026 recruitment dataset is the initial MVP source. Manually supplied CSV/XLSX updates are accepted through the local operator workflow; XLSX and CSV must follow the same validation and normalisation contract.
- Do not scrape SEEK or any other job site, and do not enrich records by fetching full job descriptions.
- Do not read or analyse the complete source dataset unless a task explicitly authorises it.
- Preserve source provenance, import snapshot, update time, and validation outcome for every imported recruitment record.
- A parsable recruitment record remains retained unless its minimum identity is missing: `company_name` and `job_title` are the only record-validity requirements. Field quality issues must remain separately visible.
- `recruitment_url`, `announcement_url`, deadline, education requirement, major requirement, and location never invalidate a record. Missing industry category only prevents industry-segment analysis; missing major requirement is retained as lower-quality future inference context.
- Record validity and analysis eligibility are distinct: persist explicit market-analysis and industry-analysis eligibility flags with reasons.

## Job-group identity and inference

- A `JobGroup` is an aggregation of recruitment records with highly similar job titles within the same or compatible industry scope. It is not a standardised occupation profile and must not force distinct concrete positions into one occupation.
- Do not delete, overwrite, or collapse original `RecruitmentRecord` instances. A job group preserves `original_job_titles`, `source_record_ids`, `occurrence_count`, `company_count`, `location_count`, and `industry_category`.
- `company_name`, `location`, `recruitment_session`, and `recruitment_batch` remain linked-record context or aggregated market signals. They do not alone define a new job group.
- Job grouping is a future deterministic aggregation step. Do not implement its matching/grouping algorithm unless explicitly authorised.
- Skill inference is an offline, cacheable, persistent enrichment operation. It must never run merely because a user opens an analysis page or report.
- Re-inference is permitted only for a newly unseen job group, an explicit user-triggered re-infer action, a changed model/prompt/rule version, or an inference explicitly marked stale.
- Inference state must be explicit: `pending`, `completed`, `failed`, `stale`, or `skipped_low_context`. Failed and low-context records must not trigger unlimited retries.
- Persist a context snapshot or `context_hash` for every inference, covering company, industry, job, major-requirement, and related-role market context.
- Enforce `UNIQUE(job_group_id, inference_version)` for persisted inference runs. The same job group and inference version must never make a duplicate LLM request.
- Retain model, prompt version, inference version, timestamp, status, confidence, and context provenance. Never overwrite a prior inference version.

## Skill evidence rules

- `ObservedSkill` and `InferredSkill` are separate data models, not a boolean variation of one table.
- Observed skills originate from direct text matching and use `source_type=direct_text_match` and `evidence_level=observed_high`.
- Inferred skills originate from LLM enrichment and use `source_type=llm_inference` and `evidence_level=inferred_medium` or `inferred_low`.
- Inferred skills are candidate skills based on role context. They must never be presented as skills explicitly required by recruitment text.
- If contextual evidence is weak, lower confidence or use `skipped_low_context`; do not invent specific skills.

## Deterministic-statistics boundary

- LLMs may infer candidate hard and soft skills only. They must not generate, estimate, fill in, or alter statistical numbers.
- Industry skill frequency, role coverage, industry distribution and occupation comparison are calculated deterministically in Python from persisted `ObservedSkill` and `InferredSkill` records. If optional curriculum features are reintroduced, Skill Demand and Curriculum Skill Gap must also remain deterministic Python calculations.
- Every final report must expose skill source and evidence level. For inferred skills it must also expose inference version, and label them as "candidate skills inferred from role context".

## Reference Taxonomy coverage

- Reference Taxonomy defines the classification space; recruitment data is mapped into that space.
- A `CanonicalOccupation` defines occupational identity; an `OccupationDomainLink` defines its governed taxonomy placement. Do not conflate the two.
- A canonical occupation has one `canonical` domain placement and may have additional `applicable` domains. Cross-industry applicability never authorises copying an occupation identity or creating classes from recruitment-data distribution.
- The current workbook remains compatible: each existing Level-3 row is treated as one canonical occupation and its current Level-1/Level-2 as the canonical domain until an explicitly governed applicable-domain link is approved.
- Canonical occupation across industries does not make a `JobGroup` cross-industry. Job groups remain title- and compatible-industry-based recruitment aggregates with their source context preserved.
- Do not create level-1, level-2, or level-3 taxonomy classes from recruitment-data distribution. Do not overwrite a raw recruitment job title with a standard occupation name.
- Mapping may use the raw job title and available company/industry/location context to disambiguate an existing Reference Taxonomy entry. It must retain the source record ID and raw job title.
- When an existing level-3 occupation cannot be reasonably confirmed, leave it unmapped or mark it for review. Persist it in an occupation candidate pool with occurrence, company, location, industry-distribution, and source-record evidence.
- Coverage analysis never modifies the Reference Taxonomy workbook or automatically adds aliases or occupations.
- Semantic candidate review must decide occupation identity separately from placement. Placement uncertainty alone must not turn a stable occupation into identity-pending status. `management_trainee` is a career/programme modifier, not a canonical Level-3 occupation.
- MVP Taxonomy is frozen at `mvp-taxonomy-v4.1-frozen`. Do not execute P2/P3 semantic review or automatically add aliases/occupations. Pending and generic titles retain raw context; reopen only for a demonstrated systemic taxonomy bug.

## Optional future curriculum capability

If curriculum features are explicitly reintroduced, the architecture can accommodate this hierarchy:

`Program -> Curriculum -> Course -> LearningOutcome -> Assessment`

This hierarchy, course data, learning outcomes, curriculum-skill mapping, and curriculum-gap reporting are not current MVP scope. Do not implement or surface them as current job-search functionality without explicit authorisation.

## Implementation discipline

- Keep deterministic Python analysis tools separate from LLM orchestration.
- Use a single agent/orchestrator only. It may call tools but cannot invent evidence or bypass validation.
- Version schemas, vocabularies, normalisation rules, analysis parameters, prompts, and inference outputs so reports are reproducible.
- Preserve source data, update-batch provenance, validation outcomes, run records, model token usage, and conservative cost estimates. A user-approved withdrawal of an update batch must be recoverable through an archive, not a silent purge.
- Before adding a capability, verify it belongs to the approved MVP scope.
