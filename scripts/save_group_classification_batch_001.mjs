import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
const root='data/processed/record_role_classification_v1';
const groups=JSON.parse(readFileSync(`${root}/groups/record_role_groups.json`)).groups;
const decisions={
 'RRG-8d9cec2e72c328b12241':['电子/电气/通信','半导体/芯片','芯片设计'],
 'RRG-a3f3587af1e3d9cc3a5c':['电子/电气/通信','电子/硬件开发','电路与硬件设计'],
 'RRG-70f9b0308a6caece3df0':['电子/电气/通信','半导体/芯片','封装与测试'],
 'RRG-e230e7c5418bb0c9c9f1':['金融','证券/基金/期货','基金期货交易与运营'],
 'RRG-d3f2c6606b26c8a50cde':['互联网/AI','前端/移动开发','Web 与前端开发'],
 'RRG-3825107f270933183cf2':['电子/电气/通信','半导体/芯片','芯片设计'],
 'RRG-4188a00751d8a2349abe':['互联网/AI','运维/技术支持','基础设施与云运维'],
 'RRG-1b21ff3332bc0be4dfe6':['电子/电气/通信','通信',null],
 'RRG-32f619c0fc80a1fcdd2c':['互联网/AI','数据分析师',null],
 'RRG-05324ad47abb08e9c208':['采购/贸易','采购','采购执行与合同管理'],
 'RRG-d649e95568caf62d7624':['财务/审计/税务','会计','总账与财务核算'],
 'RRG-a93e3d87a20aa2be4271':['生产制造','机械设计/制造','机械结构与产品设计'],
 'RRG-732f88a01128bb570b2e':['电子/电气/通信','电气/自动化','电气控制与自动化设计'],
 'RRG-2fbee0d9684352b21177':['互联网/AI','Java','服务端与企业应用开发'],
 'RRG-e8484bb77156e6e8bc49':['互联网/AI','Python',null],
 'RRG-6657e4faf9330e194a7a':['财务/审计/税务','出纳','资金收付与结算'],
 'RRG-769efb04960edd55b725':['设计','视觉/交互设计','品牌与视觉设计'],
};
const rows=groups.filter(g=>decisions[g.record_role_group_id]).map(g=>{const [level_1,level_2,level_3]=decisions[g.record_role_group_id];return {record_role_group_id:g.record_role_group_id,canonical_title:g.canonical_title,level_1,level_2,level_3,mapping_status:level_3?'mapped':'review',member_count:g.member_count,member_record_role_ids:g.member_record_role_ids,source_record_ids:g.source_record_ids,evidence:{source:'canonical_title_and_member_context_review',reason:`Codex group-level judgment for explicit professional title ${g.canonical_title}; all members retain their source contexts for later divergence checks.`}}});
mkdirSync(`${root}/group_classifications`,{recursive:true});writeFileSync(`${root}/group_classifications/batch_001.json`,JSON.stringify({schema_version:'record-role-group-classification-v1',mapping_method:'codex_semantic_judgment',processed_at:new Date().toISOString(),classifications:rows},null,2)+'\n');
