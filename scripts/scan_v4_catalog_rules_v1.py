"""Rule-driven, name-only catalog scan of the frozen v4 occupation snapshot."""
from __future__ import annotations
import json,re
from pathlib import Path
R=Path('data/processed/record_role_classification_v1'); NR=R/'name_registry'; SRC=NR/'standard_occupation_to_original_names_final_deterministic_v4.json'; OUT=R/'catalog_mappings'/'v4_catalog_rule_scan_v2_expanded.json'
# Rule targets are fixed taxonomy IDs from display_role_subcategory_taxonomy.mjs.
RULES=[
 ('java-server',r'Java(?:后端|开发工程师|开发)$',r'嵌入式|客户端','互联网/AI','Java','服务端与企业应用开发'),
 ('frontend-web',r'(?:Web)?前端开发工程师$',r'数字IC|芯片','互联网/AI','前端/移动开发','Web 与前端开发'),
 ('design-visual',r'^(?:UI|界面)设计师$',r'游戏','设计','视觉/交互设计','品牌与视觉设计'),
 ('design-interaction',r'^(?:用户体验|UX)设计师$',r'游戏','设计','视觉/交互设计','交互与体验设计'),
 ('hr-learning',r'^人力资源培训生$',r'','人力/行政/法务','人力资源','培训与人才发展'),
 ('media-social',r'^新媒体运营$',r'','运营/客服','新媒体运营',None),
 ('game-ux',r'^游戏UI设计师$',r'','设计','游戏设计','游戏体验与交互设计'),
 ('backend-service',r'^(?:后端|服务端)(?:开发|研发)工程师$',r'Java|Python','互联网/AI','后端开发','业务服务端开发'),
 ('data-engineering',r'^(?:大数据|数据)开发工程师$',r'分析','互联网/AI','数据开发','数据工程与数仓'),
 ('test-functional',r'^(?:软件)?测试工程师$',r'芯片|性能|安全','互联网/AI','测试','功能与自动化测试'),
 ('security-network',r'^(?:网络|信息)安全工程师$',r'AI|CPU|数据|应用','互联网/AI','网络/系统安全','网络与基础设施安全'),
 ('ops-support',r'^现场应用工程师\(FAE\)$',r'','互联网/AI','销售技术支持',None),
 ('finance-accounting',r'^会计$',r'','财务/审计/税务','会计','总账与财务核算'),
 ('ml-deep',r'^机器学习算法工程师$',r'','互联网/AI','机器学习',None),
 ('embedded-firmware',r'^(?:嵌入式|BSP|固件|MCU).*工程师$',r'硬件|PCB','互联网/AI','C++','嵌入式与实时开发'),
 ('pcb-design',r'^PCB(?:设计)?工程师$',r'','电子/通信/硬件','半导体/芯片','芯片设计'),
 ('linux-client',r'^Linux客户端开发工程师$',r'','互联网/AI','前端/移动开发','移动端与客户端开发'),
 ('sdk-development',r'^SDK开发工程师$',r'','互联网/AI','后端开发','平台与中间件开发'),
 ('u3d-development',r'^(?:U3D|Unity)开发工程师$',r'','互联网/AI','前端/移动开发','交互与可视化开发'),
 ('algorithm-general',r'^(?:算法工程师|AI算法工程师)$',r'自动驾驶|语音|图像|视觉','互联网/AI','算法工程师','算法研究与通用算法'),
 ('algorithm-vision',r'.*(?:图像|视觉|CV).*算法工程师$',r'','互联网/AI','算法工程师','计算机视觉与三维感知'),
 ('algorithm-llm',r'.*(?:大模型|LLM|AIGC).*算法工程师$',r'','互联网/AI','算法工程师','大模型与生成式 AI'),
 ('chip-test',r'^(?:芯片测试|芯片测试工程师)$',r'','电子/通信/硬件','半导体/芯片','封装与测试'),
 ('chip-design',r'.*(?:数字IC|模拟IC|版图|电路).*工程师$',r'前端开发','电子/通信/硬件','半导体/芯片','芯片设计'),
 ('editorial',r'^(?:编辑|全媒体记者/编辑)$',r'新媒体运营','影视/传媒','新闻/编辑','内容编辑与审校'),
 ('graphic-design',r'^平面设计(?:师|助理)?$',r'','设计','视觉/交互设计','品牌与视觉设计'),
 ('product-hardware',r'^产品经理\(硬件方向\)$',r'','产品','硬件产品经理','硬件产品规划'),
 ('product-internet',r'^(?:互联网)?产品经理$',r'硬件|金融','产品','互联网产品经理',None),
 ('sales-engineer',r'^销售工程师$',r'','销售','销售工程师',None),
 ('procurement',r'^(?:采购专员|采购工程师|设备采购专员)$',r'','采购/供应链','采购',None),
 ('foreign-trade',r'^(?:外贸业务员|外贸订单管理员|小语种外贸业务员)$',r'','销售','外贸销售',None),
 ('teacher',r'.*(?:教师|老师)$',r'培训生','教育','教师',None),
 ('researcher',r'.*(?:研究员|研究助理)$',r'算法|材料|化学','科研','科研人员',None),
 ('mechanical',r'^(?:机械|机电|电机|热工).*工程师$',r'质量|采购','制造/工程','机械工程',None),
 ('electrical',r'^(?:电气|自动化设备).*工程师$',r'质量|采购','制造/工程','电气工程',None),
 ('quality',r'.*(?:质量工程师|QE工程师)$',r'','制造/工程','质量管理',None),
 ('financial-analyst',r'^(?:财务分析师|财务BP)$',r'','财务/审计/税务','财务分析/财务BP',None),
 ('risk-control',r'^(?:风控专员|风险管理专员)$',r'','财务/审计/税务','风控',None),
]
def main():
 src=json.loads(SRC.read_text(encoding='utf-8')); mapped=[];partial=[];conflicts=[];unmatched=[]
 for o in src['occupations']:
  n=o['standard_name']; hits=[r for r in RULES if re.search(r[1],n,re.I) and not (r[2] and re.search(r[2],n,re.I))]
  base={'standard_occupation_id':o['standard_occupation_id'],'standard_name':n,'original_group_ids':o['original_group_ids'],'source_atomic_unit_ids':o['source_atomic_unit_ids'],'source_record_ids':o['source_record_ids']}
  if len(hits)>1:conflicts.append({**base,'matched_rule_ids':[h[0] for h in hits]})
  elif len(hits)==1:
   h=hits[0];rec={**base,'rule_id':h[0],'level_1':h[3],'level_2':h[4],'level_3':h[5]}
   (mapped if h[5] else partial).append(rec)
  else:unmatched.append(base)
 payload={'schema_version':'v4-catalog-rule-scan-v1','source_snapshot':SRC.name,'rule_count':len(RULES),'rules':[{'id':a,'include':b,'exclude':c,'level_1':d,'level_2':e,'level_3':f} for a,b,c,d,e,f in RULES],'counts':{'input_standard_occupations':len(src['occupations']),'mapped_level_3':len(mapped),'mapped_upper_only':len(partial),'rule_conflicts':len(conflicts),'unmatched':len(unmatched)},'mapped':mapped,'upper_level_review':partial,'rule_conflicts':conflicts,'unmatched':unmatched,'validation':src['validation']}
 with open(OUT,'x',encoding='utf-8') as f:json.dump(payload,f,ensure_ascii=False,indent=2);f.write('\n')
if __name__=='__main__':main()
