import { readFileSync, writeFileSync } from 'node:fs';
const root='data/processed/record_role_classification_v1';const gs=JSON.parse(readFileSync(`${root}/groups/record_role_groups.json`)).groups;
const d={
'RRG-8e4c705747331965c057':['电子/电气/通信','电子/硬件开发','电路与硬件设计'],
'RRG-0f62652b996212874250':['生产制造','机械设计/制造',null],
'RRG-11f3297df7bd33b92946':['生产制造','质量管理','质量检验与过程控制'],
'RRG-dddf857eddb0a559c92a':['生产制造','机械设计/制造','机械结构与产品设计'],
'RRG-12895ffb22c2fef03373':['财务/审计/税务','会计','总账与财务核算'],
'RRG-e73d84773a078bbb5590':['财务/审计/税务','审计',null],
'RRG-b0788e753b91ec6fdd16':['互联网/AI','前端/移动开发','Web 与前端开发'],
'RRG-b6f5d69ccf632c871370':['咨询/翻译/法律','法律服务',null],
'RRG-29065e3ecb05e9c81dce':['运营/客服','新媒体运营',null],
'RRG-237c5b6205e497b8fa33':['互联网/AI','算法工程师',null],
'RRG-38cf0d1bd6bc663ffff9':['互联网/AI','测试',null],
'RRG-6e098153a5860b461caa':['采购/贸易','采购','采购执行与合同管理'],
'RRG-a2981a0b0549bcaf8cc5':['金融','银行',null],
'RRG-3f5a8d5bb8214e602da8':['互联网/AI','机器学习',null],
'RRG-2804b190025a71166209':['互联网/AI','机器学习','机器学习平台与工程'],
'RRG-6fcf8fb54ac70dc40b44':['互联网/AI','机器学习','机器学习平台与工程'],
'RRG-1d5486b92522266cf4c5':['互联网/AI',null,null],
'RRG-31ac8f7db68b5a5d75ee':['互联网/AI','销售技术支持',null],
'RRG-d32de3864fac406dd77c':['电子/电气/通信','电子/硬件开发',null],
'RRG-2b41b7fdb9fa2b39594f':['财务/审计/税务','会计',null],
'RRG-4226c90bcc6f97696f4c':['互联网/AI',null,null],
};
const rows=gs.filter(g=>d[g.record_role_group_id]).map(g=>{const [level_1,level_2,level_3]=d[g.record_role_group_id];return {record_role_group_id:g.record_role_group_id,canonical_title:g.canonical_title,level_1,level_2,level_3,mapping_status:level_3?'mapped':'review',member_count:g.member_count,member_record_role_ids:g.member_record_role_ids,source_record_ids:g.source_record_ids,evidence:{source:'canonical_title_plus_member_context_review',reason:`Codex group-level judgment; ${g.source_context_variant_count} source contexts retained for member-difference audit.`}}});writeFileSync(`${root}/group_classifications/batch_002.json`,JSON.stringify({schema_version:'record-role-group-classification-v1',mapping_method:'codex_semantic_judgment',processed_at:new Date().toISOString(),classifications:rows},null,2)+'\n');
