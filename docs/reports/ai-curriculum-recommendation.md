# AI Curriculum Recommendation MVP

## Evidence boundary

- Recruitment skills are candidate skills inferred from job-group context, not stated recruitment requirements.
- Curriculum content is MVP demo/sample material, not an official syllabus.
- `not_observed` means no supplied curriculum-text evidence was observed; it does not prove absence from teaching.
- Recommendations are decision-support suggestions, not authoritative curriculum decisions.

## Execution

- Model: `gpt-4.1-mini`
- Prompt version: `curriculum-recommendation-prompt-v2-structured`
- API request attempts: 1
- Validation status: `passed`

## Recommendations

- **Integrate 软件开发 into IFN711 Industry Project** (integrate_skill_into_existing_course) — target skills: 软件开发; gaps: gap-01, gap-09; market refs: market-gap-01, market-gap-09; curriculum refs: none.
- **Add 网络安全与隐私保护 coverage in IFN712 Research in IT Practice** (integrate_skill_into_existing_course) — target skills: 网络安全与隐私保护; gaps: gap-02; market refs: market-gap-02; curriculum refs: none.
- **Strengthen and explicitly highlight 数据分析 skill in IFN712 Research in IT Practice** (strengthen_existing_content) — target skills: 数据分析; gaps: gap-03, gap-10; market refs: market-gap-03, market-gap-10; curriculum refs: curriculum-04.
- **Incorporate Algorithm Design & Optimization in IFN711 Industry Project** (integrate_skill_into_existing_course) — target skills: 算法设计与优化; gaps: gap-04, gap-08; market refs: market-gap-04, market-gap-08; curriculum refs: none.
- **Introduce 网络安全与隐私保护 optional module or activities in IFN711 Industry Project** (optional_module_or_activity) — target skills: 网络安全与隐私保护; gaps: gap-02; market refs: market-gap-02; curriculum refs: none.
