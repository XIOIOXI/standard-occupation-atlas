"""Persist an independent, title-only semantic audit of DeepSeek trial v3."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path("data/processed/record_role_classification_v1")
TRIAL = ROOT / "api_trials" / "deepseek_name_classification_trial_v3"
TAXONOMY = ROOT / "catalog_mappings" / "taxonomy_embedding_texts_v1.json"
OUTPUT = TRIAL / "manual_semantic_audit_100.json"

# Explicit manual decisions, entered after separately reading every v3 model
# response.  MODEL retains a semantically adequate model target; None means no
# defensible deepest taxonomy placement can be confirmed from the title alone.
AUDIT = [
    ("通信网络运维工程师", "correct", "appropriate", "MODEL", "通信网络运维直接承接通信网络维护。"),
    ("CPUIP验证工程师", "correct", "appropriate", "MODEL", "CPU IP验证属于芯片验证。"),
    ("市场职能", "name_insufficient", "appropriate", None, "市场职能未说明具体职责。"),
    ("会计专员", "correct", "appropriate", "MODEL", "会计专员可由通用财务核算承接。"),
    ("分两个批次开展招聘。第一批次为省市局(公司)机关相关", "name_insufficient", "appropriate", None, "招聘说明而非职业名称。"),
    ("外科医师", "correct", "appropriate", "MODEL", "外科医师属于临床诊疗。"),
    ("电气工程师(交付技术)", "correct", "appropriate", "MODEL", "交付技术与现场调试是可接受的电气自动化承接。"),
    ("客服培训生", "correct", "appropriate", "MODEL", "客服是核心职责，培训生不改变职业。"),
    ("初级DQE工程师(电气)", "correct", "appropriate", "MODEL", "DQE属于质量控制。"),
    ("2026年浙江省新昌中学第三轮计划招聘教师6名(语文2人、英语1人、物理1人、化学1人、地理1人)", "correct", "appropriate", "MODEL", "各项均为中学教师，可由基础教育教学统一承接。"),
    ("燃烧室设计", "correct", "appropriate", "MODEL", "核心职责是机械结构设计。"),
    ("车辆控制工程师", "correct", "appropriate", "MODEL", "车辆控制属于汽车研发。"),
    ("数字化仿真应用工程师", "name_insufficient", "inappropriate", None, "仿真对象和工程领域缺失，不能推定机械设计。"),
    ("国际贸易经理", "correct", "appropriate", "MODEL", "国际贸易经理可归国际市场客户开发。"),
    ("设备技术员", "correct", "appropriate", "MODEL", "设备技术员可由设备维修安装承接。"),
    ("动力总成研发工程师", "correct", "appropriate", "MODEL", "动力总成研发属于汽车研发。"),
    ("总装工艺员", "name_insufficient", "inappropriate", "生产制造", "总装不必然是汽车，名称只能确认制造工艺领域。"),
    ("安全研究工程师", "name_insufficient", "inappropriate", None, "安全不必然是网络安全，领域缺失。"),
    ("社媒运营(日语)", "correct", "appropriate", "MODEL", "日语为语言限定，核心是社媒运营。"),
    ("电气类管培生", "name_insufficient", "inappropriate", "电子/电气/通信", "只能确认电气领域，不能推定自动化设计。"),
    ("专区运营", "name_insufficient", "inappropriate", "运营/客服", "专区含义不足以细分业务流程。"),
    ("供应链解决方案工程师", "name_insufficient", "inappropriate", "供应链/物流/supply-chain", "供应链解决方案不等同计划采购协同。"),
    ("算法工程师(安全方向)", "correct", "appropriate", "MODEL", "算法职责明确，安全方向不妨碍通用算法承接。"),
    ("国内业务管理专员", "name_insufficient", "inappropriate", None, "国内业务管理不等于业务流程运营。"),
    ("结构材料工程师", "error", "inappropriate", None, "材料工程职责明确而目录无材料研发承接，应标目录缺口。"),
    ("初中物理教师", "correct", "appropriate", "MODEL", "基础教育教学明确。"),
    ("材料基因工程师", "correct", "appropriate", None, "材料研发职业明确，目录无对应类别。"),
    ("环境可靠性工程师", "correct", "appropriate", "MODEL", "环境可靠性可由质量检验与过程控制通用承接。"),
    ("市场综合监管辅助员", "error", "inappropriate", None, "市场监管辅助职责可识别但目录无清晰承接，应标目录缺口。"),
    ("教育服务助理", "correct", "appropriate", "MODEL", "教育机构行政是合理承接。"),
    ("社媒运营经理(海外-西葡)", "correct", "appropriate", "MODEL", "语言市场限定不改变社媒运营。"),
    ("软体家具质检Qc管培生", "correct", "appropriate", "MODEL", "质检QC核心明确。"),
    ("电源设计工程师", "correct", "appropriate", "MODEL", "电源设计属于电路硬件设计。"),
    ("内贸业务", "name_insufficient", "inappropriate", "采购/贸易", "内贸业务不能直接推定客户开发直销。"),
    ("工艺实验室培训生", "name_insufficient", "inappropriate", None, "工艺实验室不表示化工行业。"),
    ("训练推理优化算法工程师", "correct", "appropriate", "MODEL", "训练与推理优化可归深度学习模型训练。"),
    ("AI游戏内容运营", "error", "inappropriate", "运营/客服/ops-content", "游戏内容运营不等同短视频直播内容。"),
    ("AI推理工程师", "correct", "appropriate", "MODEL", "AI推理工程可归机器学习工程平台。"),
    ("系统建设运维及数据管理", "error", "inappropriate", None, "运维和数据管理是并列核心职责，应标多岗位。"),
    ("宏观研究员", "error", "inappropriate", "金融/financial-securities/securities-research", "宏观研究不等同市场社会调研，证券研究是更合理承接。"),
    ("公司本部法务", "correct", "appropriate", "MODEL", "公司法务与合规明确。"),
    ("工艺设备", "correct", "appropriate", "MODEL", "机械制造与工艺是可接受的通用承接。"),
    ("零售金融市场营销岗(成都)", "correct", "appropriate", "MODEL", "零售金融营销可合理归金融销售财富方向。"),
    ("市场营销员", "name_insufficient", "inappropriate", "市场/公关/广告", "营销员没有品牌策略细分证据。"),
    ("质量技术师", "correct", "appropriate", "MODEL", "质量技术职责可归质量控制。"),
    ("管理类管培生(财务管理、项目管理方向)", "correct", "appropriate", None, "两个独立培养方向并列。"),
    ("测试", "name_insufficient", "inappropriate", None, "测试未说明软件或行业，不能判功能自动化测试。"),
    ("医生", "correct", "appropriate", "MODEL", "临床诊疗是医生的通用承接。"),
    ("投后管理", "correct", "appropriate", "MODEL", "投后管理可归股权投资管理。"),
    ("/ERBP研发人员", "name_insufficient", "appropriate", None, "缩写含义和研发方向不明。"),
    ("媒介助理", "correct", "appropriate", "MODEL", "媒介关系投放支持明确。"),
    ("机务工程师(南京)", "name_insufficient", "appropriate", None, "机务所属行业不明。"),
    ("管培生专项计划", "name_insufficient", "appropriate", None, "计划未表达职业职责。"),
    ("业务管理", "name_insufficient", "inappropriate", None, "业务管理过宽，不能直接归流程运营。"),
    ("创意设计师", "correct", "appropriate", "MODEL", "品牌与视觉设计是合理承接。"),
    ("线上运营主管", "name_insufficient", "inappropriate", "运营/客服", "线上运营不能归线下门店运营。"),
    ("智能制造专员", "name_insufficient", "inappropriate", "生产制造", "智能制造不足以确认精益改善职责。"),
    ("助理软件工程师", "name_insufficient", "inappropriate", "互联网/AI", "软件工程师不能默认后端。"),
    ("国产CADCAM软件开发工程师(参与国产CAD/CAM软件核心模块设计开发等)", "name_insufficient", "inappropriate", "互联网/AI", "名称没有C++语言证据，不能归C++图形计算。"),
    ("计划控制工程师", "name_insufficient", "inappropriate", None, "计划控制也可为项目工程，行业未体现。"),
    ("风控创优生", "name_insufficient", "inappropriate", None, "风控领域未明确，不能限定信用业务风险。"),
    ("算法集成工程师", "correct", "appropriate", "MODEL", "算法工程可由通用算法研究承接。"),
    ("光学算法工程师", "correct", "appropriate", "MODEL", "光学算法可合理归视觉三维感知。"),
    ("DFT可测性设计工程师", "error", "inappropriate", "电子/电气/通信/electronic-semiconductor/chip-verification", "DFT逻辑可测性设计更接近芯片验证，不是封装。"),
    ("检测员", "correct", "appropriate", "MODEL", "质量检验与过程控制是合理通用承接。"),
    ("股权融资及财务顾问", "correct", "appropriate", "MODEL", "交易融资顾问直接承接。"),
    ("专业课教师", "name_insufficient", "inappropriate", "教育培训", "未说明职业教育或高等教育，不能直接归职业技能教学。"),
    ("硬件研发工程师", "correct", "appropriate", "MODEL", "电路硬件设计是合理通用承接。"),
    ("总经办总裁助理", "name_insufficient", "appropriate", "人力/行政/法务", "可确认行政支持，模型以review保留不确定性。"),
    ("管培生岗位(研发、职能、商业化、生产&供应链)", "correct", "appropriate", None, "多个培养方向明确并列。"),
    ("证券事务经理", "error", "inappropriate", "金融/financial-securities", "证券事务并非基金期货交易运营。"),
    ("教学科研岗(政治学理论、中共党史、社会学、马克思主义中国化研究、思想政治教育、基础心理学、发展与教育心理学、应用心理学)", "correct", "appropriate", "MODEL", "教学科研岗位可由高等教育教学统一承接。"),
    ("岗理财经理", "correct", "appropriate", "MODEL", "“岗”是冗余前缀，理财经理明确。"),
    ("人力资源储备", "name_insufficient", "inappropriate", "人力/行政/法务/people-hr", "人力资源储备不能推定员工关系方向。"),
    ("基础设施互联互通促进中心专技", "name_insufficient", "appropriate", None, "组织名称和专技不足以说明职业。"),
    ("私人教练团课全职/兼职教练职能/技术", "correct", "appropriate", "MODEL", "全职兼职与团课是健身教练的修饰而非独立职业。"),
    ("油气储运与新能源开发", "correct", "appropriate", "MODEL", "均属能源开发工程范围，可由能源工程统一承接。"),
    ("财务内控", "correct", "appropriate", "MODEL", "内部控制与内审明确。"),
    ("算法工程师(媒体算法)", "error", "inappropriate", "互联网/AI/internet-algorithm", "媒体不等于语音音频，不能确定该三级。"),
    ("工程", "name_insufficient", "appropriate", None, "工程一词没有领域。"),
    ("新闻宣传", "error", "inappropriate", "市场/公关/广告/marketing-pr/pr-media-public-relations", "新闻宣传不必然是新媒体新闻传播。"),
    ("检测技术等", "name_insufficient", "appropriate", None, "名称不完整且领域不明。"),
    ("生产调度工程师", "correct", "appropriate", "MODEL", "生产调度直接对应生产计划调度。"),
    ("生产制造员", "correct", "appropriate", "MODEL", "生产线作业是合理通用承接。"),
    ("售后助理", "name_insufficient", "appropriate", None, "售后可指客服、维修或商务。"),
    ("法律事务相关", "correct", "appropriate", "MODEL", "公司法务合规是可接受的法律事务承接。"),
    ("法务风控岗", "correct", "appropriate", None, "法务与风控是两个独立职业方向。"),
    ("方案解决高级工程师", "name_insufficient", "appropriate", None, "技术领域不明。"),
    ("文案实习生(德语/英语)", "correct", "appropriate", "MODEL", "语言是能力限定，核心是文案。"),
    ("企管法规", "correct", "appropriate", "MODEL", "企业法规合规可由公司法务合规承接。"),
    ("化工外贸业务员", "correct", "appropriate", "MODEL", "化工是产品方向，核心为外贸销售。"),
    ("支撑", "name_insufficient", "appropriate", None, "名称没有职业职责。"),
    ("机器人系统开发工程师", "error", "inappropriate", "互联网/AI", "机器人系统开发不必然是算法岗位。"),
    ("客户订单计划员", "correct", "appropriate", "MODEL", "订单计划与供应链计划协同合理。"),
    ("零售管培生职能定向生(产研类/技术类/职能类等)", "correct", "appropriate", None, "多个独立培养方向。"),
    ("分行营销培训生(零售金融方向)", "correct", "appropriate", "MODEL", "零售金融营销可由金融销售财富方向承接。"),
    ("纪检", "correct", "appropriate", None, "纪检职能明确但目录没有承接类别。"),
    ("样品管理员", "name_insufficient", "inappropriate", None, "样品管理所在行业和职责范围不明。"),
    ("市场推广专员(负责在所辖区域有效执行市场推广活动等)", "correct", "appropriate", "MODEL", "市场推广活动执行直接对应渠道营销活动。"),
    ("石家庄分行运营培训生", "correct", "appropriate", "MODEL", "分行运营可由零售综合银行通用承接。"),
]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite existing audit: {OUTPUT}")
    mappings = load(TRIAL / "trial_100_mappings.json")["results"]
    selected = load(TRIAL / "selection_manifest.json")["occupations"]
    tax = load(TAXONOMY)["rows"]
    names = {row["standard_occupation_id"]: row["standard_name"] for row in selected}
    l3 = {row["category_id"] for row in tax}
    l2 = {row["category_id"].rsplit("/", 1)[0] for row in tax}
    l1 = {row["level_1"] for row in tax}
    allowed = l1 | l2 | l3
    if len(mappings) != 100 or len(AUDIT) != 100:
        raise ValueError("Audit and mappings must both contain exactly 100 entries")
    rows = []
    for ordinal, (model, decision) in enumerate(zip(mappings, AUDIT), 1):
        expected_name, verdict, handling, expected_target, reason = decision
        occupation_id = model["occupation_id"]
        if names.get(occupation_id) != expected_name:
            raise ValueError(f"Manual row {ordinal} does not match v3 selection")
        target = model["target_category_id"] if expected_target == "MODEL" else expected_target
        if verdict not in {"correct", "error", "name_insufficient"} or handling not in {"appropriate", "inappropriate"}:
            raise ValueError(f"Invalid manual decision at {ordinal}")
        if target is not None and target not in allowed:
            raise ValueError(f"Invalid confirmed target at {ordinal}: {target}")
        rows.append({
            "ordinal": ordinal,
            "occupation_id": occupation_id,
            "occupation_name": expected_name,
            "api_result": model,
            "audit_verdict": verdict,
            "model_output_handling": handling,
            "correct_category_id_or_deepest_confirmed": target,
            "reason": reason,
            "audit_scope": "name_only; independently reviewed after v3 response",
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
        "schema_version": "deepseek-name-classification-trial-v3-manual-semantic-audit-v1",
        "audit_method": "Every title was independently read against the v3 API output and frozen taxonomy; no v2 verdict was copied as a default.",
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
