# Single Curriculum Intelligence Agent — Offline Demo

## Fixed workflow

`Curriculum Input → Curriculum Skill Analysis → Market-Curriculum Mapping → Structural Gap Analysis → Validated Recommendation → Final Analysis Result`

## Capability wrappers

- `load_market_skill_profile`
- `analyze_curriculum`
- `map_curriculum_to_market`
- `identify_structural_gaps`
- `generate_curriculum_recommendations`

## Execution

- Mode: `offline_frozen_artifacts`
- API calls: 0
- State history: `pending → analyzing_curriculum → mapping_market → identifying_gaps → generating_recommendations → completed`
- Priority gaps: 20
- Validated recommendations: 5

## Evidence boundary

- Recruitment skills are inferred candidate skills based on job-group context, not stated recruitment requirements.
- Curriculum data is MVP demo/sample content, not an official syllabus.
- not_observed means no frozen curriculum-text evidence was observed; it does not confirm absence from teaching.
- Recommendations are decision-support suggestions, not authoritative curriculum decisions.
- Market evidence comes from selective skill inference rather than all job groups.
- Curriculum evidence is from a demo/sample program and may not reflect comprehensive teaching.
- Market skill evidence is inferred and may not capture all local or emerging employer needs.
- Recommendations are decision-support suggestions, not authoritative or prescriptive curriculum decisions.
