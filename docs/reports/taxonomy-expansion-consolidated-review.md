# Consolidated Taxonomy Expansion Review

This plan consolidates completed P0/P1 reviews only. It is a governance proposal and does not alter the Reference Taxonomy.

## Scope

- Consolidated unique families: 129 (P0 v1 non-pending 10 + P0 v2 replacement 12 + P1 v2 107)
- P2/P3 are explicitly deferred.

## Governance summary

| Bucket | Count |
|---|---:|
| recommended_for_approval | 15 |
| needs_manual_review | 38 |
| hold | 1 |
| deferred_for_mvp | 75 |

## Recommended aliases

软件开发、项目管理岗、C++开发工程师、法务岗、市场专员、审计岗、软件测试、财务会计岗、前端开发、机械设计、大数据开发、人力资源管理岗、后端开发

## Recommended new occupations

财务专员、技术服务工程师

## New occupations requiring manual review

销售工程师、技术支持工程师、销售经理、项目工程师、行政专员、硬件测试工程师、产品运营、热设计工程师、电气设计工程师、人事专员、数据科学工程师、FPGA工程师、数据开发工程师、网络安全与隐私保护工程师、结构设计工程师、解决方案工程师、品质工程师、解决方案经理、销售专员、售前工程师、嵌入式软件开发工程师、视觉算法工程师、AI Infra研究员、嵌入式工程师、芯片与器件设计工程师、软件开发高级工程师、营销策划、IE工程师、图像算法工程师、AI安全与隐私研究员、硬件开发工程师、法律事务岗、云服务开发工程师、物流专员、工业工程师、AI应用开发工程师

## Held proposals

硬件技术高级工程师

## Candidate merges

- 电气设计 → 电气设计工程师 (PCF-00163)
- 芯片与器件设计高级工程师 → 芯片与器件设计工程师 (PCF-00060)

## Cross-industry domain-link proposals

- 技术支持工程师: canonical 信息技术与数字产业 / 信息化与IT服务; applicable [{"level_1": "信息技术与数字产业", "level_2": "信息化与IT服务", "relationship_type": "canonical"}, {"level_1": "电子信息与通信产业", "level_2": "通信网络", "relationship_type": "applicable"}, {"level_1": "先进材料与化工", "level_2": "新材料产业化", "relationship_type": "applicable"}]
- 项目工程师: canonical 商业与企业服务 / 项目管理; applicable [{"level_1": "商业与企业服务", "level_2": "项目管理", "relationship_type": "canonical"}, {"level_1": "新能源与能源产业", "level_2": "储能", "relationship_type": "applicable"}, {"level_1": "建筑与房地产", "level_2": "工程管理", "relationship_type": "applicable"}]
- 产品运营: canonical 商业与企业服务 / 产品管理; applicable [{"level_1": "商业与企业服务", "level_2": "产品管理", "relationship_type": "canonical"}, {"level_1": "教育与人力资本", "level_2": "教育产品与科技", "relationship_type": "applicable"}]
- 技术服务工程师: canonical 信息技术与数字产业 / 信息化与IT服务; applicable [{"level_1": "信息技术与数字产业", "level_2": "信息化与IT服务", "relationship_type": "canonical"}, {"level_1": "电子信息与通信产业", "level_2": "通信网络", "relationship_type": "applicable"}]
- 售前工程师: canonical 信息技术与数字产业 / AI产品与解决方案; applicable [{"level_1": "信息技术与数字产业", "level_2": "AI产品与解决方案", "relationship_type": "canonical"}, {"level_1": "电子信息与通信产业", "level_2": "通信网络", "relationship_type": "applicable"}]

## Coverage simulation

- Baseline Level-3 coverage: 8.30% (1741/20964)
- Approved aliases only: 9.41% (1972/20964)
- Aliases + recommended new occupations: 9.64% (2020/20964)
- Simulations use accepted-unit occurrence upper bounds; they are not a formal remapping or approval.

## MVP Taxonomy Freeze policy

After an explicit human approval of this plan, freeze the Reference Taxonomy for MVP: do not execute P2/P3, do not pursue 100% coverage, and retain unknown/pending titles with raw context for Job Group and future offline Skill Inference. Reopen policy only for a demonstrated systemic issue.

## Validation

- No family duplication after P0 v2 replaced only P0 v1 pending families.
- Alias IDs, merge targets, and emitted domain pairs were validated.
- No exact/normalised duplicate proposed title, invalid reference, or circular merge was found.
- No source result, workbook, P2, or P3 work was modified or executed.
