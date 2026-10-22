# Taxonomy Semantic Review — P1 v2

Scope: exactly 107 P1 families; P0, P2, P3 and all taxonomy source data are excluded.

- Version: `semantic-review-v2` / `semantic-candidate-review-prompt-v2`
- Model: `gpt-5 (Codex runtime)`
- Cache reused: `True`

## Aggregate results

| Identity decision | Count |
|---|---:|
| alias_of_existing | 8 |
| proposed_new_occupation | 34 |
| merge_with_candidate | 2 |
| too_generic | 29 |
| company_specific_or_program | 0 |
| pending_identity_review | 34 |

| Placement status | Count |
|---|---:|
| single_domain | 8 |
| cross_industry | 3 |
| context_dependent | 63 |
| placement_review_required | 33 |

## Aliases

审计岗、软件测试、财务会计岗、前端开发、机械设计、大数据开发、人力资源管理岗、后端开发

## Proposed new occupations

行政专员、硬件测试工程师、产品运营、热设计工程师、电气设计工程师、人事专员、数据科学工程师、FPGA工程师、数据开发工程师、网络安全与隐私保护工程师、技术服务工程师、结构设计工程师、解决方案工程师、品质工程师、解决方案经理、销售专员、售前工程师、嵌入式软件开发工程师、视觉算法工程师、AI Infra研究员、嵌入式工程师、芯片与器件设计工程师、软件开发高级工程师、营销策划、IE工程师、图像算法工程师、AI安全与隐私研究员、硬件开发工程师、法律事务岗、云服务开发工程师、物流专员、工业工程师、AI应用开发工程师、硬件技术高级工程师

## Pending identity review

系统工程师、商务专员、海外销售、应用工程师、研发助理、销售助理、项目管理工程师、技术研究工程师、国内销售、产品助理、财务助理、建筑设计岗、销售代表、产品开发、客服经理、客服专员、结构与材料工程师、大客户销售、数字金融岗、法律合规岗、英语教师、版图设计工程师、视觉设计、综合柜员岗、人因与用户体验工程师、计划专员、数学教师、高中物理教师、市场运营、咨询顾问、高中数学教师、运营柜员岗、工业设计、机械研发工程师

## Validation

- 107/107 results, unique family IDs, and complete v2 result fields.
- Every cited existing occupation ID and emitted domain pair was validated against the current Reference Taxonomy.
- No management-trainee family appeared in P1; no modifier was emitted.
- No duplicate proposed title was found. Near-duplicate title similarity remains a human consolidated-review concern; no automatic merge was performed.
- No P0/P2/P3 execution, v1/P0-v2 overwrite, or Reference Taxonomy change occurred.

## Deterministic quality samples

The following first-five-per-decision samples are evidence-linked result records, not a new review pass.

| Decision | Candidate | Placement | Review rationale |
|---|---|---|---|
| proposed_new_occupation | 行政专员 | placement_review_required | The title is a specific, reusable occupation label with no safe semantic equivalent identified in the current Reference Taxonomy; evidence does not justify inventing one canonical domain placement. |
| proposed_new_occupation | 硬件测试工程师 | placement_review_required | The title is a specific, reusable occupation label with no safe semantic equivalent identified in the current Reference Taxonomy; evidence does not justify inventing one canonical domain placement. |
| proposed_new_occupation | 产品运营 | cross_industry | The title is a concrete, reusable occupation label. The emitted domain links use existing Reference Taxonomy pairs and retain cross-industry context without duplicating the identity. |
| proposed_new_occupation | 热设计工程师 | placement_review_required | The title is a specific, reusable occupation label with no safe semantic equivalent identified in the current Reference Taxonomy; evidence does not justify inventing one canonical domain placement. |
| proposed_new_occupation | 电气设计工程师 | placement_review_required | The title is a specific, reusable occupation label with no safe semantic equivalent identified in the current Reference Taxonomy; evidence does not justify inventing one canonical domain placement. |
| alias_of_existing | 审计岗 | single_domain | The supplied title is a surface naming variant of the cited existing occupation, rather than a new occupation proposal. |
| alias_of_existing | 软件测试 | single_domain | The supplied title is a surface naming variant of the cited existing occupation, rather than a new occupation proposal. |
| alias_of_existing | 财务会计岗 | single_domain | The supplied title is a surface naming variant of the cited existing occupation, rather than a new occupation proposal. |
| alias_of_existing | 前端开发 | single_domain | The supplied title is a surface naming variant of the cited existing occupation, rather than a new occupation proposal. |
| alias_of_existing | 机械设计 | single_domain | The supplied title is a surface naming variant of the cited existing occupation, rather than a new occupation proposal. |
| pending_identity_review | 系统工程师 | context_dependent | The supplied title and contexts do not safely establish one occupation identity; the uncertainty concerns the occupational boundary, not merely a missing single placement. |
| pending_identity_review | 商务专员 | context_dependent | The supplied title and contexts do not safely establish one occupation identity; the uncertainty concerns the occupational boundary, not merely a missing single placement. |
| pending_identity_review | 海外销售 | context_dependent | The supplied title and contexts do not safely establish one occupation identity; the uncertainty concerns the occupational boundary, not merely a missing single placement. |
| pending_identity_review | 应用工程师 | context_dependent | The supplied title and contexts do not safely establish one occupation identity; the uncertainty concerns the occupational boundary, not merely a missing single placement. |
| pending_identity_review | 研发助理 | context_dependent | The supplied title and contexts do not safely establish one occupation identity; the uncertainty concerns the occupational boundary, not merely a missing single placement. |
