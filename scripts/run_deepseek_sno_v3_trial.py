"""Run a non-destructive 100-name DeepSeek trial against the SNO v3 directory.

The input is the fixed 100-name holdout used in the preceding SNO experiment.
It is a directory-validation sample, not a production migration: results are
saved separately and cannot alter recruitment records or old display mappings.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from run_deepseek_name_classification_trial_v1 import (
    api_post_retry, canonical_base_url, estimate_cost, exclusive_json,
    output_content, read_dotenv, read_json, response_metadata, sha256_file,
    usage_summary,
)


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / os.environ.get("SNO_V3_CATALOG", "data/taxonomy/sno_v3_1/sno_occupation_catalog_v3.1.json")
PRIOR_SELECTION = ROOT / "data/processed/record_role_classification_v1/api_trials/deepseek_name_classification_trial_v3/selection_manifest.json"
OUT = ROOT / "data/processed/record_role_classification_v1/api_trials" / os.environ.get("SNO_V3_TRIAL_OUTPUT", "deepseek_sno_v3_directory_trial_100_v2_fixed")
TRIAL_SIZE = int(os.environ.get("SNO_V3_TRIAL_SIZE", "100"))
BATCH_SIZE = 20
USD_BUDGET = 1.0
STATUSES = {"mapped", "review", "taxonomy_gap", "multi_role", "non_role_text"}


def compact_directory(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    return [{
        "id": l1["level_1_id"], "name": l1["name"],
        "level_2": [{
            "id": l2["level_2_id"], "name": l2["name"], "scope": l2["scope"],
            "level_3": [{"id": l3["level_3_id"], "name": l3["name"], "scope": l3["scope"]} for l3 in l2["level_3"]],
        } for l2 in l1["level_2"]],
    } for l1 in catalog["taxonomy"]]


def allowed_ids(catalog: dict[str, Any]) -> tuple[set[str], set[str], set[str]]:
    l1 = {item["level_1_id"] for item in catalog["taxonomy"]}
    l2 = {item["level_2_id"] for item in catalog["taxonomy"] for item in item["level_2"]}
    l3 = {item["level_3_id"] for item in catalog["taxonomy"] for item in item["level_2"] for item in item["level_3"]}
    return l1, l2, l3


def messages(directory: list[dict[str, Any]], batch: list[dict[str, str]]) -> list[dict[str, str]]:
    system = """你是 SNO v3 职业目录的测试分类器。只依据本次提供的岗位标题和下方目录分类，不能使用公司、行业、地点、学历、技能、外部资料或自行补充招聘职责。
规则：
1. 必须按顺序：先识别标题明确表达的核心职业职能，再选二级，最后才判断三级证据。不能因某个三级名称相似而跨一级或跨二级归类。
2. 每个岗位最多一个二级主归属，一级只能由二级推导。行业、语言、工具、资历、培养身份不能替代核心职能。
3. 二级明确而三级证据不足时，mapped 且 target_category_id 使用二级 ID；三级必须属于该二级。一级明确但方向不明时，只可使用该一级定义的通用二级。实质歧义用 review，target_category_id 可为最深候选或 null，并说明缺少什么证据。不能为提高映射率猜测，也不能把已明确岗位一律 review。
4. 管培生、培训生、储备、实习、助理、经理不是独立职业。专业方向已明确时归该专业，培养身份只作为标签；仅真实培养项目且最终方向未明确才归 L32，不得推断一定跨职能轮岗。仅行业或领域（银行、绿色金融、农化）不足以确定职能，应 review；仅有实习生/校招生身份且无职业信息时 review。
5. 示例边界：光学算法、GNSS算法可到算法研发二级但不能猜具体三级；安全算法先判断算法核心；售后助理不能推断技术安装维修；专区运营不能推断对象；新零售销售不能推断现场销售；助理兽医不能推断伴侣动物；研发测试应到通用测试与质量工作；解决方案工程师不能自动等同售前；行李员不能自动推断交通场景。
6. 明显不是岗位名称时 status=non_role_text 且 target_category_id=null。职业明确而目录确实没有范围时 taxonomy_gap。明确含多个独立岗位时 multi_role。所有 ID 必须逐字来自目录。
7. reason 必须引用标题中的具体词；若没有继续到三级，要说明标题缺少的具体信息。不得把推测写成事实。
只输出合法 JSON：{"results":[{"occupation_id":string,"status":"mapped|review|taxonomy_gap|multi_role|non_role_text","target_category_id":string或null,"reason":string}]}。reason 不超过80字。
目录：""" + json.dumps(directory, ensure_ascii=False, separators=(",", ":"))
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps({"occupations": batch}, ensure_ascii=False, separators=(",", ":"))},
    ]


def body(model: str, prompt: list[dict[str, str]]) -> dict[str, Any]:
    return {"model": model, "messages": prompt, "temperature": 0, "max_tokens": 4000, "response_format": {"type": "json_object"}, "thinking": {"type": "disabled"}, "stream": False}


def validate(raw: Any, batch: list[dict[str, str]], catalog: dict[str, Any]) -> list[dict[str, Any]]:
    results = raw.get("results") if isinstance(raw, dict) else None
    expected = {item["occupation_id"] for item in batch}
    if not isinstance(results, list) or len(results) != len(expected) or {item.get("occupation_id") for item in results if isinstance(item, dict)} != expected:
        raise ValueError("results must return each requested occupation_id exactly once")
    l1, l2, l3 = allowed_ids(catalog)
    allowed = l1 | l2 | l3
    output = []
    for item in results:
        if set(item) != {"occupation_id", "status", "target_category_id", "reason"}:
            raise ValueError("result fields do not match the contract")
        status, target, reason = item["status"], item["target_category_id"], item["reason"]
        if status not in STATUSES or not isinstance(reason, str) or not reason.strip() or len(reason) > 80:
            raise ValueError("invalid status or reason")
        if target is not None and target not in allowed:
            raise ValueError(f"unknown category ID: {target!r}")
        if status == "mapped" and target not in l2 | l3:
            raise ValueError("mapped must select an L2 or L3 ID")
        if status in {"taxonomy_gap", "multi_role", "non_role_text"} and target is not None:
            raise ValueError(f"{status} must not claim a primary category")
        output.append({"occupation_id": item["occupation_id"], "status": status, "target_category_id": target, "reason": reason.strip()})
    return output


def main() -> None:
    selection_source = Path(os.environ.get("SNO_V3_SELECTION_FILE", str(PRIOR_SELECTION)))
    catalog, selection = read_json(CATALOG), read_json(selection_source)
    if catalog["taxonomy_version"] not in {"sno-v3-directory-design", "sno-v3.1-local-revision"}:
        raise ValueError("unexpected SNO catalog")
    selected = [{"occupation_id": item["standard_occupation_id"], "occupation_name": item["standard_name"], "selection_strata": item["selection_strata"]} for item in selection["occupations"]]
    if len(selected) != TRIAL_SIZE or len({item["occupation_id"] for item in selected}) != TRIAL_SIZE:
        raise ValueError("the fixed holdout must contain exactly 100 unique names")
    dotenv = read_dotenv(ROOT / ".env")
    key = os.environ.get("DEEPSEEK_API_KEY") or dotenv.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY") or dotenv.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("No configured DeepSeek credential")
    base = canonical_base_url(os.environ.get("DEEPSEEK_BASE_URL") or dotenv.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com")
    model = os.environ.get("DEEPSEEK_MODEL") or dotenv.get("DEEPSEEK_MODEL") or "deepseek-flash"
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = OUT / "selection_manifest.json"
    if not manifest.exists():
        exclusive_json(manifest, {"schema_version": "deepseek-sno-v3-trial-selection-v1", "scope": "title-only directory validation, not production reclassification", "selection_source": str(selection_source), "catalog": str(CATALOG.relative_to(ROOT)), "catalog_sha256": sha256_file(CATALOG), "occupations": selected})
    directory = compact_directory(catalog)
    completed: list[dict[str, Any]] = []
    all_usage: list[dict[str, int]] = []
    all_costs: list[dict[str, Any]] = []
    for number, start in enumerate(range(0, TRIAL_SIZE, BATCH_SIZE), 1):
        batch = selected[start:start + BATCH_SIZE]
        final = OUT / f"batch_{number:03d}_classified.json"
        if final.exists():
            saved = read_json(final)
            completed.extend(saved["results"])
            all_usage.append(saved["usage"])
            all_costs.append(saved["cost_estimate"])
            continue
        if sum(float(item["estimated_usd"]) for item in all_costs) >= USD_BUDGET:
            raise RuntimeError("trial budget reached before next batch")
        prompt, request = messages(directory, batch), None
        request = body(model, prompt)
        input_path, raw_path = OUT / f"batch_{number:03d}_api_input.json", OUT / f"batch_{number:03d}_api_output.json"
        if not input_path.exists():
            exclusive_json(input_path, {"endpoint": base + "/chat/completions", "model": model, "messages": prompt, "privacy_scope": "title-only: occupation ID and name plus SNO v3 directory; no company, industry, record ID, or recruitment text", "request_sha256": hashlib.sha256(json.dumps(request, ensure_ascii=False, sort_keys=True).encode()).hexdigest()})
        observed = datetime.now(timezone.utc)
        if raw_path.exists():
            raw, attempts = read_json(raw_path), 0
        else:
            raw, attempts = api_post_retry(base, key, request)
        if not raw_path.exists():
            exclusive_json(raw_path, raw)
        decisions = validate(json.loads(output_content(raw)), batch, catalog)
        usage, cost = usage_summary(raw), estimate_cost(usage_summary(raw), observed)
        exclusive_json(final, {"schema_version": "deepseek-sno-v3-trial-batch-v2", "batch_number": number, "model_requested": model, "batch_input_count": len(batch), "attempts": attempts, "validation_retry_count": 0, "response_metadata": response_metadata(raw), "usage": usage, "cost_estimate": cost, "results": decisions})
        completed.extend(decisions)
        all_usage.append(usage)
        all_costs.append(cost)
    expected = {item["occupation_id"] for item in selected}
    if len(completed) != TRIAL_SIZE or {item["occupation_id"] for item in completed} != expected:
        raise ValueError("trial completion is incomplete")
    usage = {key: sum(row[key] for row in all_usage) for key in all_usage[0]}
    total_cost = sum(float(item["estimated_usd"]) for item in all_costs)
    mappings = OUT / "trial_100_mappings.json"
    cost_path = OUT / "cost_report.json"
    if not mappings.exists():
        exclusive_json(mappings, {"schema_version": "deepseek-sno-v3-trial-mappings-v1", "taxonomy_version": catalog["taxonomy_version"], "sample_size": TRIAL_SIZE, "status_counts": dict(Counter(item["status"] for item in completed)), "results": completed, "non_production": True})
    if not cost_path.exists():
        exclusive_json(cost_path, {"schema_version": "deepseek-sno-v3-trial-cost-v1", "model_requested": model, "classified_name_count": TRIAL_SIZE, "usage": usage, "estimated_cost_usd": total_cost, "stop_budget_usd": USD_BUDGET, "cost_scope": "Estimate from API-reported tokens and the DeepSeek Flash rates embedded in the existing runner; not a provider billing export."})
    print(json.dumps({"classified": TRIAL_SIZE, "status_counts": dict(Counter(item["status"] for item in completed)), "estimated_cost_usd": total_cost, "output": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
