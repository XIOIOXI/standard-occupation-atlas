"""Create the independent title-only audit for the SNO v3 100-name trial."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRIAL = ROOT / "data/processed/record_role_classification_v1/api_trials/deepseek_sno_v3_directory_trial_100"
CATALOG = ROOT / "data/taxonomy/sno_v3/sno_occupation_catalog_v3.json"
AUDIT = TRIAL / "semantic_audit_100.json"
REPORT = ROOT / "docs/reports/deepseek-sno-v3-directory-trial-100.md"

# Only decisions that fail the v3 title-only rule are listed.  Every other
# result was independently checked for a compatible status and primary path.
# A review status can be safe even when its tentative candidate is not useful;
# that distinction is reported separately below.
CORRECTIONS = {
    "SNO-ddfc61f055c9d52b6b4c": ("incorrect_status", "招聘公告文本，应为 non_role_text，不能按学科教师 multi_role 处理。"),
    "SNO-96d890047d86358d7739": ("incorrect_primary", "动力总成是车辆专业研发语境；不应优先落入热流体与动力工程。"),
    "SNO-1f45fd778a1c2fee3330": ("overclassified", "“安全研究”未说明网络攻防、漏洞或技术安全治理，应 review。"),
    "SNO-eb279b03901806c234c1": ("incorrect_primary", "电气方向已明确；培养是角色标签，不能替代为 L32 跨职能培养。"),
    "SNO-d92d4a0afc2c7e920354": ("overclassified", "“专区运营”没有数字产品或平台证据，应 review。"),
    "SNO-5f43b78cf7549e2ea3a4": ("incorrect_primary", "算法是核心职责；安全为领域限定，应优先 L02 而不是 L03。"),
    "SNO-27e63eba60eb4d40d1ac": ("incorrect_primary", "结构材料工程师应优先材料研发或 review，不能直接等同机械结构设计。"),
    "SNO-a47b055ca7ccc6f1a475": ("overclassified", "“质检”未给出客诉职责，不能细分为产品质量与客诉管理。"),
    "SNO-0ec7605e63aece2ec4af": ("unsafe_review_candidate", "ERBP 含义不足；review 正确，但候选 L01 通用软件研发没有名称依据。"),
    "SNO-be992e432c8abf4f0cc3": ("overclassified", "线上运营未说明产品/平台对象，应停在运营通用或 review。"),
    "SNO-f695c0780e0d47200402": ("overclassified", "光学算法不必然是计算机视觉；名称不足时应停在算法二级。"),
    "SNO-2c46ed9676c2ed0f87ee": ("incorrect_primary", "理财经理以客户顾问成交为核心时应归 L13 个人客户销售，不是金融后台运营。"),
    "SNO-1ee6e8b56f32b3181ae8": ("overclassified", "媒体算法不必然为视觉算法，缺少图像/视频职责时应停在算法二级。"),
    "SNO-1080766dda240d9f40f4": ("overclassified", "售后助理未证明安装、调试或技术服务，不能直接归 L14-10。"),
    "SNO-60a6932da8bc0fb9a9cb": ("overclassified", "机器人系统开发未证明设备端/嵌入式，应归通用软件研发或 review。"),
    "SNO-117dba594b0d6e53eb1d": ("incorrect_primary", "零售金融营销方向已明确；培养是标签，应归销售或保留二级，不是 L32。"),
    "SNO-2796afcf7a07b87d58c6": ("incorrect_primary", "样品管理员的实验/检测上下文不明，不能直接推为档案与资料管理。"),
    "SNO-435aa6a2a3ed64664fa6": ("incorrect_primary", "分行运营方向已明确；培训生是标签，应归 L20 金融运营而不是 L32。"),
}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    if AUDIT.exists() or REPORT.exists():
        raise FileExistsError("Refusing to overwrite the v3 trial audit")
    selection = load(TRIAL / "selection_manifest.json")["occupations"]
    results = {row["occupation_id"]: row for row in load(TRIAL / "trial_100_mappings.json")["results"]}
    catalog = load(CATALOG)
    rows = []
    for item in selection:
        result = results[item["occupation_id"]]
        finding = CORRECTIONS.get(item["occupation_id"])
        rows.append({
            "occupation_id": item["occupation_id"],
            "occupation_name": item["occupation_name"],
            "model_status": result["status"],
            "model_target_category_id": result["target_category_id"],
            "audit_verdict": "correction_required" if finding else "accepted_title_only",
            "finding_type": finding[0] if finding else None,
            "audit_note": finding[1] if finding else "标题证据支持当前状态与主归属粒度；不把它视为已完成生产映射。",
        })
    mapped = [row for row in rows if row["model_status"] == "mapped"]
    mapped_corrections = [row for row in mapped if row["audit_verdict"] == "correction_required"]
    safe_status_corrections = [row for row in rows if row["finding_type"] != "unsafe_review_candidate" and row["audit_verdict"] == "correction_required"]
    summary = {
        "sample_size": len(rows),
        "strict_title_only_accepted": sum(row["audit_verdict"] == "accepted_title_only" for row in rows),
        "strict_title_only_accuracy": round(sum(row["audit_verdict"] == "accepted_title_only" for row in rows) / len(rows), 4),
        "mapped_count": len(mapped),
        "mapped_primary_precision": round((len(mapped) - len(mapped_corrections)) / len(mapped), 4),
        "safe_status_count": len(rows) - len(safe_status_corrections),
        "safe_status_rate": round((len(rows) - len(safe_status_corrections)) / len(rows), 4),
        "finding_counts": dict(sorted(Counter(row["finding_type"] for row in rows if row["finding_type"]).items())),
        "gate": "do_not_start_formal_mapping",
        "gate_reason": "The pilot still over-classifies title-only cases and mishandles training labels. Revise prompt and re-test before any production mapping.",
    }
    payload = {
        "schema_version": "deepseek-sno-v3-trial-semantic-audit-v1",
        "scope": "Independent title-only review of the fixed 100-name directory-validation sample. This is not an accuracy estimate for all recruitment records.",
        "taxonomy_version": catalog["taxonomy_version"],
        "audit_rules": ["core responsibility over industry/technology", "training and seniority are tags", "do not force ambiguous titles", "one level-2 primary placement"],
        "summary": summary,
        "rows": rows,
    }
    AUDIT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text("\n".join([
        "# DeepSeek SNO v3 100 条目录试映射",
        "",
        "## 结论",
        "",
        "**暂不进入正式映射。** 该试验仅验证标题级分类，且仍出现过度细分、将培养标签当作职业主归属、以及跨一级误分的问题。",
        "",
        "## 结果",
        "",
        f"- 样本：{summary['sample_size']} 个上一轮固定 SNO 名称；不含公司、行业、招聘正文或原始记录 ID。",
        f"- 严格标题级正确率：{summary['strict_title_only_accepted']}/{summary['sample_size']}（{summary['strict_title_only_accuracy']:.1%}）。",
        f"- 已输出 mapped 的主归属精度：{summary['mapped_count'] - len(mapped_corrections)}/{summary['mapped_count']}（{summary['mapped_primary_precision']:.1%}）。",
        f"- API 的安全状态率：{summary['safe_status_count']}/{summary['sample_size']}（{summary['safe_status_rate']:.1%}）；其中一条 review 的候选归属不安全，未计入严格正确率。",
        "",
        "## 主要错误模式",
        "",
        "- 过度细分：仅凭“专区运营”“光学算法”“售后助理”等名称猜测工作对象或技术场景。",
        "- 培养标签抢占主归属：电气类、银行运营或金融营销管培生被归入 L32，而不是已明确的专业职能。",
        "- 核心职责错位：安全方向算法应优先算法研发；理财经理应优先客户销售。",
        "",
        "下一轮应修改 prompt：把“名称不足时宁可 review”设为最高优先级，并显式禁止把 `管培生/培训生/储备` 当作 L32 的充分条件。",
        "",
    ]), encoding="utf-8")
    print(json.dumps({"audit": str(AUDIT.relative_to(ROOT)), "report": str(REPORT.relative_to(ROOT)), "summary": summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
