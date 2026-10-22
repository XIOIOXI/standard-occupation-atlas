"""Finalize the contract-200 review without mutating any provider artifact.

Produces a traceable comparison, an adjudicated correction proposal, and a
cost/quality report.  This script deliberately does not call a model/API.
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/record_role_classification_v1/api_trials/deepseek_sno_v31_contract_200"
CATALOG = ROOT / "data/taxonomy/sno_v3_1/sno_occupation_catalog_v3.1.json"
SELECTION = ROOT / "data/processed/record_role_classification_v1/api_trials/sno_v31_200_selection.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(name, value):
    path = OUT / name
    if path.exists():
        raise SystemExit(f"Refusing to overwrite existing derived artifact: {path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def taxonomy_index(catalog):
    by_id, path = {}, {}
    for l1 in catalog["taxonomy"]:
        by_id[l1["level_1_id"]] = {"id": l1["level_1_id"], "name": l1["name"], "level": "level_1", "scope": l1.get("scope")}
        path[l1["level_1_id"]] = [by_id[l1["level_1_id"]]]
        for l2 in l1["level_2"]:
            item = {"id": l2["level_2_id"], "name": l2["name"], "level": "level_2", "scope": l2.get("scope")}
            by_id[item["id"]] = item
            path[item["id"]] = [by_id[l1["level_1_id"]], item]
            for l3 in l2["level_3"]:
                leaf = {"id": l3["level_3_id"], "name": l3["name"], "level": "level_3", "scope": l3.get("scope")}
                by_id[leaf["id"]] = leaf
                path[leaf["id"]] = [by_id[l1["level_1_id"]], item, leaf]
    return by_id, path


def display_path(path):
    return [{k: x.get(k) for k in ("id", "name", "level", "scope")} for x in path] if path else None


def usage(raw):
    value = raw.get("usage", {})
    details = value.get("prompt_tokens_details", {})
    cached = value.get("prompt_cache_hit_tokens", details.get("cached_tokens", 0)) or 0
    prompt = value.get("prompt_tokens", 0) or 0
    return {"input_tokens": prompt, "cached_input_tokens": cached,
            "uncached_input_tokens": max(0, prompt - cached),
            "output_tokens": value.get("completion_tokens", 0) or 0}


def estimate(u):
    # Same documented DeepSeek Flash off-peak rate stored with initial batch cost.
    return u["cached_input_tokens"] * .003 / 1_000_000 + u["uncached_input_tokens"] * .15 / 1_000_000 + u["output_tokens"] * .6 / 1_000_000


def main():
    normalized = load(OUT / "normalized_contract_results.json")
    selection = load(SELECTION)["occupations"]
    titles = {x["standard_occupation_id"]: x["standard_name"] for x in selection}
    reviews = load(OUT / "review_all.json")["results"]
    review_by_id = {x["occupation_id"]: x for x in reviews}
    catalog = load(CATALOG)
    by_id, paths = taxonomy_index(catalog)

    # A clearly contradicted reviewer result is not silently accepted. This is
    # a deterministic directory-scope correction, not a prompt-specific rule.
    manual = {
        "SNO-3350d766577dab09fb5d": {
            "verdict": "correction_required", "suggested_target_category_id": "L02-05", "proposed_status": "mapped",
            "issue": "“超声信号处理算法”排除 L02-05-03 的语音/音频细分，但标题没有预测或统计学习证据；回退至算法研发二级 L02-05。", "basis": "directory_scope_adjudication"},
        "SNO-a7d3e79a496e5c4850b0": {
            "verdict": "correction_required", "suggested_target_category_id": "L26-04", "proposed_status": "mapped",
            "issue": "“兽医师助理”没有伴侣或生产动物证据，退至 L26-04 兽医与动物医疗二级。", "basis": "directory_scope_adjudication"},
        "SNO-6f0b61c2a8aa884ad401": {
            "verdict": "unresolved", "suggested_target_category_id": None, "proposed_status": "review",
            "issue": "“多媒体工程师”不能从标题确定剪辑后期、内容制作或系统技术方向；撤销过细的 L15-06，保留待复核。", "basis": "avoid_misclassification_adjudication"},
        "SNO-a38c7e2de09fbe6cb5ec": {
            "verdict": "unresolved", "suggested_target_category_id": None, "proposed_status": "review",
            "issue": "“铁路电务操作技能”不足以确认目录中“轨道驾驶与专业操作”的具体职业身份；撤销三级，保留待复核。", "basis": "avoid_misclassification_adjudication"},
        "SNO-cc125b61530a02724f63": {
            "verdict": "unresolved", "suggested_target_category_id": None, "proposed_status": "review",
            "issue": "“无人系统总体设计”未给出无人机、车辆或其他装备类型；不能确定整车装备集成或通用研发，保留待复核。", "basis": "avoid_misclassification_adjudication"},
        "SNO-3c4d285367a397cfde25": {
            "verdict": "taxonomy_issue", "suggested_target_category_id": None, "proposed_status": "review",
            "issue": "药品注册事务不等于知识产权；现有目录未见直接的药品注册/法规事务类别。撤销 L30-04-02，作为目录缺口待审。", "basis": "directory_scope_adjudication"},
        "SNO-372c9815ce356b008ddf": {
            "verdict": "unresolved", "suggested_target_category_id": None, "proposed_status": "review",
            "issue": "“私人投资顾问”不足以区分市场研究、资产管理、财富顾问或销售服务；撤销 L20-02-01，保留待复核。", "basis": "avoid_misclassification_adjudication"},
        "SNO-3dd73911e09235373671": {
            "verdict": "correction_required",
            "suggested_target_category_id": "L09-04",
            "issue": "标题中的“珠宝”直接对应 L09-04 范围“服装、首饰、配饰与纺织图案设计”；L09-03 仅覆盖实体产品外观、造型、人机与工业设计。应改为 L09-04，且标题不足以支持三级。",
            "basis": "directory_scope_adjudication",
            "supersedes_reviewer_verdict": "pass",
        },
        "SNO-e24d1e9d58fed3885451": {
            "verdict": "unresolved", "suggested_target_category_id": None, "proposed_status": "review",
            "issue": "“阵列前端设计师”不能仅凭“前端”认定 Web 前端，亦不能把阵列推断为某个硬件方向；撤销 Web 三级，保留待复核。", "basis": "avoid_misclassification_adjudication"},
        "SNO-6bbb262fcc9a1361569b": {
            "verdict": "unresolved", "suggested_target_category_id": None, "proposed_status": "review",
            "issue": "“自动驾驶车辆调试工程师”表明调试职能，但不足以在工业安装调试和产品测试间唯一确定；撤销既有三级，保留待复核。", "basis": "avoid_misclassification_adjudication"},
    }

    comparison, proposed = [], []
    for initial in normalized["results"]:
        oid = initial["occupation_id"]
        reviewer = review_by_id.get(oid)
        adjudication = manual.get(oid)
        effective = adjudication or reviewer or {"verdict": "unresolved", "suggested_target_category_id": None, "issue": "missing review row"}
        current = initial.get("target_category_id")
        suggested = effective.get("suggested_target_category_id")
        if adjudication and adjudication.get("proposed_status") == "review":
            target, status = None, "review"
        else:
            target = suggested if effective.get("verdict") == "correction_required" and suggested in by_id else current
            status = "mapped" if target else ("review" if effective.get("verdict") in {"unresolved", "taxonomy_issue"} else initial["status"])
        row = {
            "occupation_id": oid, "title": titles.get(oid),
            "initial_normalized_result": initial,
            "initial_target_path": display_path(paths.get(current)),
            "model_review": reviewer,
            "adjudication": adjudication,
            "effective_review": effective,
            "proposed_result": {
                "status": status, "target_category_id": target,
                "target_level": by_id[target]["level"] if target else None,
                "target_path": display_path(paths.get(target)),
                "change_reason": effective.get("issue") if target != current or status != initial["status"] else None,
            },
            "changed": target != current or status != initial["status"],
        }
        comparison.append(row)
        proposed.append({"occupation_id": oid, "title": titles.get(oid), **row["proposed_result"]})

    map_parsed = [load(OUT / f"map_{n:03d}_parsed.json") for n in range(1, 11)]
    map_cost = sum(x["cost"]["estimated_usd"] for x in map_parsed)
    map_usage = Counter()
    for x in map_parsed:
        map_usage.update(x["usage"])
    review_files = [load(OUT / f"review_{n:03d}.json") for n in range(1, 11)]
    review_usage = Counter()
    for x in review_files:
        review_usage.update(usage(x["raw"]))
    review_cost = estimate(review_usage)
    verdicts = Counter(x["verdict"] for x in review_by_id.values())
    effective_verdicts = Counter((manual.get(x["occupation_id"]) or x).get("verdict") for x in reviews)
    statuses = Counter(x["status"] for x in normalized["results"])
    initial_levels = Counter(x["target_level"] or "none" for x in normalized["results"])

    report = {
        "run": {"taxonomy_version": catalog["taxonomy_version"], "sample_count": len(comparison), "api_calls_made_by_this_finalizer": 0},
        "artifact_integrity": {
            "mapping_batches": 10, "review_batches": 10,
            "initial_rows": len(normalized["results"]), "review_rows": len(reviews),
            "review_rows_missing": [x["occupation_id"] for x in normalized["results"] if x["occupation_id"] not in review_by_id],
            "raw_contract_strict_valid": normalized.get("raw_strict_valid"),
            "normalization_changes": normalized.get("normalization_changes"),
            "normalized_contract_valid": normalized.get("normalized_valid_count"),
        },
        "initial_mapping_counts": {"status": statuses, "target_level": initial_levels},
        "review_counts": {"raw_model": verdicts, "effective_after_directory_scope_adjudication": effective_verdicts,
                          "changed_proposals": sum(1 for x in comparison if x["changed"])},
        "jewelry_design_engineer": next(x for x in comparison if x["occupation_id"] == "SNO-3dd73911e09235373671"),
        "similar_obvious_misclassification_search": {
            "method": "reviewed all initially selected L09-03 records against their title evidence and the L09-03/L09-04 scopes.",
            "initial_L09_03_records": [x["title"] for x in comparison if x["initial_normalized_result"].get("target_category_id") == "L09-03"],
            "additional_clear_L09_04_corrections": 0,
            "conclusion": "Only 珠宝设计工程师 has direct 首饰/珠宝 evidence conflicting with L09-03 in this set; 内/外饰设计 remains compatible with L09-03.",
        },
        "cost": {
            "basis": "API-reported token usage multiplied by the saved DeepSeek Flash off-peak rates; DeepSeek response does not provide billed currency.",
            "rates_usd_per_million_tokens": {"cached_input": .003, "uncached_input": .15, "output": .6},
            "initial_mapping": {"usage": dict(map_usage), "estimated_usd": round(map_cost, 9), "calls": 10, "recorded_retries": 0},
            "review": {"usage": dict(review_usage), "estimated_usd": round(review_cost, 9), "calls": 10, "recorded_retries": "not recorded by prior review runner"},
            "cumulative_estimated_usd": round(map_cost + review_cost, 9),
            "budget_usd": 1.0,
            "within_budget": map_cost + review_cost <= 1,
        },
        "limitations": [
            "pass means the same-model review did not identify a clear problem; it is not an accuracy guarantee.",
            "The historical reviewer prompt included the full directory but did not explicitly inject sibling alternatives per record; its false pass on 珠宝设计工程师 demonstrates that limitation.",
            "The correction proposal is a separate derived artifact. Provider raw responses and normalized initial results are preserved unchanged.",
        ],
    }
    dump("reviewed_comparison_200_adjudicated_v2.json", {"count": len(comparison), "records": comparison})
    dump("corrected_result_proposals_200_adjudicated_v2.json", {"count": len(proposed), "results": proposed,
                                             "note": "Derived proposals only; not a replacement for raw or normalized provider output."})
    dump("contract_200_final_report_adjudicated_v2.json", report)
    print(json.dumps({"rows": len(comparison), "changes": report["review_counts"]["changed_proposals"], "cost": report["cost"]["cumulative_estimated_usd"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
