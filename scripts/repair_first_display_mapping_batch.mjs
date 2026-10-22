import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';

const path = 'data/processed/job_market_intelligence/market_map/display_role_mappings_v1.json';
const artifact = JSON.parse(readFileSync(path, 'utf8'));
const now = new Date().toISOString();
const reviewed = {
  'candidate-002512ea1146': ['互联网/AI', '算法工程师', null, 'review', ['算法研究与通用算法', '计算机视觉与三维感知', '大模型与生成式 AI'], '技能同时包含自然语言处理与计算机视觉，不能确认单一专业三级。'],
  'OCC0109': ['生产制造', null, null, 'review', ['化工工艺与生产', '机械制造与工艺'], '工艺设计、设备优化和质量控制可确认制造上级，但无行业证据确认化工或机械三级。'],
  'candidate-cbf1184074d8': ['互联网/AI', null, null, 'review', ['后端开发', '机器学习', '算法工程师'], '软件开发与 AI 技能并存，标题未给出技术分工，不能默认后端。'],
  'OCC0001': ['互联网/AI', null, null, 'review', ['后端开发', '前端/移动开发', '测试'], '软件开发、测试和运维均出现，不能由“软件工程师”默认到后端。'],
  'candidate-6e161a59e050': [null, null, null, 'review', [], '管理培训生是培养身份，不构成可判断的职业职责。'],
  'OCC0284': ['财务/审计/税务', '会计', '总账与财务核算', 'mapped', [], '“会计”可直接确认财务核算职责；未见成本、税务或审计限定。'],
  'candidate-536b6678714f': ['互联网/AI', '测试', null, 'review', ['功能与自动化测试', '性能与可靠性测试', '安全与专项测试'], '测试工程师可确认测试二级，但没有专项证据判定三级。'],
  'OCC0158': ['电子/电气/通信', '电气/自动化', '电气控制与自动化设计', 'mapped', [], '标题和可用技能均指向电气工程设计；未出现以现场调试为核心的证据。'],
  'candidate-1b484873f99f': ['互联网/AI', null, null, 'review', ['后端开发', '算法工程师'], '可用技能支持软件研发上级，但“研发工程师”没有足够技术分工信息。'],
  'OCC0082': ['电子/电气/通信', '电子/硬件开发', '电路与硬件设计', 'mapped', [], '数字硬件、模拟电路和硬件设计与开发共同支持电路与硬件设计。'],
  'OCC0289': ['产品', '互联网产品经理', null, 'review', ['用户与增长产品', '平台与企业产品', '人工智能与数据产品'], '需求分析、用户调研和体验设计确认互联网产品职能，但不足以确认产品类型三级。'],
  'candidate-d8cb9fa20e26': ['互联网/AI', '销售技术支持', null, 'review', ['售前与解决方案支持', '客户技术支持'], 'IT 技术销售可确认销售技术支持，但没有方案、投标或实施职责证据确认售前三级。'],
};
for (const row of artifact.mappings) {
  const [level1, level2, level3, status, candidates, reason] = reviewed[row.occupation_id];
  row.target_level_1 = level1; row.target_level_2 = level2; row.target_level_3 = level3;
  row.display_group_id = level1 && level2 ? `DIR:${level1}/${level2}` : null;
  row.role_subcategory_id = level1 && level2 && level3 ? `DIR:${level1}/${level2}/${level3}` : null;
  row.mapping_status = status; row.candidate_targets = candidates;
  row.reason = reason; row.model = 'Codex (GPT-5)'; row.mapping_method = 'codex_semantic_judgment';
  row.source_title = row.context_hash.replace('title:', ''); delete row.context_hash;
  row.source_hash = createHash('sha256').update(JSON.stringify({ occupation_id: row.occupation_id, source_title: row.source_title })).digest('hex');
  row.created_at = now; row.updated_at = now;
}
artifact.mapping_scope = 'codex_semantic_review_batch_001_repaired';
artifact.model = 'Codex (GPT-5)'; artifact.updated_at = now;
artifact.resume_cursor = { processed_occupation_count: artifact.mappings.length, next_source_offset: 12 };
writeFileSync(path, `${JSON.stringify(artifact, null, 2)}\n`, 'utf8');
