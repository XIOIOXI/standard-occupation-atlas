# High-family Merge Safety Audit

Deterministic audit only; no Job Group merge, Taxonomy change, LLM call, or Skill Inference was performed.

## Summary

- High families: 1,341
- SAFE / REVIEW_REQUIRED / UNSAFE_MIXED: 1,323 / 18 / 0
- SAFE groups / reduction: 4,212 / 2,889
- SAFE-only simulation: 12,957
- SAFE atomic units / records / companies: 6,410 / 2,269 / 2,132

## All families larger than 10

| Representative | Size | Classification | Signals | Reason |
|---|---:|---|---|---|
| 算法工程师 | 38 | REVIEW_REQUIRED | 算法 | broad occupation label requires semantic boundary review |
| 软件开发工程师 | 27 | SAFE | 软件 | titles differ only by safe role wording, recruitment modifiers, location, seniority, or punctuation |
| 结构工程师 | 22 | SAFE | 结构 | titles differ only by safe role wording, recruitment modifiers, location, seniority, or punctuation |
| AI应用工程师 | 21 | SAFE | - | titles differ only by safe role wording, recruitment modifiers, location, seniority, or punctuation |
| 人力资源岗 | 21 | REVIEW_REQUIRED | - | broad occupation label requires semantic boundary review |
| 财务岗 | 21 | REVIEW_REQUIRED | - | broad occupation label requires semantic boundary review |
| 应用工程师 | 20 | REVIEW_REQUIRED | 软件 | broad occupation label requires semantic boundary review |
| 硬件开发工程师 | 19 | SAFE | 硬件 | titles differ only by safe role wording, recruitment modifiers, location, seniority, or punctuation |
| 系统工程师 | 19 | REVIEW_REQUIRED | - | broad occupation label requires semantic boundary review |
| 采购 | 19 | REVIEW_REQUIRED | - | broad occupation label requires semantic boundary review |
| FPGA工程师 | 18 | SAFE | 软件 | titles differ only by safe role wording, recruitment modifiers, location, seniority, or punctuation |
| 技术支持工程师 | 18 | SAFE | - | titles differ only by safe role wording, recruitment modifiers, location, seniority, or punctuation |
| 技术支持 | 17 | SAFE | - | titles differ only by safe role wording, recruitment modifiers, location, seniority, or punctuation |
| 嵌入式软件开发工程师 | 16 | SAFE | 嵌入式, 软件 | titles differ only by safe role wording, recruitment modifiers, location, seniority, or punctuation |
| 项目工程师 | 16 | REVIEW_REQUIRED | - | broad occupation label requires semantic boundary review |
| 运维工程师 | 15 | SAFE | 运维 | titles differ only by safe role wording, recruitment modifiers, location, seniority, or punctuation |
| 助理工程师 | 14 | SAFE | 软件 | titles differ only by safe role wording, recruitment modifiers, location, seniority, or punctuation |
| 工艺开发 | 14 | REVIEW_REQUIRED | 工艺 | compound title may contain more than one role boundary |
| 人工智能工程师 | 13 | SAFE | - | titles differ only by safe role wording, recruitment modifiers, location, seniority, or punctuation |
| 客户经理 | 13 | SAFE | - | titles differ only by safe role wording, recruitment modifiers, location, seniority, or punctuation |
| 机械研发工程师 | 13 | SAFE | - | titles differ only by safe role wording, recruitment modifiers, location, seniority, or punctuation |
| 营销岗 | 13 | SAFE | - | titles differ only by safe role wording, recruitment modifiers, location, seniority, or punctuation |
| 财务会计 | 13 | SAFE | - | titles differ only by safe role wording, recruitment modifiers, location, seniority, or punctuation |
| 财务管理岗 | 13 | SAFE | - | titles differ only by safe role wording, recruitment modifiers, location, seniority, or punctuation |
| C++开发 | 12 | SAFE | 软件 | titles differ only by safe role wording, recruitment modifiers, location, seniority, or punctuation |
| 产品设计 | 12 | SAFE | - | titles differ only by safe role wording, recruitment modifiers, location, seniority, or punctuation |
| 电气设计工程师 | 12 | SAFE | - | titles differ only by safe role wording, recruitment modifiers, location, seniority, or punctuation |
| 结构设计工程师 | 12 | SAFE | 结构 | titles differ only by safe role wording, recruitment modifiers, location, seniority, or punctuation |
| 下属各单位岗位 | 11 | SAFE | - | titles differ only by safe role wording, recruitment modifiers, location, seniority, or punctuation |
| 人事专员 | 11 | SAFE | - | titles differ only by safe role wording, recruitment modifiers, location, seniority, or punctuation |
| 审计 | 11 | SAFE | - | titles differ only by safe role wording, recruitment modifiers, location, seniority, or punctuation |
| 数据开发工程师 | 11 | SAFE | 数据 | titles differ only by safe role wording, recruitment modifiers, location, seniority, or punctuation |
| 法务 | 11 | SAFE | - | titles differ only by safe role wording, recruitment modifiers, location, seniority, or punctuation |
| 海外销售 | 11 | SAFE | - | titles differ only by safe role wording, recruitment modifiers, location, seniority, or punctuation |
| 行政专员 | 11 | SAFE | - | titles differ only by safe role wording, recruitment modifiers, location, seniority, or punctuation |

## Deterministic random sample (size <= 10)

{"SAFE": 100}

## Standard

SAFE is reserved for surface/recruitment variants without broad-title or specialization-boundary signals. Uncertain cases remain REVIEW_REQUIRED; conflicting protected specializations are UNSAFE_MIXED.
