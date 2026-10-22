# Pending Candidate Prioritization

Only `pending_review` candidates are included. This is deterministic grouping and queue preparation; no LLM or taxonomy change was performed.

## Summary

- Pending titles reviewed: 6,874
- Conservative candidate families: 6,733
- P0/P1 semantic review queue: 129
- Management-trainee families: 11

| Tier | Families |
|---|---:|
| P0 | 22 |
| P1 | 107 |
| P2 | 463 |
| P3 | 6,141 |

## Scoring

Priority = 40×log occurrence + 30×log companies + 10×log locations + 20×industry spread. Each component is retained in the family CSV. Thresholds: P0 ≥75, P1 ≥55, P2 ≥30, P3 <30.

## Top 30 families

| Rank | Representative | Occurrences | Companies | Locations | Score | Tier |
|---:|---|---:|---:|---:|---:|---|
| 1 | 测试工程师 | 88 | 88 | 82 | 100.0 | P0 |
| 2 | 研发工程师 | 86 | 84 | 79 | 99.407 | P0 |
| 3 | 客户经理 | 84 | 76 | 70 | 98.269 | P0 |
| 4 | 销售工程师 | 76 | 72 | 65 | 96.866 | P0 |
| 5 | 财务管理岗 | 52 | 51 | 43 | 90.353 | P0 |
| 6 | 结构工程师 | 53 | 50 | 42 | 90.338 | P0 |
| 7 | 产品工程师 | 43 | 39 | 39 | 86.725 | P0 |
| 8 | 技术支持工程师 | 37 | 36 | 35 | 84.659 | P0 |
| 9 | 财务专员 | 32 | 31 | 27 | 81.863 | P0 |
| 10 | 软件开发 | 29 | 29 | 27 | 80.582 | P0 |
| 11 | 采购 | 27 | 26 | 26 | 79.181 | P0 |
| 12 | 销售经理 | 27 | 25 | 26 | 78.929 | P0 |
| 13 | 项目管理岗 | 26 | 25 | 20 | 78.036 | P0 |
| 14 | 项目工程师 | 25 | 23 | 23 | 77.467 | P0 |
| 15 | 技术支持 | 25 | 23 | 22 | 77.371 | P0 |
| 16 | C++开发工程师 | 24 | 22 | 22 | 76.737 | P0 |
| 17 | AI工程师 | 23 | 23 | 22 | 76.657 | P0 |
| 18 | 项目助理 | 23 | 22 | 22 | 76.373 | P0 |
| 19 | 法务岗 | 22 | 22 | 21 | 75.893 | P0 |
| 20 | 工程管理岗 | 22 | 21 | 20 | 75.491 | P0 |
| 21 | 市场专员 | 21 | 21 | 20 | 75.094 | P0 |
| 22 | 运维工程师 | 21 | 21 | 20 | 75.094 | P0 |
| 23 | 行政专员 | 21 | 20 | 20 | 74.784 | P1 |
| 24 | 安全管理岗 | 21 | 20 | 18 | 74.557 | P1 |
| 25 | 硬件测试工程师 | 21 | 20 | 18 | 74.557 | P1 |
| 26 | 产品运营 | 21 | 19 | 18 | 74.231 | P1 |
| 27 | 系统工程师 | 19 | 19 | 16 | 73.13 | P1 |
| 28 | 审计岗 | 19 | 18 | 18 | 73.039 | P1 |
| 29 | 热设计工程师 | 21 | 20 | 20 | 72.784 | P1 |
| 30 | 技术岗 | 18 | 18 | 16 | 72.33 | P1 |

## Management-trainee review

Management-trainee families are flagged separately and are not proposed as occupations. They require a taxonomy policy decision distinguishing occupation, trainee type, and company programme.

## Impact upper bounds

- P0 accepted-unit upper bound: 866
- P0+P1 accepted-unit upper bound: 2,404
- These are prioritization impacts, not predicted new occupations or formal coverage results.

## Sanity constraints

- Grouping removes only surface suffix/format variants; domain qualifiers such as AI, software, hardware, or industry terms remain separate.
- Scores are log-scaled so repeated postings by one company do not dominate.
- All families retain member titles, industry distributions, and representative contexts.
