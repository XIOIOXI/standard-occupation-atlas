# Taxonomy Coverage Analysis

Reference Taxonomy defines the classification space; recruitment data is mapped into that space.

## Scope and method

- Snapshot: `24923444-9eb3-4f4e-a2eb-e611b964287b`
- Market-eligible, non-duplicate recruitment records: 6,163
- Distinct raw job-title fields: 5,919
- Reference Taxonomy level-3 occupations: 452
- Generated title units retained for audit: 34,185
- Accepted title units used for automatic coverage: 20,964
- Review-required title units retained outside the automatic coverage denominator: 8,642
- Rejected non-job fragments retained outside candidate expansion: 4,579
- Splitter and quality gate are deterministic. Coverage is calculated only from accepted title units. Review-required and rejected units remain in `taxonomy_mapping_results.csv` for audit.
- Mapping is deterministic. Exact/standard matches use reference level-3 names, aliases (if present), safe formatting cleanup, and industry context only for disambiguation. Fuzzy similarity only produces a review suggestion, never an automatic level-3 assignment.

## Splitter quality summary

| Metric | Count |
|---|---:|
| Generated units | 34,185 |
| Accepted units | 20,964 |
| Review-required units | 8,642 |
| Rejected non-job fragments | 4,579 |
| Average accepted units per record | 3.40 |
| Records with >10 generated units | 1,021 |
| Records with >10 accepted units | 519 |

## Coverage summary

| Level | Mapped | Unmapped | Coverage |
|---|---:|---:|---:|
| Level 1 | 11,229 | 9,735 | 53.6% |
| Level 2 | 2,039 | 18,925 | 9.7% |
| Level 3 exact/standard | 1,741 | 19,223 | 8.3% |

## Level-3 mapping types

- Exact or standard mapped: 1,741
- Alias mapped: 0
- Semantic/manual-review suggestions: 298
- Unmapped: 18,925

## Top 30 unmapped or review-required job titles

| Candidate job title | Status | Occurrences | Companies | Locations | Suggested level 1 | Suggested level 2 |
|---|---|---:|---:|---:|---|---|
| 算法工程师 | review_required | 130 | 126 | 102 |  | 机器人 |
| 管理培训生 | pending | 94 | 90 | 74 |  |  |
| 软件开发工程师 | pending | 93 | 89 | 81 |  |  |
| 测试工程师 | review_required | 88 | 88 | 82 |  |  |
| 研发工程师 | review_required | 85 | 83 | 78 |  |  |
| 销售工程师 | pending | 76 | 72 | 65 |  |  |
| 管培生 | pending | 71 | 66 | 54 |  |  |
| AI应用工程师 | pending | 63 | 60 | 54 |  |  |
| 客户经理 | pending | 59 | 53 | 51 |  |  |
| 结构工程师 | review_required | 53 | 50 | 42 |  |  |
| 财务管理岗 | pending | 52 | 51 | 43 |  |  |
| 财务管培生 | pending | 47 | 45 | 38 |  |  |
| 人力资源岗 | pending | 46 | 45 | 39 |  |  |
| 产品工程师 | pending | 43 | 39 | 39 |  |  |
| AI模型工程师 | pending | 41 | 40 | 35 |  |  |
| 财务岗 | pending | 39 | 37 | 32 |  |  |
| 技术支持工程师 | review_required | 37 | 36 | 35 |  | 通信网络 |
| AI Infra工程师 | pending | 37 | 35 | 31 |  |  |
| 综合管理岗 | pending | 36 | 36 | 22 |  |  |
| 市场营销岗 | pending | 31 | 28 | 31 |  |  |
| 财务专员 | pending | 30 | 29 | 25 |  |  |
| 营销管培生 | pending | 29 | 28 | 28 |  |  |
| 销售管培生 | pending | 29 | 28 | 25 |  |  |
| 嵌入式开发工程师 | pending | 29 | 24 | 22 |  |  |
| 生产管培生 | pending | 28 | 28 | 28 |  |  |
| 硬件技术工程师 | pending | 28 | 26 | 23 |  |  |
| 销售经理 | pending | 27 | 25 | 26 |  |  |
| 算法研究员 | pending | 26 | 25 | 23 |  |  |
| 项目管理岗 | pending | 26 | 25 | 20 |  |  |
| AI安全与隐私工程师 | pending | 26 | 24 | 19 |  |  |

## Coverage by reference level 1

| Level 1 | Taxonomy level-3 roles | Mapped title units | Candidate title-unit occurrences |
|---|---:|---:|---:|
| 信息技术与数字产业 | 75 | 2,186 | 976 |
| 电子信息与通信产业 | 28 | 1,608 | 684 |
| 智能制造与工业 | 33 | 1,084 | 348 |
| 新能源与能源产业 | 31 | 663 | 374 |
| 汽车与智能交通 | 30 | 235 | 109 |
| 航空航天与低空经济 | 14 | 119 | 85 |
| 先进材料与化工 | 15 | 28 | 0 |
| 生物医药与生命科学 | 18 | 185 | 133 |
| 医疗健康与医疗器械 | 16 | 158 | 71 |
| 金融与金融科技 | 28 | 2,424 | 1,391 |
| 商业与企业服务 | 28 | 208 | 0 |
| 市场营销与传媒 | 21 | 222 | 111 |
| 电子商务与零售 | 16 | 282 | 153 |
| 物流与供应链 | 15 | 366 | 190 |
| 建筑与房地产 | 17 | 486 | 307 |
| 教育与人力资本 | 13 | 672 | 574 |
| 文化旅游体育与娱乐 | 19 | 1 | 0 |
| 农业食品与消费产业 | 13 | 211 | 110 |
| 环境生态与资源 | 13 | 27 | 32 |
| 公共管理与社会服务 | 9 | 64 | 18 |

## Level-2 review queue

A `review_candidate_present` flag means market titles with a deterministic partial/review association appear under the field. It is not an automatic proposal to add a level-3 role.

| Level 1 | Level 2 | Existing level-3 roles | Mapped title units | Candidate occurrences | Possible level-3 addition review |
|---|---|---:|---:|---:|---|
| 信息技术与数字产业 | 软件开发与工程 | 13 | 237 | 29 | review_candidate_present |
| 信息技术与数字产业 | 软件测试与质量 | 6 | 73 | 5 | review_candidate_present |
| 信息技术与数字产业 | 人工智能与机器学习 | 9 | 45 | 1 | review_candidate_present |
| 信息技术与数字产业 | 生成式AI与大模型 | 7 | 36 | 4 | review_candidate_present |
| 信息技术与数字产业 | AI产品与解决方案 | 7 | 31 | 4 | review_candidate_present |
| 信息技术与数字产业 | 数据分析与数据科学 | 7 | 30 | 2 | review_candidate_present |
| 信息技术与数字产业 | 数据工程与数据平台 | 6 | 37 | 5 | review_candidate_present |
| 信息技术与数字产业 | 云计算与DevOps | 6 | 12 | 1 | review_candidate_present |
| 信息技术与数字产业 | 网络与信息安全 | 7 | 39 | 0 |  |
| 信息技术与数字产业 | 信息化与IT服务 | 7 | 13 | 0 |  |
| 电子信息与通信产业 | 通信网络 | 6 | 7 | 1 | review_candidate_present |
| 电子信息与通信产业 | 电子硬件与嵌入式 | 7 | 197 | 3 | review_candidate_present |
| 电子信息与通信产业 | 芯片设计 | 6 | 33 | 1 | review_candidate_present |
| 电子信息与通信产业 | 半导体制造与封装 | 5 | 14 | 0 |  |
| 电子信息与通信产业 | 光电与显示 | 4 | 40 | 2 | review_candidate_present |
| 智能制造与工业 | 机械设计与装备 | 6 | 284 | 17 | review_candidate_present |
| 智能制造与工业 | 自动化与控制 | 5 | 23 | 1 | review_candidate_present |
| 智能制造与工业 | 机器人 | 5 | 22 | 0 |  |
| 智能制造与工业 | 工业互联网 | 4 | 0 | 0 |  |
| 智能制造与工业 | 数字孪生与工业建模 | 4 | 21 | 2 | review_candidate_present |
| 智能制造与工业 | 智能制造与生产 | 5 | 25 | 2 | review_candidate_present |
| 智能制造与工业 | 质量与可靠性 | 4 | 84 | 4 | review_candidate_present |
| 新能源与能源产业 | 光伏与太阳能 | 4 | 1 | 0 |  |
| 新能源与能源产业 | 风能 | 3 | 5 | 0 |  |
| 新能源与能源产业 | 储能 | 4 | 4 | 0 |  |
| 新能源与能源产业 | 电池 | 5 | 13 | 7 | review_candidate_present |
| 新能源与能源产业 | 氢能与燃料电池 | 4 | 0 | 0 |  |
| 新能源与能源产业 | 电力与电网 | 6 | 98 | 3 | review_candidate_present |
| 新能源与能源产业 | 绿色低碳与ESG | 5 | 0 | 0 |  |
| 汽车与智能交通 | 整车研发 | 5 | 3 | 0 |  |
| 汽车与智能交通 | 智能驾驶 | 5 | 12 | 0 |  |
| 汽车与智能交通 | 汽车电子 | 4 | 2 | 0 |  |
| 汽车与智能交通 | 新能源汽车 | 4 | 0 | 0 |  |
| 汽车与智能交通 | 汽车制造与质量 | 4 | 0 | 0 |  |
| 汽车与智能交通 | 汽车销售与服务 | 4 | 0 | 0 |  |
| 汽车与智能交通 | 智能交通 | 4 | 0 | 0 |  |
| 航空航天与低空经济 | 航空航天 | 5 | 1 | 2 | review_candidate_present |
| 航空航天与低空经济 | 无人机与低空技术 | 5 | 0 | 0 |  |
| 航空航天与低空经济 | 卫星与空间信息 | 4 | 0 | 0 |  |
| 先进材料与化工 | 材料研发 | 5 | 24 | 0 |  |
| 先进材料与化工 | 半导体与电子材料 | 3 | 0 | 0 |  |
| 先进材料与化工 | 化工与过程工程 | 4 | 4 | 0 |  |
| 先进材料与化工 | 新材料产业化 | 3 | 0 | 0 |  |
| 生物医药与生命科学 | 生物技术 | 5 | 1 | 0 |  |
| 生物医药与生命科学 | 药物研发 | 4 | 2 | 1 | review_candidate_present |
| 生物医药与生命科学 | 临床与注册 | 5 | 2 | 1 | review_candidate_present |
| 生物医药与生命科学 | 生物数据 | 4 | 0 | 0 |  |
| 医疗健康与医疗器械 | 医疗器械研发 | 4 | 2 | 0 |  |
| 医疗健康与医疗器械 | 医疗信息化 | 4 | 0 | 0 |  |
| 医疗健康与医疗器械 | 医学检验与诊断 | 3 | 0 | 0 |  |
| 医疗健康与医疗器械 | 医疗服务 | 5 | 2 | 3 | review_candidate_present |
| 金融与金融科技 | 银行 | 5 | 0 | 0 |  |
| 金融与金融科技 | 证券与资本市场 | 5 | 37 | 12 | review_candidate_present |
| 金融与金融科技 | 保险 | 5 | 2 | 0 |  |
| 金融与金融科技 | 金融科技 | 4 | 4 | 0 |  |
| 金融与金融科技 | 风险与合规 | 4 | 6 | 0 |  |
| 金融与金融科技 | 财务与会计 | 5 | 63 | 0 |  |
| 商业与企业服务 | 产品管理 | 6 | 90 | 0 |  |
| 商业与企业服务 | 项目管理 | 5 | 50 | 0 |  |
| 商业与企业服务 | 商业分析与战略 | 4 | 5 | 0 |  |
| 商业与企业服务 | 咨询 | 4 | 8 | 0 |  |
| 商业与企业服务 | 人力资源 | 5 | 33 | 0 |  |
| 商业与企业服务 | 法务与合规 | 4 | 22 | 0 |  |
| 市场营销与传媒 | 市场营销 | 4 | 9 | 0 |  |
| 市场营销与传媒 | 品牌 | 3 | 7 | 0 |  |
| 市场营销与传媒 | 广告与公关 | 4 | 1 | 0 |  |
| 市场营销与传媒 | 内容与媒体 | 5 | 47 | 1 | review_candidate_present |
| 市场营销与传媒 | 数字营销 | 5 | 2 | 0 |  |
| 电子商务与零售 | 电商运营 | 4 | 29 | 10 | review_candidate_present |
| 电子商务与零售 | 跨境电商 | 4 | 7 | 0 |  |
| 电子商务与零售 | 用户增长与会员 | 4 | 8 | 2 | review_candidate_present |
| 电子商务与零售 | 零售与消费 | 4 | 7 | 3 | review_candidate_present |
| 物流与供应链 | 供应链管理 | 3 | 1 | 0 |  |
| 物流与供应链 | 采购与寻源 | 4 | 57 | 0 |  |
| 物流与供应链 | 物流与运输 | 4 | 4 | 1 | review_candidate_present |
| 物流与供应链 | 仓储与配送 | 4 | 2 | 2 | review_candidate_present |
| 建筑与房地产 | 建筑设计 | 3 | 8 | 5 | review_candidate_present |
| 建筑与房地产 | 土木与结构 | 3 | 3 | 0 |  |
| 建筑与房地产 | 工程管理 | 4 | 2 | 0 |  |
| 建筑与房地产 | 城市规划 | 3 | 1 | 0 |  |
| 建筑与房地产 | 房地产 | 4 | 0 | 0 |  |
| 教育与人力资本 | 基础教育 | 3 | 11 | 5 | review_candidate_present |
| 教育与人力资本 | 高等教育 | 3 | 3 | 3 | review_candidate_present |
| 教育与人力资本 | 职业教育 | 3 | 0 | 0 |  |
| 教育与人力资本 | 教育产品与科技 | 4 | 1 | 0 |  |
| 文化旅游体育与娱乐 | 旅游 | 3 | 0 | 0 |  |
| 文化旅游体育与娱乐 | 酒店与餐饮 | 4 | 1 | 0 |  |
| 文化旅游体育与娱乐 | 文化创意 | 4 | 0 | 0 |  |
| 文化旅游体育与娱乐 | 影视与娱乐 | 4 | 0 | 0 |  |
| 文化旅游体育与娱乐 | 体育 | 4 | 0 | 0 |  |
| 农业食品与消费产业 | 现代农业 | 4 | 3 | 0 |  |
| 农业食品与消费产业 | 食品研发 | 3 | 3 | 0 |  |
| 农业食品与消费产业 | 食品安全 | 3 | 0 | 0 |  |
| 农业食品与消费产业 | 快消品 | 3 | 1 | 0 |  |
| 环境生态与资源 | 环境工程 | 4 | 1 | 0 |  |
| 环境生态与资源 | 环境监测 | 3 | 0 | 0 |  |
| 环境生态与资源 | 资源与地质 | 3 | 2 | 0 |  |
| 环境生态与资源 | 生态保护 | 3 | 0 | 0 |  |
| 公共管理与社会服务 | 公共管理 | 3 | 0 | 0 |  |
| 公共管理与社会服务 | 公共安全与应急 | 3 | 19 | 1 | review_candidate_present |
| 公共管理与社会服务 | 社会服务 | 3 | 0 | 0 |  |

## Interpretation boundary

Only accepted title units are included in automatic coverage and the occupation candidate pool. Review-required units remain audit evidence, and rejected non-job fragments are explicitly excluded from candidate expansion. This analysis does not add aliases or occupations, does not modify the reference workbook, and does not replace any raw recruitment job title with a standard occupation name.
