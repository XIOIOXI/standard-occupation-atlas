# Taxonomy Semantic Review — P0 Pilot

P0 only: 22 candidate families. Results are LLM-assisted recommendations; the Reference Taxonomy was not modified.

- Model: `gpt-5 (Codex runtime)`
- Semantic review version: `semantic-review-v1`; prompt version: `semantic-candidate-review-prompt-v1`.

## Decision counts

| Decision | Count |
|---|---:|
| alias_of_existing | 5 |
| proposed_new_occupation | 0 |
| merge_with_candidate | 0 |
| too_generic | 5 |
| company_specific_or_program | 0 |
| pending_human_review | 12 |

## Focus cases

| Candidate | Evidence | Relevant taxonomy / decision | Reason |
|---|---|---|---|
| 测试工程师 | 88 occurrences; 88 companies; 82 locations | No single safe existing occupation; pending_human_review | Cross-industry testing has materially different domain meanings; generic title cannot select software, semiconductor, or industrial testing. |
| 研发工程师 | 86 occurrences; 84 companies; 79 locations | No single safe existing occupation; too_generic | R&D engineer is a broad function spanning many existing domain-specific R&D occupations. |
| 客户经理 | 84 occurrences; 76 companies; 70 locations | No single safe existing occupation; pending_human_review | Customer-manager meaning changes substantially between banking, enterprise sales, and service contexts. |
| 销售工程师 | 76 occurrences; 72 companies; 65 locations | No single safe existing occupation; pending_human_review | A reusable role is plausible, but the current taxonomy has no stable cross-industry sales-engineering placement. |
| 财务管理岗 | 52 occurrences; 51 companies; 43 locations | No single safe existing occupation; too_generic | Broad finance-management label lacks a stable level-3 occupational definition. |
| 结构工程师 | 53 occurrences; 50 companies; 42 locations | No single safe existing occupation; pending_human_review | Existing structural-engineer occupations occur in manufacturing, automotive, medical devices, and construction; context is required. |
| 产品工程师 | 43 occurrences; 39 companies; 39 locations | No single safe existing occupation; pending_human_review | Product engineer is cross-industry and distinct from product manager; placement requires human taxonomy policy. |
| 技术支持工程师 | 37 occurrences; 36 companies; 35 locations | No single safe existing occupation; pending_human_review | Could mean IT support, communications support, or domain-specific technical support; no single safe match. |

## Validation

- 22/22 P0 families have one versioned result.
- Every alias occupation ID exists in the Reference Taxonomy.
- No taxonomy workbook, splitter, candidate queue, or P1 family was changed or executed.
