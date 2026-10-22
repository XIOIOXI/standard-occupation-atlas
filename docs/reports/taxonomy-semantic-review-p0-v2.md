# Taxonomy Semantic Review — P0 v2 Re-review

Scope: only the twelve `pending_human_review` P0 families from semantic-review-v1. This version independently assesses occupation identity and taxonomy placement. It is a proposal; the Reference Taxonomy was not modified.

- Model: `gpt-5 (Codex runtime)`
- Semantic review version: `semantic-review-v2`
- Prompt version: `semantic-candidate-review-prompt-v2`

## Distribution

| Identity decision | Count |
|---|---:|
| alias_of_existing | 0 |
| proposed_new_occupation | 5 |
| merge_with_candidate | 0 |
| too_generic | 1 |
| company_specific_or_program | 0 |
| pending_identity_review | 6 |

| Placement status | Count |
|---|---:|
| single_domain | 1 |
| cross_industry | 2 |
| context_dependent | 6 |
| placement_review_required | 3 |

## v1 to v2 comparison

| Candidate | v1 decision | v2 identity | v2 placement | Semantic interpretation |
|---|---|---|---|---|
| 测试工程师 | pending_human_review | pending_identity_review | context_dependent | The title covers software, semiconductor, and industrial validation contexts in the supplied evidence; those contexts can denote materially different occupation identities, not merely different placements. |
| 客户经理 | pending_human_review | pending_identity_review | context_dependent | The supplied market contexts span banking and non-banking settings, while the current taxonomy contains bank-specific customer-manager identities. The generic title alone does not establish one reusable identity. |
| 销售工程师 | pending_human_review | proposed_new_occupation | placement_review_required | The title is a specific, reusable occupation label across many companies. The current taxonomy has no demonstrated generic equivalent, but the supplied evidence does not justify one canonical Level-1/Level-2 placement yet. |
| 结构工程师 | pending_human_review | pending_identity_review | context_dependent | Existing entries use the same label for mechanical and civil-structure contexts, with additional automotive and medical-device variants. This is an identity collision, not only a multi-domain placement question. |
| 产品工程师 | pending_human_review | pending_identity_review | context_dependent | The evidence establishes market use across product and industrial contexts but does not delimit one stable occupation from product/process-engineering or product-management-adjacent meanings. |
| 技术支持工程师 | pending_human_review | proposed_new_occupation | cross_industry | The title has a stable technical-support identity across many companies. Existing taxonomy entries evidence telecommunications and materials-specific support, while the supplied market evidence also spans IT and manufacturing; domain context should refine, not erase, the proposed identity. |
| 财务专员 | pending_human_review | proposed_new_occupation | single_domain | The title is a concrete, reusable finance occupation label across multiple companies. It is not equivalent by name or stated boundary to the existing accountant, financial analyst, or finance-manager entries. |
| 销售经理 | pending_human_review | proposed_new_occupation | placement_review_required | The title expresses a stable, reusable management occupation and no equivalent generic Level-3 entry was identified. The available contexts span multiple sectors without supporting one canonical domain placement. |
| 项目工程师 | pending_human_review | proposed_new_occupation | cross_industry | The title is distinct from the existing project-manager titles and recurs across companies. It has a stable project-engineering identity; the energy and construction contexts are applicable domains rather than grounds to duplicate the occupation. |
| AI工程师 | pending_human_review | too_generic | context_dependent | The title does not distinguish among existing AI algorithm, generative-AI, application, or embedded-AI occupation identities. High occurrence does not make this umbrella label a canonical Level-3 occupation. |
| 项目助理 | pending_human_review | pending_identity_review | placement_review_required | The supplied title signals assistance but does not establish whether the underlying work is project management, engineering delivery, consulting, or another project context. It cannot safely be equated with project-management specialist. |
| 运维工程师 | pending_human_review | pending_identity_review | context_dependent | The available contexts include IT operations, energy operations, and industrial maintenance. Existing IT-operations and wind-operations entries demonstrate that the shared label can hide different occupation identities. |

## Proposed identities with domain treatment

| Candidate | Canonical domain | Applicable domains |
|---|---|---|
| 销售工程师 | placement review required | none proposed |
| 技术支持工程师 | 信息技术与数字产业 / 信息化与IT服务 | 信息技术与数字产业 / 信息化与IT服务 (canonical); 电子信息与通信产业 / 通信网络 (applicable); 先进材料与化工 / 新材料产业化 (applicable) |
| 财务专员 | 金融与金融科技 / 财务与会计 | 金融与金融科技 / 财务与会计 (canonical) |
| 销售经理 | placement review required | none proposed |
| 项目工程师 | 商业与企业服务 / 项目管理 | 商业与企业服务 / 项目管理 (canonical); 新能源与能源产业 / 储能 (applicable); 建筑与房地产 / 工程管理 (applicable) |

## ADR validation

- `销售工程师` resolves to a proposed occupation with `placement_review_required`; its identity is no longer pending solely because one placement is unavailable.
- `技术支持工程师` resolves to a proposed cross-industry occupation with governed canonical/applicable domain context.
- `项目工程师` resolves to a proposed cross-industry occupation with governed canonical/applicable domain context.
- Context-dependent titles remain identity-pending only where the supplied evidence indicates a materially different occupation boundary, rather than merely multiple industries.

## Validation

- 12/12 target families have one v2 result and unique family IDs.
- Existing occupation IDs were checked against the Reference Taxonomy; this bounded re-review produced no alias mapping claims.
- Every emitted applicable domain pair exists in the current Reference Taxonomy.
- semantic-review-v1 results, P1 families, the Reference Taxonomy workbook, recruitment records, splitter, and gate were not modified.
