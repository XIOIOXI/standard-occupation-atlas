# Data Flow and Evidence Boundaries

## Offline recruitment enrichment flow

```text
Raw CSV recruitment data
  -> schema validation and import snapshot
  -> normalisation and deduplication
  -> RecruitmentRecord
  -> candidate / occupation mapping
  -> CanonicalOccupation + governed domain context (when confirmed)
  -> future grouping into JobGroup within compatible industries
  -> context aggregation from linked records
  -> conditional offline LLM Skill Inference
  -> versioned SkillInferenceRun and persisted InferredSkill
  -> Industry Skill Database
```

`CanonicalOccupation` answers what a mapped occupation is; `OccupationDomainLink` answers where it is canonically or validly applicable. A current Reference Taxonomy row remains compatible as a canonical occupation with one canonical domain. Future applicable-domain links are governed taxonomy additions, not source-data-created classifications.

`JobGroup` is a future aggregation of highly similar job titles in the same or compatible industry scope. It preserves original titles, source record IDs, occurrence count, company count, location count, and industry category. It does not replace recruitment records or assert that all members are one standardised occupation. **A canonical occupation with multiple applicable domains never causes its Job Groups to merge across industry contexts.**

Company name, location, recruitment session, and recruitment batch remain linked record context. They are usable in inference-context aggregation and do not alone create a job group.

## Inference gate

```text
Job group requires enrichment?
  -> no existing run for requested version: eligible
  -> existing completed run for same version: read persisted result; never call LLM
  -> failed / skipped_low_context: do not retry automatically
  -> stale after explicit version or context policy change: eligible under a new version
  -> user chooses Re-infer: create explicitly authorised new version/run
```

Before an inference request, the system builds and persists a context snapshot containing:

1. company context;
2. industry context;
3. canonical occupation identity, when confirmed;
4. governed industry/domain context and selected applicable-domain link, when relevant;
5. specific Job Group and normalised-job context;
6. major-requirement context; and
7. related-role market signals, when already deterministically available.

The inference output is at most the candidate Top 5 hard skills and Top 5 soft skills per job group, each with confidence, concise reasoning, and evidence context. Its future contract may distinguish `occupation_core_skills` from `domain_specific_skills`, but both remain candidate skills and never market facts. Weak context lowers confidence or produces `skipped_low_context`; it never justifies invented specificity. `occurrence_count` remains a deterministic Python-side market-demand weight, not an LLM-produced fact.

## Analysis and programme-comparison flow

```text
Persisted ObservedSkill + persisted InferredSkill
  -> Python deterministic aggregation
  -> Industry / occupation / role Skill Demand Profile
  -> Program / Curriculum / Course / Learning Outcome mapping
  -> deterministic structural skill-gap calculation
  -> evidence pack with source and confidence labels
  -> single-agent LLM recommendation wording
  -> validation that every recommendation maps to the evidence pack
  -> teacher review
```

The analysis layer must not invoke Skill Inference. It reads only persisted results.

## Evidence handling

| Evidence type | Meaning | Report label |
|---|---|---|
| `direct_text_match` + `observed_high` | Skill was directly matched in permitted recruitment text | Observed from recruitment text |
| `llm_inference` + `inferred_medium` | Candidate skill inferred from sufficient role context | Candidate skill inferred from role context |
| `llm_inference` + `inferred_low` | Candidate skill inferred from limited role context | Low-confidence candidate inferred from role context |

All frequencies, coverage, distributions, occupation comparisons, demand measures, and curriculum gaps are calculated in Python from persisted skill rows. An LLM cannot create or change these figures. Reports must show source type, evidence level, and, for inferred skills, inference version.
