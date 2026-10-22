import { readFileSync, writeFileSync } from 'node:fs';
const dir='data/processed/record_role_classification_v1';
const roles=JSON.parse(readFileSync(`${dir}/record_roles.json`)).roles;
const ids='ee9980d1b31838dae36c5769 1a1625000a27088ca5b66205 881ae3892d5c7e8e3d0a4ff0 90d7cc916a7fb5138a114133 b39112f23fcceef6b772c72d 0b31df0f957994d110e428cf 5d043a828f93b64cd8831721 c6ca755e6e04fc6137dc134a 3ab3b90ddbcf82faaf9bb55a 8e149ab3df28353fdfa49714 255871771a2a98cebb0cc7ab 60663654c267fefa12d6aac3 c1afd355a4d88d949d6adee6 2a828d2837ebb599890f3873 89fda4809889e08957400bf0 297dff3ca9099545ba437ec4 12cea1c2ebe8d6d9e239e040 0e89a8ed3323ba9079d7c931 112fe3b473d3414e773b319d 90e852ab5877a14c2effd029'.split(' ');
const d={
'平面设计助理':['设计','视觉/交互设计','品牌与视觉设计','mapped'],
'RCS-有机合成研究员-RCS能力技术平台-武汉':['医疗健康','生物医药','生物医药研发','mapped'],
'市场金融培训生':['金融',null,null,'review'],'小号演奏岗':['影视/传媒',null,null,'review'],
'热工设计工程师':['生产制造','机械设计/制造',null,'review'],'造型岗':['设计',null,null,'review'],
'MICU工程师':['电子/电气/通信',null,null,'review'],'材料类管培生':['生产制造',null,null,'review'],
'土地储备业务岗':['房地产/建筑','房地产规划开发',null,'review'],'移动端全栈AI开发':['互联网/AI','前端/移动开发',null,'review'],
'城市更新工作管理员':['房地产/建筑','城市规划设计',null,'review'],'U3D 开发工程师':['互联网/AI','C++','图形与高性能计算','mapped'],
'产品岗':['产品',null,null,'review'],'奥赛老师':['教育培训','教师','基础教育教学','mapped'],
'系统开发工程师':['互联网/AI',null,null,'review'],'产品经理（硬件方向）':['产品','硬件产品经理','硬件产品规划','mapped'],
'出纳（会计学、教育技术学、广播电视工程、信息与通信工程、计算机科学与技术、水利工程、港口海岸及近海工程、环境科......':['财务/审计/税务','出纳','资金收付与结算','mapped'],
'工艺研究岗':['生产制造',null,null,'review'],'IQ图像工程师':['互联网/AI','算法工程师','计算机视觉与三维感知','mapped'],'项目经理':['互联网/AI','技术项目管理',null,'review']};
const by=new Map(roles.map(r=>[r.source_atomic_unit_id,r]));const classifications=ids.map(id=>{const r=by.get(id),x=d[r.source_title];if(!x)throw Error(r.source_title);const [level_1,level_2,level_3,classification_status]=x;return {record_role_id:r.record_role_id,source_record_id:r.source_record_id,source_atomic_unit_id:id,source_title:r.source_title,level_1,level_2,level_3,classification_status,evidence:{source:'source_title_and_raw_job_title',value:r.raw_job_title,reason:`Codex manual judgment based on stated role responsibility: ${r.source_title}.`}}});writeFileSync(`${dir}/classification_batch_004.json`,JSON.stringify({schema_version:'record-role-classification-v1',mapping_method:'codex_semantic_judgment',model:'Codex (GPT-5)',processed_at:new Date().toISOString(),classifications},null,2)+'\n');
