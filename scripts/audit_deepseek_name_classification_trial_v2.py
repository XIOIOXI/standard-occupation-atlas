"""Save the human semantic audit of every DeepSeek v2 trial result.

The decisions below were entered one-by-one after reading only the title, the
model result, and the frozen taxonomy.  They are deliberately not inferred from
status or target ID; the script merely joins, validates, and writes them.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path("data/processed/record_role_classification_v1")
TRIAL = ROOT / "api_trials" / "deepseek_name_classification_trial_v2"
TAXONOMY = ROOT / "catalog_mappings" / "taxonomy_embedding_texts_v1.json"
OUTPUT = TRIAL / "manual_semantic_audit_100.json"

# (expected title, audit verdict, model handling, confirmed deepest category,
#  concise rationale).  MODEL means the audited model L3 target is retained.
# Verdict is intentionally one of correct / error / name_insufficient.
AUDIT = [
    ("通信网络运维工程师", "correct", "appropriate", "MODEL", "通信网络运维直接对应网络建设维护。"),
    ("CPUIP验证工程师", "correct", "appropriate", "MODEL", "CPU IP验证是芯片验证职责。"),
    ("市场职能", "name_insufficient", "appropriate", "市场/公关/广告", "仅说明市场职能，无法细分。"),
    ("会计专员", "correct", "appropriate", "MODEL", "会计专员可归入通用财务核算。"),
    ("分两个批次开展招聘。第一批次为省市局(公司)机关相关", "name_insufficient", "appropriate", None, "是招聘说明，不是岗位名称。"),
    ("外科医师", "correct", "appropriate", "MODEL", "外科医师属于临床诊疗。"),
    ("电气工程师(交付技术)", "error", "inappropriate", "电子/电气/通信/electronic-automation", "可确认电气自动化大类，交付技术不足以确认控制设计三级。"),
    ("客服培训生", "correct", "appropriate", "MODEL", "客服方向明确，培训生不改变核心职业。"),
    ("初级DQE工程师(电气)", "correct", "appropriate", "MODEL", "DQE属于质量控制，电气为产品方向。"),
    ("2026年浙江省新昌中学第三轮计划招聘教师6名(语文2人、英语1人、物理1人、化学1人、地理1人)", "correct", "appropriate", None, "多个学科教师粘连，不能作为单职业。"),
    ("燃烧室设计", "correct", "appropriate", "MODEL", "核心为机械结构设计。"),
    ("车辆控制工程师", "correct", "appropriate", "MODEL", "车辆控制属于汽车研发。"),
    ("数字化仿真应用工程师", "name_insufficient", "appropriate", None, "仿真对象与工程领域未体现。"),
    ("国际贸易经理", "correct", "appropriate", "MODEL", "国际市场与客户开发是明确贸易职责。"),
    ("设备技术员", "correct", "appropriate", "MODEL", "设备技术员可归设备维修安装。"),
    ("动力总成研发工程师", "correct", "appropriate", "MODEL", "动力总成研发属于汽车研发。"),
    ("总装工艺员", "correct", "appropriate", "MODEL", "总装工艺属于汽车制造工艺。"),
    ("安全研究工程师", "name_insufficient", "inappropriate", None, "安全可能是网络、生产或其他领域，不能确认应用安全。"),
    ("社媒运营(日语)", "correct", "appropriate", "MODEL", "社媒运营明确，日语是能力/市场限定。"),
    ("电气类管培生", "name_insufficient", "appropriate", "电子/电气/通信", "可确认电子电气领域，无法确认岗位职责。"),
    ("专区运营", "name_insufficient", "inappropriate", "运营/客服", "仅知运营，无法断定业务流程运营。"),
    ("供应链解决方案工程师", "name_insufficient", "inappropriate", "供应链/物流/supply-chain", "可确认供应链，解决方案不等同计划采购协同。"),
    ("算法工程师(安全方向)", "name_insufficient", "inappropriate", "互联网/AI/internet-algorithm", "安全方向不等同金融风控算法。"),
    ("国内业务管理专员", "name_insufficient", "appropriate", None, "业务管理未说明职能。"),
    ("结构材料工程师", "name_insufficient", "inappropriate", "生产制造", "材料研发与机械结构设计并非同一职责。"),
    ("初中物理教师", "correct", "appropriate", "MODEL", "基础教育教学明确。"),
    ("材料基因工程师", "error", "inappropriate", None, "材料信息学职业明确但目录无对应三级，应标目录缺口。"),
    ("环境可靠性工程师", "name_insufficient", "appropriate", None, "可靠性对象/行业未说明。"),
    ("市场综合监管辅助员", "error", "inappropriate", None, "市场监管辅助不同于政府事务申报，应标目录缺口或复核。"),
    ("教育服务助理", "correct", "appropriate", "MODEL", "教育机构服务助理可归教育行政。"),
    ("社媒运营经理(海外-西葡)", "correct", "appropriate", "MODEL", "海外语种限定不改变社媒运营职责。"),
    ("软体家具质检Qc管培生", "correct", "appropriate", "MODEL", "QC核心职责为质量检验过程控制。"),
    ("电源设计工程师", "correct", "appropriate", "MODEL", "电源设计属于电路与硬件设计。"),
    ("内贸业务", "name_insufficient", "inappropriate", "采购/贸易", "只能确认国内贸易，不能确认客户直销。"),
    ("工艺实验室培训生", "name_insufficient", "inappropriate", None, "实验室工艺领域不明，不能直接归化工。"),
    ("训练推理优化算法工程师", "correct", "appropriate", "MODEL", "训练推理优化是机器学习工程职责。"),
    ("AI游戏内容运营", "error", "inappropriate", "运营/客服/ops-content", "游戏内容运营不等同短视频与直播内容运营。"),
    ("AI推理工程师", "correct", "appropriate", "MODEL", "AI推理工程对应机器学习平台工程。"),
    ("系统建设运维及数据管理", "error", "inappropriate", None, "运维与数据管理并列，是多职责名称。"),
    ("宏观研究员", "correct", "appropriate", "MODEL", "宏观研究属于证券研究投资顾问。"),
    ("公司本部法务", "correct", "appropriate", "MODEL", "公司法务与合规明确。"),
    ("工艺设备", "name_insufficient", "appropriate", "生产制造/manufacturing-mechanical", "可确认机械制造领域，无法确认具体三级。"),
    ("零售金融市场营销岗(成都)", "error", "inappropriate", "金融/financial-banking", "零售金融营销不等同财富理财销售。"),
    ("市场营销员", "name_insufficient", "appropriate", "市场/公关/广告", "营销方向未细分到品牌策略。"),
    ("质量技术师", "correct", "appropriate", "MODEL", "质量技术岗位可归质量检验与过程控制。"),
    ("管理类管培生(财务管理、项目管理方向)", "correct", "appropriate", None, "财务和项目管理方向粘连。"),
    ("测试", "name_insufficient", "appropriate", None, "未说明软件、产品或检测领域。"),
    ("医生", "correct", "appropriate", "MODEL", "目录中的临床诊疗是医生的可用通用承接。"),
    ("投后管理", "correct", "appropriate", "金融/financial-investment", "可确认投融资大类，三级候选仅作复核。"),
    ("/ERBP研发人员", "name_insufficient", "appropriate", None, "缩写和研发对象无法从名称判定。"),
    ("媒介助理", "correct", "appropriate", "MODEL", "媒介关系与投放是媒介助理的直接承接。"),
    ("机务工程师(南京)", "name_insufficient", "appropriate", None, "机务可能指航空、车辆或设备，行业未见。"),
    ("管培生专项计划", "name_insufficient", "appropriate", None, "计划不是具体职业。"),
    ("业务管理", "name_insufficient", "appropriate", None, "业务管理过于宽泛。"),
    ("创意设计师", "correct", "appropriate", "MODEL", "创意设计可归品牌与视觉设计。"),
    ("线上运营主管", "name_insufficient", "inappropriate", "运营/客服", "线上运营与线下门店运营相反，不能指向门店三级。"),
    ("智能制造专员", "name_insufficient", "appropriate", "生产制造", "可确认制造领域，职责方向仍不足。"),
    ("助理软件工程师", "name_insufficient", "appropriate", "互联网/AI", "软件工程明确但不能推定后端。"),
    ("国产CADCAM软件开发工程师(参与国产CAD/CAM软件核心模块设计开发等)", "name_insufficient", "appropriate", "互联网/AI", "软件开发明确，但名称没有C++语言证据。"),
    ("计划控制工程师", "name_insufficient", "appropriate", None, "计划控制可在项目或制造等领域，未能确定。"),
    ("风控创优生", "name_insufficient", "appropriate", None, "风控的行业与具体风险职责未明。"),
    ("算法集成工程师", "name_insufficient", "appropriate", "互联网/AI/internet-algorithm", "可确认算法，集成方向不足以确认三级。"),
    ("光学算法工程师", "name_insufficient", "appropriate", "互联网/AI/internet-algorithm", "光学算法未必是计算机视觉三级。"),
    ("DFT可测性设计工程师", "correct", "appropriate", "MODEL", "DFT是明确芯片验证/可测性设计。"),
    ("检测员", "name_insufficient", "appropriate", None, "检测对象和行业缺失。"),
    ("股权融资及财务顾问", "correct", "appropriate", "MODEL", "股权融资财务顾问可归交易融资顾问。"),
    ("专业课教师", "name_insufficient", "appropriate", "教育培训", "教学层级和专业课程类型未说明。"),
    ("硬件研发工程师", "correct", "appropriate", "MODEL", "硬件研发可由电路与硬件设计通用承接。"),
    ("总经办总裁助理", "error", "inappropriate", "人力/行政/法务", "总裁助理是明确行政支持；目录缺少更细三级。"),
    ("管培生岗位(研发、职能、商业化、生产&供应链)", "correct", "appropriate", None, "多个培养方向粘连。"),
    ("证券事务经理", "error", "inappropriate", "金融/financial-securities", "证券事务不等同基金期货交易运营，三级不能确认。"),
    ("教学科研岗(政治学理论、中共党史、社会学、马克思主义中国化研究、思想政治教育、基础心理学、发展与教育心理学、应用心理学)", "correct", "appropriate", "MODEL", "多学科不改变高等教育教学科研的核心。"),
    ("岗理财经理", "name_insufficient", "appropriate", None, "名称疑有截断，不能据此确认理财岗位。"),
    ("人力资源储备", "name_insufficient", "inappropriate", "人力/行政/法务/people-hr", "可确认人力资源，不能推定招聘方向。"),
    ("基础设施互联互通促进中心专技", "name_insufficient", "appropriate", None, "组织名称与专技不足以确定实际职业。"),
    ("私人教练团课全职/兼职教练职能/技术", "correct", "appropriate", None, "全职兼职、私教团课和职能技术多项粘连。"),
    ("油气储运与新能源开发", "error", "inappropriate", None, "油气储运与新能源开发是两个核心职责，应标多岗位。"),
    ("财务内控", "correct", "appropriate", "MODEL", "财务内控可明确归内部控制与内审。"),
    ("算法工程师(媒体算法)", "name_insufficient", "appropriate", "互联网/AI/internet-algorithm", "媒体算法可确认算法，不能确定通用算法三级。"),
    ("工程", "name_insufficient", "appropriate", None, "仅有工程一词。"),
    ("新闻宣传", "correct", "appropriate", "MODEL", "新闻宣传直接对应品牌公关传播。"),
    ("检测技术等", "name_insufficient", "appropriate", None, "“等”表明名称不完整且领域不明。"),
    ("生产调度工程师", "correct", "appropriate", "MODEL", "生产调度直接对应生产计划与调度。"),
    ("生产制造员", "error", "inappropriate", "生产制造/manufacturing-general-worker", "仅能确认普工/制造员，不能限定装配线。"),
    ("售后助理", "name_insufficient", "appropriate", None, "售后可能是客服、维修或商务支持。"),
    ("法律事务相关", "name_insufficient", "inappropriate", "咨询/翻译/法律", "“相关”未表达具体公司法务合规职责。"),
    ("法务风控岗", "correct", "appropriate", None, "法务与风控并列，属于多岗位粘连。"),
    ("方案解决高级工程师", "name_insufficient", "appropriate", None, "方案解决的技术领域不明。"),
    ("文案实习生(德语/英语)", "error", "inappropriate", "运营/客服/ops-copywriting", "语言是能力限定，核心职业仍是文案而非多职业。"),
    ("企管法规", "name_insufficient", "appropriate", None, "企业管理或法规职责无法区分。"),
    ("化工外贸业务员", "error", "inappropriate", "采购/贸易/trade-import-export", "化工是产品方向，外贸业务员是单一贸易职业。"),
    ("支撑", "name_insufficient", "appropriate", None, "职责完全不明。"),
    ("机器人系统开发工程师", "correct", "appropriate", "MODEL", "机器人系统开发可归机器人与具身智能。"),
    ("客户订单计划员", "correct", "appropriate", "MODEL", "客户订单计划对应订单合同管理。"),
    ("零售管培生职能定向生(产研类/技术类/职能类等)", "correct", "appropriate", None, "产研、技术和职能方向粘连。"),
    ("分行营销培训生(零售金融方向)", "correct", "appropriate", "MODEL", "分行零售金融方向可归零售综合银行。"),
    ("纪检", "error", "inappropriate", None, "纪检职责明确但目录未提供承接类别，应标目录缺口。"),
    ("样品管理员", "name_insufficient", "appropriate", None, "样品可能在实验室、制造或仓储，领域不明。"),
    ("市场推广专员(负责在所辖区域有效执行市场推广活动等)", "correct", "appropriate", "MODEL", "名称已明确市场推广活动执行。"),
    ("石家庄分行运营培训生", "correct", "appropriate", "MODEL", "分行运营培训生可由零售综合银行通用承接。"),
]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite existing audit: {OUTPUT}")
    mappings = load(TRIAL / "trial_100_mappings.json")["results"]
    selected = load(TRIAL / "selection_manifest.json")["occupations"]
    taxonomy_rows = load(TAXONOMY)["rows"]
    names = {item["standard_occupation_id"]: item["standard_name"] for item in selected}
    category_ids = {item["category_id"] for item in taxonomy_rows}
    level_2_ids = {item["category_id"].rsplit("/", 1)[0] for item in taxonomy_rows}
    level_1_ids = {item["level_1"] for item in taxonomy_rows}
    allowed = category_ids | level_2_ids | level_1_ids
    if len(mappings) != 100 or len(AUDIT) != 100:
        raise ValueError("Audit and trial must each contain exactly 100 records")
    rows = []
    for ordinal, (model_result, decision) in enumerate(zip(mappings, AUDIT), start=1):
        expected_name, verdict, handling, confirmed, rationale = decision
        occupation_id = model_result["standard_occupation_id"]
        actual_name = names.get(occupation_id)
        if actual_name != expected_name:
            raise ValueError(f"Manual audit row {ordinal} title does not match trial: {actual_name!r}")
        if verdict not in {"correct", "error", "name_insufficient"}:
            raise ValueError(f"Invalid verdict at row {ordinal}")
        if handling not in {"appropriate", "inappropriate"}:
            raise ValueError(f"Invalid handling at row {ordinal}")
        confirmed_id = model_result["target_category_id"] if confirmed == "MODEL" else confirmed
        if confirmed_id is not None and confirmed_id not in allowed:
            raise ValueError(f"Invalid confirmed category at row {ordinal}: {confirmed_id!r}")
        rows.append({
            "ordinal": ordinal,
            "standard_occupation_id": occupation_id,
            "standard_name": actual_name,
            "api_result": model_result,
            "audit_verdict": verdict,
            "model_output_handling": handling,
            "correct_category_id_or_deepest_confirmed": confirmed_id,
            "reason": rationale,
            "audit_scope": "name_only",
        })
    summary = {
        "audit_verdict_counts": dict(Counter(row["audit_verdict"] for row in rows)),
        "model_output_handling_counts": dict(Counter(row["model_output_handling"] for row in rows)),
        "api_status_by_audit_verdict": {
            verdict: dict(Counter(row["api_result"]["status"] for row in rows if row["audit_verdict"] == verdict))
            for verdict in ("correct", "error", "name_insufficient")
        },
    }
    payload = {
        "schema_version": "deepseek-name-classification-trial-manual-semantic-audit-v1",
        "trial_mapping_path": str(TRIAL / "trial_100_mappings.json"),
        "taxonomy_path": str(TAXONOMY),
        "audit_method": "Each of 100 titles was independently reviewed by Codex; no default verdicts or generated templates were used.",
        "input_count": len(rows),
        "summary": summary,
        "rows": rows,
    }
    with OUTPUT.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
