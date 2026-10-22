import { readFileSync, writeFileSync } from 'node:fs';
import { resolve, join } from 'node:path';

const root = resolve(process.cwd(), 'data/processed/job_market_intelligence/market_map');
const industries = JSON.parse(readFileSync(join(root, 'display_industries.json'), 'utf8')).display_industries;

// User-defined navigation categories. These are display buckets, not a change to
// the frozen reference taxonomy or to any original occupation identity.
const CATEGORIES = [
  ['互联网/AI', /(?:\bAI\b|人工智能|算法|大模型|机器学习|深度学习|生成式|Agent|模型|软件|前端|后端|Java|Python|C\+\+|嵌入式|测试|网络安全|信息安全|数据(?:科学|工程|开发|分析|标注)|AI训练|运维|云原生|SRE|程序|技术项目|IT项目|研发项目|售前|技术销售|技术支持)/i],
  ['产品', /(?:产品经理|产品策划|产品设计|产品专员|游戏策划|游戏制作|游戏运营|化妆品产品)/i],
  ['运营/客服', /(?:运营|客服|客户服务|客户成功|客户经理|柜员|呼叫中心|编辑|SEO|SEM|品类)/i],
  ['设计', /(?:设计师|视觉|交互|UI|UX|原画|美术|创意设计|用户研究|展示|照明|游戏设计|服装设计|工业设计|家居设计)/i],
  ['影视/传媒', /(?:影视|传媒|编导|导演|制片|记者|编辑|摄影|主播|内容创作|儿童引导|演员|配音|模特|采编|出版|撰稿|主持|DJ|播音)/i],
  ['人力/行政/法务', /(?!.*销售)(?:人力资源|行政|法务|合规|员工关系|组织发展|招聘专员|前台|接待|文员|统计员)/i],
  ['财务/审计/税务', /(?:财务|会计|审计|税务|出纳)/i],
  ['咨询/翻译/法律', /(?:咨询|顾问|翻译|律师|法律)/i],
  ['教育培训', /(?:教师|讲师|教育|培训|教研|辅导员)/i],
  ['销售', /(?:销售|商务拓展|渠道|客户开发|招商主管|招商主管)/i],
  ['供应链/物流', /(?:供应链|物流|仓储|运输|配送)/i],
  ['房地产/建筑', /(?:房地产|建筑|土木|工程造价|物业|园林|施工|监理)/i],
  ['医疗健康', /(?:医疗|医师|医生|护士|药|临床|健康|生物医|检验)/i],
  ['酒店/旅游', /(?:酒店|旅游|旅行|景区|航空服务|空乘)/i],
  ['汽车', /(?:汽车|车辆|整车|车载|智能驾驶)/i],
  ['生产制造', /(?:生产|制造|工艺|质量工程|机械|材料|热设计|结构工程)/i],
  ['电子/电气/通信', /(?:电子|电气|通信|芯片|硬件|射频|电路|半导体|PCB)/i],
  ['采购/贸易', /(?:采购|贸易|进出口|供应商)/i],
  ['市场/公关/广告', /(?:市场|营销|公关|品牌|广告|媒介)/i],
  ['生活服务/零售', /(?:零售|门店|店长|美容|健身|家政|服务员)/i],
  ['餐饮', /(?:餐饮|厨师|食品|烘焙|咖啡|茶饮)/i],
  ['能源/环保/农业', /(?:能源|电力|环保|环境|农业|农|化工|矿|碳)/i],
  ['金融', /(?:金融|银行|证券|保险|投资|信贷|理财|资产管理)/i],
];
// Where a concrete title belongs to a more specific user-defined category,
// resolve it before the broad display buckets below (for example 医疗销售).
const CATEGORY_OVERRIDES = [
  ['餐饮', /(?:服务员|前厅|饮品师|餐饮管理|甜点|烘焙|餐饮店长|厨师|送餐员|帮厨|餐饮学徒)/i],
  ['能源/环保/农业', /(?:环保|农业|林业|禽畜|水产养殖|能源|地质|饲养员|畜牧兽医)/i],
  ['金融', /(?:互联网金融|投融资|证券|基金|期货|银行|保险精算|风控合规清算|资产评估|资信评估|催收员|保险理赔)/i],
  ['生产制造', /(?:搬运工|装卸工|化工|质量管理|生产营运|服装制作|挖掘机|铲车|叉车|机械(?:设计|制造)|服装纺织|生产安全|食品.*(?:研发|开发)|饮料.*(?:研发|开发)|普工|技工)/i],
  ['市场/公关/广告', /(?:商业数据分析|公关媒介|广告制作|政府事务|会务会展)/i],
  ['电子/电气/通信', /(?:电气|自动化|通信|电子维修|电子.*(?:开发|设计)|硬件.*(?:开发|设计)|半导体|芯片)/i],
  ['汽车', /(?:汽车|车辆|整车|车载|智能驾驶)/i],
  ['生活服务/零售', /(?:运动健身|理疗保健|纹绣|美甲|美睫|安保|家政|宠物美容|花艺|验光|美容|美体|美发|化妆|造型|保洁|网吧网管|宠物医生|婚礼策划|(?:^|[^医])维修)/i],
  ['医疗健康', /(?:医疗销售|医药销售|医疗器械|药品生产|生物医药|临床试验|导医|护工|保健理疗|药店|护士|医生|医技)/i],
  ['酒店/旅游', /(?:酒店|旅游|旅行|景区|导游|客房|迎宾)/i],
  ['房地产/建筑', /(?:房地产|房产|物业|园林|景观|建筑|装修|装饰|工程管理|城市规划)/i],
];
const OTHER = '其他职业';
const byLabel = new Map([...CATEGORIES.map(([label]) => [label, { label, occupations: new Map(), sourceIndustryLabels: new Set(), memberIndustryIds: new Set() }]), [OTHER, { label: OTHER, occupations: new Map(), sourceIndustryLabels: new Set(), memberIndustryIds: new Set() }]]);

function categoryFor(label) {
  return CATEGORY_OVERRIDES.find(([, pattern]) => pattern.test(label))?.[0]
    || CATEGORIES.find(([, pattern]) => pattern.test(label))?.[0]
    || OTHER;
}
for (const industry of industries) {
  const sourceLabels = industry.source_industry_labels || [industry.label];
  const sourceIds = industry.member_industry_ids || [industry.node_id];
  for (const occupation of industry.occupations) {
    const category = byLabel.get(categoryFor(occupation.label));
    sourceLabels.forEach(label => category.sourceIndustryLabels.add(label));
    sourceIds.forEach(id => category.memberIndustryIds.add(id));
    const existing = category.occupations.get(occupation.node_id);
    if (existing) {
      existing.recruitment_evidence_count = Math.max(existing.recruitment_evidence_count, occupation.recruitment_evidence_count);
      existing.source_industry_labels = [...new Set([...existing.source_industry_labels, ...(occupation.source_industry_labels || sourceLabels)])];
    } else {
      category.occupations.set(occupation.node_id, { ...occupation, source_industry_labels: occupation.source_industry_labels || sourceLabels });
    }
  }
}

const display_industries = [...byLabel.values()].map((category, index) => ({
  node_id: `category:${String(index + 1).padStart(2, '0')}`,
  label: category.label,
  occupations: [...category.occupations.values()].sort((a, b) => b.recruitment_evidence_count - a.recruitment_evidence_count || a.label.localeCompare(b.label, 'zh-Hans-CN')),
  source_industry_labels: [...category.sourceIndustryLabels],
  member_industry_ids: [...category.memberIndustryIds],
  display_relation: category.label === OTHER ? 'unclassified_display_titles' : 'user_defined_job_category',
}));
for (const category of display_industries) category.recruitment_evidence_count = category.occupations.reduce((sum, occupation) => sum + occupation.recruitment_evidence_count, 0);

writeFileSync(join(root, 'display_primary_categories.json'), `${JSON.stringify({
  schema_version: 'display-primary-categories-v1',
  classification: 'user_defined_display_navigation',
  categories: CATEGORIES.map(([label]) => label),
  fallback_category: OTHER,
  display_industries,
}, null, 2)}\n`);
console.log(`Wrote ${join(root, 'display_primary_categories.json')} (${display_industries.length} display categories)`);
