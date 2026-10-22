"""Resumable name-only review for existing L1/L2/L3 placements.

The source names are former generic-R&D display entries.  A result may be
promoted to an existing L3, or to the deepest explicit existing L2/L1 while
retaining review state.  The script does not alter the taxonomy or projection.
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
    output_content, read_dotenv, response_metadata, usage_summary,
)


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data/processed/record_role_classification_v1/targeted_name_repairs/name_only_targeted_repair_v1"
PROJECTION = DATA_DIR / "display_projection_v7.json"
TAXONOMY = ROOT / "data/processed/record_role_classification_v1/catalog_mappings/taxonomy_embedding_texts_v1.json"
OUT = DATA_DIR / "general_technology_clear_remap_v2"
BATCH_SIZE = 20
SOURCE_BUCKET_IDS = {
    "holding:level_1:互联网/AI:software-digital",
    "holding:level_1:电子/电气/通信:hardware",
    "holding:level_1:生产制造:manufacturing",
    "holding:level_1:房地产/建筑:infrastructure",
    "holding:level_1:其他职业:other-rnd",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def candidates(projection: dict) -> list[dict]:
    rows = []
    for bucket_id in SOURCE_BUCKET_IDS:
        bucket = projection["level1_holding_bubbles"].get(bucket_id)
        if not bucket:
            raise KeyError(f"missing source display bucket {bucket_id}")
        rows.extend({
            "entry_id": row["standard_occupation_id"],
            "name": row["label"],
            "source_display_bucket_id": bucket_id,
            "source_display_path": f"{bucket['level_1']} / {bucket['label']}",
            "is_abnormal": bool(row.get("abnormal_source_group")),
        } for row in bucket["occupations"])
    ids = [row["entry_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("source display entries are not unique")
    return sorted(rows, key=lambda row: row["entry_id"])


def compact_taxonomy(rows: list[dict]) -> list[dict]:
    """Expose every selectable level explicitly, not inferred path fragments."""
    levels: dict[str, dict] = {}
    for row in rows:
        category_id = row["category_id"]
        l1, l2, l3 = row["level_1"], row["level_2"], row["level_3"]
        l2_id = category_id.rsplit("/", 1)[0]
        levels.setdefault(l1, {"id": l1, "level": "l1", "l1": l1})
        levels.setdefault(l2_id, {"id": l2_id, "level": "l2", "l1": l1, "l2": l2})
        levels[category_id] = {"id": category_id, "level": "l3", "l1": l1, "l2": l2, "l3": l3}
    return sorted(levels.values(), key=lambda row: (row["id"].count("/"), row["id"]))


def messages(taxonomy: list[dict], batch: list[dict]) -> list[dict]:
    system = """你是职业目录语义复核助手。只根据岗位名称判断能否明确放入已有职业目录；不读取或推断公司、行业、职责、技能或学历专业。
只返回 JSON：{"results":[{"entry_id":"...","decision":"map_l3、map_l2、map_l1或keep","target_category_id":"已有目录ID或null","reason":"具体理由"}]}。
map_l3 仅在名称本身明确支持一个唯一合理三级时使用。名称能确认职业领域或二级方向、但不足以细分三级时使用 map_l2；仅能确认一级时使用 map_l1。不得因为“工程师、研发、系统、技术、开发”等泛词，补充前后端、编程语言、硬件、制造、行业或服务对象。名称截断、专业清单、复合岗位及宽泛称谓一律 keep。target_category_id 必须逐字取自目录。
目录：""" + json.dumps(taxonomy, ensure_ascii=False, separators=(",", ":"))
    user = "待复核岗位名称：" + json.dumps(batch, ensure_ascii=False, separators=(",", ":"))
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def body(model: str, prompt: list[dict]) -> dict:
    return {"model": model, "messages": prompt, "temperature": 0, "max_tokens": 4000, "response_format": {"type": "json_object"}, "thinking": {"type": "disabled"}, "stream": False}


def validate(parsed: dict, batch: list[dict], valid_l1: set[str], valid_l2: set[str], valid_l3: set[str]) -> list[dict]:
    expected = {row["entry_id"] for row in batch}
    results = parsed.get("results") if isinstance(parsed, dict) else None
    if not isinstance(results, list) or len(results) != len(expected) or {row.get("entry_id") for row in results} != expected:
        raise ValueError("result IDs do not exactly match input batch")
    output = []
    for row in results:
        decision, target, reason = row.get("decision"), row.get("target_category_id"), row.get("reason")
        if decision not in {"map_l3", "map_l2", "map_l1", "keep"} or not isinstance(reason, str) or not reason.strip():
            raise ValueError("invalid decision or reason")
        if decision == "map_l3" and target not in valid_l3:
            raise ValueError(f"map_l3 must use a valid level-3 category: {target!r}")
        if decision == "map_l2" and target not in valid_l2:
            raise ValueError(f"map_l2 must use a valid level-2 category: {target!r}")
        if decision == "map_l1" and target not in valid_l1:
            raise ValueError(f"map_l1 must use a valid level-1 category: {target!r}")
        if decision == "keep" and target is not None:
            raise ValueError("keep must not provide a category ID")
        output.append({"entry_id": row["entry_id"], "decision": decision, "target_category_id": target, "reason": reason.strip()})
    return output


def main() -> None:
    dotenv = read_dotenv(ROOT / ".env")
    key = os.environ.get("DEEPSEEK_API_KEY") or dotenv.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY") or dotenv.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("No configured DeepSeek credential")
    base = canonical_base_url(os.environ.get("DEEPSEEK_BASE_URL") or dotenv.get("DEEPSEEK_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or dotenv.get("OPENAI_BASE_URL") or "https://api.deepseek.com")
    model = os.environ.get("DEEPSEEK_MODEL") or dotenv.get("DEEPSEEK_MODEL") or os.environ.get("OPENAI_MODEL") or dotenv.get("OPENAI_MODEL") or "deepseek-flash"
    projection = read_json(PROJECTION)
    taxonomy = compact_taxonomy(read_json(TAXONOMY)["rows"])
    valid_l1 = {row["id"] for row in taxonomy if row["level"] == "l1"}
    valid_l2 = {row["id"] for row in taxonomy if row["level"] == "l2"}
    valid_l3 = {row["id"] for row in taxonomy if row["level"] == "l3"}
    rows = candidates(projection)
    OUT.mkdir(parents=True, exist_ok=True)
    costs = []
    for number, start in enumerate(range(0, len(rows), BATCH_SIZE), 1):
        final = OUT / f"batch_{number:03d}_reviewed.json"
        if final.exists():
            costs.append(read_json(final).get("cost_estimate", {"estimated_usd": 0}))
            continue
        batch = rows[start:start + BATCH_SIZE]
        prompt = messages(taxonomy, batch)
        request = body(model, prompt)
        request_path = OUT / f"batch_{number:03d}_api_input.json"
        output_path = OUT / f"batch_{number:03d}_api_output.json"
        if not request_path.exists():
            exclusive_json(request_path, {"endpoint": base + "/chat/completions", "model": model, "messages": prompt, "privacy_scope": "standard occupation ID, occupation name and frozen category directory only"})
        if output_path.exists():
            raw, attempts = read_json(output_path), 0
        else:
            try:
                raw, attempts = api_post_retry(base, key, request)
            except HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:2000]
                raise RuntimeError(f"DeepSeek HTTP {exc.code}: {detail}") from exc
            exclusive_json(output_path, raw)
        decisions = validate(json.loads(output_content(raw)), batch, valid_l1, valid_l2, valid_l3)
        usage = usage_summary(raw)
        cost = estimate_cost(usage, datetime.now(timezone.utc))
        exclusive_json(final, {"batch_number": number, "processing_method": "deepseek_api_name_only_clear_category_review", "model_requested": model, "input_count": len(batch), "attempts": attempts, "usage": usage, "cost_estimate": cost, "results": decisions})
        costs.append(cost)
        print(json.dumps({"completed": min(start + BATCH_SIZE, len(rows)), "total": len(rows), "placed": sum(row["decision"] != "keep" for path in OUT.glob("batch_*_reviewed.json") for row in read_json(path)["results"]), "estimated_usd": sum(float(item.get("estimated_usd", 0)) for item in costs)}, ensure_ascii=False), flush=True)
    decisions = [decision for path in OUT.glob("batch_*_reviewed.json") for decision in read_json(path)["results"]]
    print(json.dumps({"completed": len(decisions), "total": len(rows), "decision_counts": dict(Counter(row["decision"] for row in decisions)), "estimated_usd": sum(float(item.get("estimated_usd", 0)) for item in costs)}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
