import { readFileSync, writeFileSync } from 'node:fs';
const dir='data/processed/record_role_classification_v1';
const roles=JSON.parse(readFileSync(`${dir}/record_roles.json`)).roles;
const ids=`77acabb21d766f342f7245f9 f6c1aeea25441b6a73973782 ffa0cebef7bdf8d7279bc45d fd24cc48e0bdbfa17c346275 ac03a35c944efbc55bd8cf3a e7ff1d0e2999c843c2ead4c4 aae31cde8d79f0e16ec9e8df 5f9e46eac7bdb2da1aabea69 a7e23e37c5056d46d72627a9 2de0c774576bac6676bbe3b0 04a0d6805a3f371543a115b3 fcb2dda76ed0de0ce48ac60d 21e0817c86016ecb1baa2918 6b254df229cb38c8abf07f4a 349a4863cc645f34fe2fa185 e9b35fc5b6e22a19eca92e47 4a03d89dc4612695e16feeb9 a22ba0c04328ee83816a512b 31119bac165f556d4d52b115 e47ea4500b7b3ee66dee741f f9e9906b40f38c7b5614851b 9803a1d7010c7888fd2ee847 47f83cdf5baf9b396eee84f3 52d00f0097862b9e924f8573 b0c7fdd0d1e03aef1f20d384 134e97c65c4c535de84f6e1b 6c57f2554526b9b1fb3a00ed 265e825494007944a758b770 041e8404d8ac70faaf587464 136768429d11f6b9331f4745 99a7380d140c7cbba95256d6 c386d7cc808c6866ff30b387 62d144c5e58d331c12ebdfac e1f45f0a097fc26d5e466f77 00e80752a15d87dc258ebb04 7d7b0671d9513f823a35d4ec 5e72c8a2de8f41336f67c0f0 5d102504ce627befbf5f635d a1466fc0d99852340a51181f 6b79def2eb52fc2b8f879b50 126dbfe54db510eb8c62076e 18397f3c93c9a250e3b1ad29 60efab75b67da810f734a31e c3f26f8cd6a1272838f6eca1 f8ea2703badbecd3c93d12dc 21e84f49bf5fc8e5a4675da2 e47feb89770ab872db50d911 7dd4819f99b90072f637e0c1 76af772f8974e1923561d4ae 76929ef557a5c84c1671fd39`.split(' ');
const byId=new Map(roles.map(r=>[r.source_atomic_unit_id,r]));
const decision={
  'PCB 工程师':['电子/电气/通信','电子/硬件开发','电路与硬件设计','mapped'],
  '软件工程师':['互联网/AI',null,null,'review'], '现场技术应用工程师（嵌入式方向）':['互联网/AI','销售技术支持','客户技术支持','review'],
  '发电部采制样员':['能源/环保/农业',null,null,'review'], '经营部采购':['采购/贸易','采购','采购执行与合同管理','mapped'],
  '销售工程师':['销售',null,null,'review'], '发行岗':['产品',null,null,'review'], '创新业务中心设计师':['设计',null,null,'review'],
  '芯片测试实习生':['电子/电气/通信','半导体/芯片','封装与测试','mapped'], '编辑（计算机科学、网络安全、信息安全、通信工程、数学、物理、化学、生物、古代文学、古代史、古典文献学、文科）':['影视/传媒','新闻/编辑','内容编辑与审校','mapped'],
  '工程咨询员（2人）':['咨询/翻译/法律','咨询/调研',null,'review'], '发射机械设计师......':['生产制造','机械设计/制造','机械结构与产品设计','mapped'], '运营专员':['运营/客服','业务运营',null,'review'], 'SDK开发工程师':['互联网/AI',null,null,'review'],
  '销售管培生（暖通空调、低温制冷、热能动力、建筑环境与能源工程、电气自动化等相关专业）':['销售',null,null,'review'], '交易员':['金融','证券/基金/期货','基金期货交易与运营','mapped'], '人力资源管理岗':['人力/行政/法务','人力资源',null,'review'],
  '电气储备生':['电子/电气/通信','电气/自动化',null,'review'], '海外售后技术支持工程师（金龙联合汽车（工业）苏州有限公司）':['互联网/AI','销售技术支持','客户技术支持','mapped'], '管培生':[null,null,null,'review'],
  '豆腐乳制作岗':['生产制造','生产营运',null,'review'], '市场专员':['市场/公关/广告','市场/营销','品牌与市场策略','mapped'], '项目管工程师':['互联网/AI','技术项目管理',null,'review'],
  '学业规划师':['教育培训',null,null,'review'], '嵌入式/上位机软件开发工程师':['互联网/AI',null,null,'review'], '电机质量工程师':['生产制造','质量管理','质量检验与过程控制','mapped'],
  '咨询顾问（内控与风险管......':['咨询/翻译/法律','咨询/调研',null,'review'], '小语种外贸业务员':['销售','外贸销售','海外客户开发','mapped'],
  '工商管理类法学类财会审计类语言文学类新闻类电气类土建水文类工程管理类 计算机类通信类电气类':[null,null,null,'review'], '流体动力研究员':['生产制造','机械设计/制造',null,'review'],
  '咨询策划管培生':['咨询/翻译/法律','咨询/调研',null,'review'], '前端开发':['互联网/AI','前端/移动开发','Web 与前端开发','mapped'], '前端开发工程师':['互联网/AI','前端/移动开发','Web 与前端开发','mapped'],
  '市场管理培训生':['市场/公关/广告','市场/营销',null,'review'], '考研教师':['教育培训','教师','基础教育教学','mapped'], '外贸订单管理员':['采购/贸易','外贸文员','外贸单证与资料管理','mapped'],
};
const classifications=ids.map(id=>{const r=byId.get(id),d=decision[r.source_title];if(!r||!d)throw Error(`missing manual decision ${id}`);const [level_1,level_2,level_3,classification_status]=d;return {record_role_id:r.record_role_id,source_record_id:r.source_record_id,source_atomic_unit_id:id,source_title:r.source_title,level_1,level_2,level_3,classification_status,evidence:{source:'source_title_and_raw_job_title',value:r.raw_job_title,reason:`Codex manual review: ${r.source_title}; industry retained separately and not used as occupational default.`}}});
writeFileSync(`${dir}/classification_batch_003.json`,JSON.stringify({schema_version:'record-role-classification-v1',mapping_method:'codex_semantic_judgment',model:'Codex (GPT-5)',processed_at:new Date().toISOString(),classifications},null,2)+'\n');
