# Data Model Design

## Design principles

The model keeps raw recruitment data, normalised recruitment records, job-group enrichment, skill evidence, deterministic aggregates, and curriculum data distinct. This is necessary to preserve provenance, prevent repeated inference, and make every curriculum recommendation auditable.

## Recruitment import and normalisation

### DatasetSnapshot

One immutable import snapshot of the runtime CSV source.

| Field | Notes |
|---|---|
| `snapshot_id` | Primary identifier |
| `source_name` | 2026 recruitment dataset |
| `source_format` | `csv` |
| `source_file_name` | Imported file name |
| `source_updated_at` | Latest dataset update represented by the snapshot |
| `imported_at` | System import time |
| `record_count` | Imported row count |
| `source_checksum` | Detects identical source files |
| `schema_version` | CSV mapping version |
| `validation_summary` | Valid, invalid, and duplicate counts |

### RecruitmentRecordRaw

Stores each CSV row without losing the original content.

| Field | Notes |
|---|---|
| `raw_record_id` | Primary identifier |
| `snapshot_id` | Parent snapshot |
| `row_number` | CSV source row |
| `raw_payload` | Original mapped row payload |
| `validation_errors` | Field-level validation failures |

### RecruitmentRecord

The validated, normalised record. It includes the source fields: update time, company, company type, recruitment session, recruitment batch, industry category, location, job title, deadline, education requirement, major requirement, recruitment link, and announcement link.

Additional fields are `record_id`, `snapshot_id`, `normalized_job_title`, `normalized_major_requirement`, future `job_group_id`, `record_status`, `content_hash`, and timestamps.

`record_status` supports `valid`, `invalid`, `duplicate`, `superseded`, and `expired`. `valid` means the minimum analysis identity (`company_name` and `job_title`) is present; it does not mean every field is complete or perfectly formatted. A record retains its source snapshot even if a later version supersedes it.

Each record separately exposes `eligible_for_market_analysis`, `eligible_for_industry_analysis`, and `eligibility_reasons`. Missing industry category excludes a record only from industry-segment analysis. Missing URL, deadline, education requirement, major requirement, or location remains a field-level quality issue, not a record-level failure.

## Job groups and offline inference

### JobGroup

Represents a shareable aggregation and future inference target, rather than an individual job advertisement or a standardised occupation. A group contains recruitment records whose titles are highly similar within the same or compatible industry scope. It must not force different concrete positions into one occupation.

| Field | Notes |
|---|---|
| `job_group_id` | Primary identifier |
| `industry_category` | One industry category or a compatible-industry scope |
| `original_job_titles` | Distinct raw job-title values represented by the group |
| `source_record_ids` | Source recruitment-record identifiers; model as a join table when implemented |
| `occurrence_count` | Number of member recruitment records; future market-demand weight |
| `company_count` | Distinct company count among members |
| `location_count` | Distinct location count among members |
| `grouping_version` | Deterministic similarity/grouping-rule version |
| `inference_status` | `pending`, `completed`, `failed`, `stale`, or `skipped_low_context` |
| `current_inference_version` | Latest accepted version, nullable |
| `created_at`, `updated_at` | Audit fields |

The database will enforce a versioned grouping identity after the grouping algorithm is specified. Until then, no `JobGroup` table, grouping key, or group membership is implemented. Company name, location, recruitment session, and recruitment batch remain available through linked records as context and market signals.

### SkillInferenceRun

An immutable versioned enrichment run for a job group.

| Field | Notes |
|---|---|
| `inference_run_id` | Primary identifier |
| `job_group_id` | Parent job group |
| `inference_version` | Integer or semantic version |
| `inference_status` | Run outcome/state |
| `inference_model` | Exact model identifier |
| `prompt_version` | Versioned inference prompt |
| `rule_version` | Any non-prompt inference rule version |
| `context_snapshot` | Structured, reproducible inference input |
| `context_hash` | Fingerprint of the input context |
| `related_role_signal_version` | Version of any aggregated market context |
| `requested_at`, `completed_at` | Timing and audit |
| `failure_reason` | Safe error code/message when applicable |

The database must enforce `UNIQUE(job_group_id, inference_version)`. A completed result is read from persistence; it is never regenerated during normal analysis or page viewing.

`context_snapshot` must include company context, industry context, job/occupation context, major-requirement context, and any related-role market signals. It should contain source record references rather than unsupported claims.

### InferredSkill

Candidate skill emitted by one completed `SkillInferenceRun`.

| Field | Notes |
|---|---|
| `inferred_skill_id` | Primary identifier |
| `inference_run_id` | Parent inference run |
| `job_group_id` | Denormalised lookup field |
| `skill_name`, `canonical_skill_id` | Vocabulary-linked skill |
| `skill_category` | `hard` or `soft` |
| `confidence` | Bounded numeric confidence |
| `reasoning_summary` | Concise explanation grounded in context |
| `evidence_context` | Relevant contextual references |
| `source_type` | Always `llm_inference` |
| `evidence_level` | `inferred_medium` or `inferred_low` |
| `inference_model`, `prompt_version`, `inference_version` | Provenance copied for reporting |
| `inferred_at` | Completion time |

## Directly observed skills

### ObservedSkill

Stores direct vocabulary matches in permitted recruitment text fields. It is deliberately independent from `InferredSkill`.

| Field | Notes |
|---|---|
| `observed_skill_id` | Primary identifier |
| `record_id` | Recruitment record source |
| `skill_name`, `canonical_skill_id` | Vocabulary-linked skill |
| `skill_category` | `hard`, `soft`, or `domain` |
| `evidence_field` | Such as `job_title` or `major_requirement` |
| `evidence_text` | Matched source excerpt |
| `source_type` | Always `direct_text_match` |
| `evidence_level` | Always `observed_high` |
| `extractor_version` | Vocabulary/extraction version |
| `extracted_at` | Audit timestamp |

## Deterministic analysis outputs

### CanonicalOccupation and OccupationDomainLink

`CanonicalOccupation` represents occupational identity independently from taxonomy placement. It contains `canonical_occupation_id`, `standard_title`, optional governed `definition`, `aliases`, `status`, and `taxonomy_version`. It has exactly one canonical placement but must not be copied merely because it is used in more than one industry.

`OccupationDomainLink` holds the governed placement relation: `occupation_id`, `level_1`, `level_2`, and `relationship_type`. `relationship_type` is either `canonical` or `applicable`. One canonical occupation can therefore have one `canonical` Level-1/Level-2 placement and multiple `applicable` domain links. An applicable link is taxonomy policy, not a claim that every recruitment record proves that placement.

For migration compatibility, every current Reference Taxonomy Level-3 row is adapted as one `CanonicalOccupation`: its existing `occupation_id` becomes `canonical_occupation_id`, its Level-3 title becomes `standard_title`, and its existing Level-1/Level-2 pair is its single `canonical` `OccupationDomainLink`. The Excel reader and workbook remain unchanged; future applicable links are additive and require an explicit governed taxonomy version.

### TaxonomyMapping and OccupationCandidate

`TaxonomyMapping` maps a source recruitment record (and, when a raw field explicitly lists multiple positions, a retained job-title unit) into the external Reference Taxonomy. It retains `source_record_id`, complete `raw_job_title`, company, source industry, location, major requirement, education requirement, `matched_level_1`, `matched_level_2`, `matched_occupation_id`, `matched_occupation_name`, `match_type`, confidence, and review status. The standard occupation never overwrites the raw job-title field.

The cross-industry model adds, without replacing raw evidence, `matched_canonical_occupation_id`, `identity_decision`, `placement_status`, and a selected/available `OccupationDomainLink`. A confirmed identity may have `placement_review_required`; this must not be represented as an identity failure. The current coverage output remains a legacy single-placement projection until explicitly migrated.

`OccupationCandidate` is a market-evidence pool, not an error table. It holds an unmapped/review-required title, occurrence count, company count, location count, industry distribution, and source-record identifiers. It may retain a cautious level-1 or level-2 context suggestion, but it does not create a new taxonomy entry.

### SemanticCandidateReviewV2 and CareerOrProgramModifier

`SemanticCandidateReviewV2` separates the two review dimensions:

| Field | Allowed values / meaning |
|---|---|
| `identity_decision` | `alias_of_existing`, `proposed_new_occupation`, `merge_with_candidate`, `too_generic`, `company_specific_or_program`, or `pending_identity_review` |
| `placement_status` | `single_domain`, `cross_industry`, `context_dependent`, or `placement_review_required` |
| `canonical_level_1`, `canonical_level_2` | Primary placement when known |
| `applicable_domains` | Zero or more `{level_1, level_2, relationship_type}` placement links |
| `career_or_program_modifiers` | Currently supports `management_trainee` independently of the occupation identity |

The two decisions are independent: a stable proposed or existing occupation may have `placement_review_required`. `management_trainee` / `管培生` is a recruitment-development modifier rather than a canonical Level-3 occupation. A title such as `财务管培生` can therefore carry both its confirmed underlying occupation and `management_trainee`; when the underlying occupation is unknown, it remains identity/context review rather than creating a trainee occupation.

### SkillDemandProfile

A versioned, reproducible aggregate for an industry, occupation, or selected market segment. It references a dataset snapshot, filters, vocabulary version, analysis parameter version, and source-skill policy.

It contains deterministic measures such as distinct-role coverage, distinct-record coverage, observed-skill counts, inferred-skill counts, evidence-level composition, and derived frequency/PMI/community metrics. The LLM never writes these fields. Where canonical occupations are confirmed, reports must distinguish canonical-occupation core demand from demand filtered to a governed domain link and observed recruitment context.

### CurriculumSkillMapping and StructuralSkillGap

`CurriculumSkillMapping` links curriculum entities to canonical skills and stores the mapping source, evidence excerpt, and confidence. `StructuralSkillGap` links a `SkillDemandProfile` to a programme/curriculum scope, records the deterministic calculation inputs and rule version, and classifies the gap. It must preserve whether demand derives from observed or inferred skills.

## Curriculum hierarchy

The long-term model is:

`Program -> Curriculum -> Course -> LearningOutcome -> Assessment`

For the MVP, create models only for `Program`, `Curriculum` (optional container), `Course`, `CourseDescription`, and `LearningOutcome`. Keep foreign keys nullable or extension-ready for future `Assessment`; do not add automated syllabus extraction.

## Reporting contract

Every skill rendered in an industry profile, gap, or recommendation carries `source_type` and `evidence_level`. An inferred skill also carries `inference_version`, model, prompt version, and a label equivalent to: "candidate skill inferred from role context". It cannot be labelled as an explicit recruitment-text requirement.
