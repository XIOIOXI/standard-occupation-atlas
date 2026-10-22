# Industry Occupation Structure Audit

Read-only derived audit. No frozen artifact, frontend, Job Group, taxonomy, Skill Intelligence, API, or LLM was changed.

## Result

The conservative precedence produces only the measured SAFE/exact-normalized reductions. It does not provide a reliable, broadly applicable semantic family layer across the 17 Industries. Adding a named family navigation layer would imply unsupported taxonomy for the remaining identities.

Evidence is the Industry-level distinct recruitment-record count. Every occupation node separately retains its own distinct-record demand; those node values are not summed because one recruitment record can contribute more than one title unit.

| Industry | Identities | Mapped | Unmapped | Candidate-covered | SAFE-covered | Singletons | Multi-member families | Display groups | Reduction | Unresolved | Evidence |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|

| 金融与金融科技 | 1402 | 40 | 1362 | 220 | 220 | 1145 | 220 | 1402 | 0 | 1402 | 686 |
| 信息技术与数字产业 | 1265 | 68 | 1197 | 328 | 328 | 835 | 328 | 1265 | 0 | 1265 | 294 |
| 电子信息与通信产业 | 828 | 54 | 774 | 244 | 244 | 495 | 244 | 828 | 0 | 828 | 220 |
| 教育与人力资本 | 510 | 22 | 488 | 94 | 94 | 389 | 94 | 510 | 0 | 510 | 160 |
| 智能制造与工业 | 617 | 32 | 585 | 184 | 184 | 380 | 184 | 617 | 0 | 617 | 142 |
| 新能源与能源产业 | 517 | 41 | 476 | 161 | 161 | 298 | 161 | 517 | 0 | 517 | 131 |
| 建筑与房地产 | 390 | 15 | 375 | 118 | 118 | 250 | 118 | 390 | 0 | 390 | 110 |
| 电子商务与零售 | 234 | 16 | 218 | 41 | 41 | 145 | 41 | 234 | 0 | 234 | 87 |
| 物流与供应链 | 272 | 13 | 259 | 68 | 68 | 183 | 68 | 272 | 0 | 272 | 80 |
| 市场营销与传媒 | 159 | 4 | 155 | 42 | 42 | 111 | 42 | 159 | 0 | 159 | 49 |
| 汽车与智能交通 | 218 | 14 | 204 | 82 | 82 | 113 | 82 | 218 | 0 | 218 | 49 |
| 农业食品与消费产业 | 194 | 5 | 189 | 37 | 37 | 134 | 37 | 194 | 0 | 194 | 48 |
| 生物医药与生命科学 | 180 | 8 | 172 | 31 | 31 | 119 | 31 | 180 | 0 | 180 | 43 |
| 医疗健康与医疗器械 | 168 | 14 | 154 | 34 | 34 | 109 | 34 | 168 | 0 | 168 | 35 |
| 公共管理与社会服务 | 45 | 1 | 44 | 6 | 6 | 34 | 6 | 45 | 0 | 45 | 31 |
| 航空航天与低空经济 | 127 | 10 | 117 | 45 | 45 | 75 | 45 | 127 | 0 | 127 | 25 |
| 环境生态与资源 | 25 | 1 | 24 | 8 | 8 | 12 | 8 | 25 | 0 | 25 | 11 |

## Financial case

Finance has 1402 current identities. Conservative safe grouping yields 1402 display groups (reduction 0); 1402 identities still require direct access. Pagination pressure is therefore a display-density issue, not evidence for creating a general occupation taxonomy.

The JSON artifact contains the requested occupation identity, normalized-title, mapping, candidate-family, merge-safety, and recruitment-lineage records for every requested title.

Trainee limitation: The frozen artifacts contain titles, normalized titles, mappings, candidate-family links, and recruitment lineage, but no reliable program/graduate/trainee semantic field. They therefore do not support automatically classifying these titles as recruitment projects or merging them.

## Grouping rule

1. canonical occupation identity: retained as one stable identity; no canonical family relation exists to merge distinct IDs
1. existing SAFE candidate family, only where it relates at least two current display identities in the same Industry
1. exact normalized-title relationship, only where it relates at least two unassigned current display identities
1. otherwise preserve the original occupation identity

REVIEW_REQUIRED candidate families are excluded from automatic grouping.
