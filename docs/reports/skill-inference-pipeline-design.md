# Skill Inference Pipeline Design

## Boundary

The inference unit is a Job Group, never an individual recruitment record. This stage prepares inputs, validation, persistence, and cache contracts only. No LLM call or inference result was generated.

## Versions

- `skill-inference-v1`
- `job-group-skill-inference-prompt-v1`
- `job-group-context-v1`
- `skill-normalization-v1`

## Context and provenance

`JobGroupSkillInferenceInput` contains a representative title, nullable canonical occupation, industry/domain context, bounded original titles, occurrence/company/location counts, at most five deterministic source contexts, at most three major-requirement examples, and bounded distributions. Its SHA-256 fingerprint covers the complete selected input.

`context_quality` is deterministic: mapped multi-member groups are high; mapped singletons or evidence-rich multi-member groups are medium; generic/management-trainee unmapped groups and sparse unmapped singletons are low.

## Output and cache contracts

`JobGroupSkillInferenceResult` permits zero to five hard and zero to five soft candidates. Each inferred skill is always `source_type=llm_inference` and `evidence_level=inferred_medium` or `inferred_low`; inferred evidence can never be emitted as `observed_high`.

Statuses: `completed`, `insufficient_context`, `skipped_generic`, `failed_validation`. Cache identity is `job_group_id + inference_version + input_fingerprint`. SQLite reserves `skill_inference_runs` and `inferred_skills`; no run has been inserted in this task.

## Pilot

The prepared pilot has exactly 50 deterministic groups with mapped/unmapped, singleton/multi-member, high/medium/low-context, management-trainee, generic, and varied-industry coverage. It is an input-only preflight artifact, not an inference result.
