"""Resumable name-only remap for non-confirmed SNO display entries.

This does not modify the frozen taxonomy or source associations.  It emits
batch-local decisions with existing category IDs, including the deepest safely
known parent for display-only "other" bubbles.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError

from run_deepseek_name_classification_trial_v1 import (
    api_post_retry, canonical_base_url, estimate_cost, exclusive_json,
    output_content, read_dotenv, read_json, response_metadata, usage_summary,
)

ROOT = Path("data/processed/record_role_classification_v1")
MAPPING = ROOT / "targeted_name_repairs/name_only_targeted_repair_v1/full_name_only_mapping_repaired_v1.json"
REGISTRY = ROOT / "name_registry/standard_occupation_to_original_names_final_deterministic_v4.json"
TAXONOMY = ROOT / "catalog_mappings/taxonomy_embedding_texts_v1.json"
OUT = ROOT / "targeted_name_repairs/name_only_targeted_repair_v1/deepseek_nonmapped_remap_v3"
BATCH_SIZE = 25
VALID_STATUS = {"mapped", "review", "multi_role", "taxonomy_gap"}


def compact_taxonomy(rows):
    return [{"id": row["category_id"], "l1": row["level_1"], "l2": row["level_2"], "l3": row["level_3"], "boundary": row["matching_text"]} for row in rows]


def make_candidates(mapping, registry):
    aliases = {row["standard_occupation_id"]: row.get("original_names", []) for row in registry["occupations"]}
    candidates = []
    for row in mapping["results"]:
        if row["status"] == "mapped":
            continue
        candidates.append({
            "entry_id": row["standard_occupation_id"],
            "entry_type": "standard_occupation",
            "name": row["standard_name"],
            "aliases": aliases.get(row["standard_occupation_id"], [])[:12],
            "current_status": row["status"],
            "current_target_category_id": row.get("target_category_id"),
            "current_reason": row.get("reason"),
            "original_group_ids": row["original_group_ids"],
            "source_atomic_unit_ids": row["source_atomic_unit_ids"],
            "source_record_ids": row["source_record_ids"],
        })
    for group in mapping["unclassified_abnormal_groups"]:
        candidates.append({
            "entry_id": f"ABNORMAL:{group['record_role_group_id']}",
            "entry_type": "abnormal_atomic_group",
            "name": group["original_name"],
            "aliases": [group["original_name"]],
            "current_status": "abnormal",
            "current_target_category_id": None,
            "current_reason": "原子岗位名称异常或截断，尚未进入标准职业映射。",
            "original_group_ids": [group["record_role_group_id"]],
            "source_atomic_unit_ids": group["source_atomic_unit_ids"],
            "source_record_ids": group["source_record_ids"],
        })
    return sorted(candidates, key=lambda row: row["entry_id"])


def prompt(taxonomy, batch):
    system = """你是职业目录复核助手。只根据职业名称、原始名称别名、当前映射和冻结目录判断；不要假设公司、行业、招聘正文或技能。
任务是尽量把职业放入已有三级类别，但不能无依据补充技术语言、后端/前端、行业或服务对象。
只返回一个 JSON 对象，格式为 {"results":[{"entry_id":"...","status":"...","target_category_id":"...或null","reason":"..."}]}。输出每项：entry_id、status、target_category_id、reason。
- status=mapped：名称足以支持一个有效三级 ID，target_category_id 必须为该三级 ID。
- status=review：三级不足，但可确认一级或二级时 target_category_id 填该已存在的一级／二级 ID；完全不能确认则 null。
- status=multi_role：名称明确列出多个互不兼容的独立职业；若能确认共同一级或二级，可填最深共同上级，否则 null。
- status=taxonomy_gap：名称职业清晰，但冻结目录没有合适三级；若能确认一级或二级，可填最深共同上级，否则 null。
“培训生/实习/校招/职级”不是职业；复合职责不自动是 multi_role。截断或专业清单不要猜补。所有 ID 必须原样取自目录。逐字回传 entry_id，并针对每项写具体理由。
冻结目录：""" + json.dumps(taxonomy, ensure_ascii=False, separators=(",", ":"))
    # Source associations stay local.  The remap is deliberately name-only.
    api_batch = [{
        "entry_id": row["entry_id"],
        "entry_type": row["entry_type"],
        "name": row["name"],
        "aliases": row["aliases"],
        "current_status": row["current_status"],
        "current_target_category_id": row["current_target_category_id"],
        "current_reason": row["current_reason"],
    } for row in batch]
    user = "待复核项：" + json.dumps(api_batch, ensure_ascii=False, separators=(",", ":"))
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def request_body(model, messages):
    return {"model": model, "messages": messages, "temperature": 0, "max_tokens": 5000, "response_format": {"type": "json_object"}, "thinking": {"type": "disabled"}, "stream": False}


def validate(raw, batch, valid_l1, valid_l2, valid_l3):
    rows = raw.get("results") if isinstance(raw, dict) else None
    expected = {item["entry_id"] for item in batch}
    if not isinstance(rows, list) or {item.get("entry_id") for item in rows} != expected or len(rows) != len(expected):
        raise ValueError("result IDs do not exactly match batch")
    output = []
    for row in rows:
        status, target, reason = row.get("status"), row.get("target_category_id"), row.get("reason")
        if status not in VALID_STATUS or not isinstance(reason, str) or not reason.strip():
            raise ValueError("invalid status or reason")
        if target is not None and target not in valid_l1 | valid_l2 | valid_l3:
            raise ValueError(f"unknown category ID {target!r}")
        if status == "mapped" and target not in valid_l3:
            raise ValueError("mapped requires valid level-3 category")
        output.append({"entry_id": row["entry_id"], "status": status, "target_category_id": target, "reason": reason.strip()})
    return output


def main():
    dotenv = read_dotenv(Path(".env"))
    # Existing project configuration may retain the legacy OPENAI_API_KEY
    # variable name while pointing it at the DeepSeek-compatible endpoint.
    key = (os.environ.get("DEEPSEEK_API_KEY") or dotenv.get("DEEPSEEK_API_KEY")
           or os.environ.get("OPENAI_API_KEY") or dotenv.get("OPENAI_API_KEY"))
    if not key:
        raise RuntimeError("No configured DeepSeek credential")
    base = canonical_base_url(os.environ.get("DEEPSEEK_BASE_URL") or dotenv.get("DEEPSEEK_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or dotenv.get("OPENAI_BASE_URL") or "https://api.deepseek.com")
    model = os.environ.get("DEEPSEEK_MODEL") or dotenv.get("DEEPSEEK_MODEL") or os.environ.get("OPENAI_MODEL") or dotenv.get("OPENAI_MODEL") or "deepseek-flash"
    mapping, registry, taxonomy_source = read_json(MAPPING), read_json(REGISTRY), read_json(TAXONOMY)
    taxonomy = compact_taxonomy(taxonomy_source["rows"])
    valid_l3 = {row["id"] for row in taxonomy}
    valid_l2 = {row["id"].rsplit("/", 1)[0] for row in taxonomy}
    valid_l1 = {row["l1"] for row in taxonomy}
    candidates = make_candidates(mapping, registry)
    OUT.mkdir(parents=True, exist_ok=True)
    costs = []
    for batch_number, start in enumerate(range(0, len(candidates), BATCH_SIZE), 1):
        final = OUT / f"batch_{batch_number:03d}_reviewed.json"
        if final.exists():
            costs.append(read_json(final).get("cost_estimate", {"estimated_usd": 0}))
            continue
        batch = candidates[start:start + BATCH_SIZE]
        messages = prompt(taxonomy, batch)
        request = request_body(model, messages)
        request_path = OUT / f"batch_{batch_number:03d}_api_input.json"
        response_path = OUT / f"batch_{batch_number:03d}_api_output.json"
        if not request_path.exists():
            exclusive_json(request_path, {"endpoint": base + "/chat/completions", "model": model, "messages": messages, "privacy_scope": "name-only mapping with existing mapping state; no company, industry, recruitment prose, skills or source links sent"})
        observed = datetime.now(timezone.utc)
        if response_path.exists():
            response, attempts = read_json(response_path), 0
        else:
            try:
                response, attempts = api_post_retry(base, key, request)
            except HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:2000]
                raise RuntimeError(f"DeepSeek HTTP {exc.code}: {detail}") from exc
            try:
                exclusive_json(response_path, response)
            except FileExistsError:
                response, attempts = read_json(response_path), 0
        validation_retry_count = 0
        for retry_index in range(3):
            try:
                decisions = validate(json.loads(output_content(response)), batch, valid_l1, valid_l2, valid_l3)
                break
            except (ValueError, json.JSONDecodeError) as validation_error:
                if retry_index == 2:
                    raise validation_error
                validation_retry_count = retry_index + 1
                retry_messages = [
                    messages[0],
                    {"role": "user", "content": messages[1]["content"] + "\n上一轮 JSON 返回的 entry_id 不完整或不匹配。请重新只返回本批全部 25 项（或本批实际项数）的 JSON results；每个 entry_id 必须逐字复制输入。"},
                ]
                retry_request = request_body(model, retry_messages)
                retry_input = OUT / f"batch_{batch_number:03d}_retry_{validation_retry_count:03d}_api_input.json"
                retry_output = OUT / f"batch_{batch_number:03d}_retry_{validation_retry_count:03d}_api_output.json"
                if not retry_input.exists():
                    exclusive_json(retry_input, {"endpoint": base + "/chat/completions", "model": model, "messages": retry_messages, "validation_retry": True})
                if retry_output.exists():
                    response = read_json(retry_output)
                else:
                    try:
                        response, _ = api_post_retry(base, key, retry_request)
                    except HTTPError as exc:
                        detail = exc.read().decode("utf-8", errors="replace")[:2000]
                        raise RuntimeError(f"DeepSeek HTTP {exc.code}: {detail}") from exc
                    try:
                        exclusive_json(retry_output, response)
                    except FileExistsError:
                        response = read_json(retry_output)
        usage = usage_summary(response)
        cost = estimate_cost(usage, observed)
        exclusive_json(final, {"batch_number": batch_number, "processing_method": "deepseek_api_name_only_nonmapped_remap", "model_requested": model, "batch_input_count": len(batch), "attempts": attempts, "validation_retry_count": validation_retry_count, "response_metadata": response_metadata(response), "usage": usage, "cost_estimate": cost, "results": decisions})
        costs.append(cost)
        print(json.dumps({"completed_batch": batch_number, "completed_entries": min(start + BATCH_SIZE, len(candidates)), "total_entries": len(candidates), "cost_estimated_usd": sum(float(item.get("estimated_usd", 0)) for item in costs)}, ensure_ascii=False), flush=True)
    print(json.dumps({"completed_entries": len(candidates), "total_entries": len(candidates), "status_counts": dict(Counter(item["status"] for path in OUT.glob("batch_*_reviewed.json") for item in read_json(path)["results"])), "cost_estimated_usd": sum(float(item.get("estimated_usd", 0)) for item in costs)}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
