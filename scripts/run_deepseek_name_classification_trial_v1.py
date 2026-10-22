"""Run a bounded DeepSeek name-only taxonomy-classification trial.

This script deliberately reads only standard occupation IDs/names and the frozen
taxonomy.  It never sends company, industry, recruitment prose, skills, or
source-record links to the API.  Output is a standalone trial artifact and the
v4 name registry is never modified.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path("data/processed/record_role_classification_v1")
V4_PATH = ROOT / "name_registry" / "standard_occupation_to_original_names_final_deterministic_v4.json"
TAXONOMY_PATH = ROOT / "catalog_mappings" / "taxonomy_embedding_texts_v1.json"
# Set DEEPSEEK_TRIAL_VERSION for a separate, never-overwritten run. Existing
# v1/v2 artifacts stay immutable even as this reusable runner is improved.
TRIAL_VERSION = os.environ.get("DEEPSEEK_TRIAL_VERSION", "v2")
OUT_DIR = ROOT / "api_trials" / f"deepseek_name_classification_trial_{TRIAL_VERSION}"
PROMPT_PROFILE = os.environ.get("DEEPSEEK_PROMPT_PROFILE", "baseline")
REUSE_SELECTION_FROM = os.environ.get("DEEPSEEK_REUSE_SELECTION_FROM")
TRIAL_SIZE = int(os.environ.get("DEEPSEEK_CLASSIFICATION_LIMIT", "100"))
BATCH_SIZE = int(os.environ.get("DEEPSEEK_CLASSIFICATION_BATCH_SIZE", "20"))
USE_ALL_OCCUPATIONS = os.environ.get("DEEPSEEK_USE_ALL_OCCUPATIONS") == "1"
# Optional inclusive batch partition.  The default covers the whole input.
# It exists solely to allow disjoint, resumable workers to finish a long
# approved run without ever sending the same selected batch intentionally.
BATCH_NUMBER_START = int(os.environ.get("DEEPSEEK_BATCH_NUMBER_START", "1"))
BATCH_NUMBER_END_RAW = os.environ.get("DEEPSEEK_BATCH_NUMBER_END")
MAX_API_ATTEMPTS = 3
USD_BUDGET = 1.0


def read_dotenv(path: Path) -> dict[str, str]:
    """Small dependency-free dotenv reader; values never appear in output."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if (value.startswith("\"") and value.endswith("\"")) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def exclusive_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_base_url(value: str) -> str:
    return value.rstrip("/")


def api_post(base_url: str, api_key: str, body: dict[str, Any]) -> dict[str, Any]:
    encoded = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    request = Request(
        f"{base_url}/chat/completions",
        data=encoded,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def api_post_retry(base_url: str, api_key: str, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
    last_error: Exception | None = None
    for attempt in range(1, MAX_API_ATTEMPTS + 1):
        try:
            return api_post(base_url, api_key, body), attempt
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < MAX_API_ATTEMPTS:
                time.sleep(2**(attempt - 1))
    assert last_error is not None
    raise last_error


def usage_summary(response: dict[str, Any]) -> dict[str, int]:
    usage = response.get("usage") or {}
    prompt = int(usage.get("prompt_tokens", 0) or 0)
    completion = int(usage.get("completion_tokens", 0) or 0)
    cached = int(
        usage.get("prompt_cache_hit_tokens", 0)
        or (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
        or 0
    )
    missed = int(usage.get("prompt_cache_miss_tokens", 0) or max(prompt - cached, 0))
    reasoning = int((usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0) or 0)
    return {
        "input_tokens": prompt,
        "cached_input_tokens": cached,
        "uncached_input_tokens": missed,
        "output_tokens": completion,
        "reasoning_tokens": reasoning,
        "total_tokens": int(usage.get("total_tokens", prompt + completion) or prompt + completion),
    }


def china_peak_at(timestamp: datetime) -> bool:
    """Current DeepSeek pricing window: Beijing weekday 09-12 / 14-18."""
    # UTC+8 without an optional dependency.
    china_hour = (timestamp.hour + 8) % 24
    china_weekday = timestamp.weekday()
    return china_weekday < 5 and (9 <= china_hour < 12 or 14 <= china_hour < 18)


def estimate_cost(usage: dict[str, int], observed_at: datetime) -> dict[str, Any]:
    """Estimate DeepSeek Flash USD cost from reported token usage/current rates."""
    peak = china_peak_at(observed_at)
    rates = {
        "cached_input_per_million_usd": 0.006 if peak else 0.003,
        "uncached_input_per_million_usd": 0.30 if peak else 0.15,
        "output_per_million_usd": 1.20 if peak else 0.60,
    }
    amount = (
        usage["cached_input_tokens"] * rates["cached_input_per_million_usd"]
        + usage["uncached_input_tokens"] * rates["uncached_input_per_million_usd"]
        + usage["output_tokens"] * rates["output_per_million_usd"]
    ) / 1_000_000
    return {
        "basis": "reported_usage_times_documented_deepseek_flash_rates; provider does not return billed currency",
        "beijing_price_window": "peak" if peak else "off_peak",
        "rates_usd_per_million_tokens": rates,
        "estimated_usd": amount,
    }


def output_content(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        raise ValueError("API response did not include choices")
    content = ((choices[0].get("message") or {}).get("content"))
    if not isinstance(content, str) or not content.strip():
        raise ValueError("API response did not include non-empty JSON content")
    return content


def compact_taxonomy(rows: list[dict[str, Any]]) -> dict[str, Any]:
    l2: dict[tuple[str, str], str] = {}
    l1: set[str] = set()
    l3: list[dict[str, str]] = []
    for row in rows:
        l1_name = row["level_1"]
        l2_name = row["level_2"]
        category_id = row["category_id"]
        l1.add(l1_name)
        # Level-1 display names can themselves contain '/', therefore a parent
        # identifier must be derived from the right-hand level-3 rule segment.
        l2[(l1_name, l2_name)] = category_id.rsplit("/", 1)[0]
        l3.append(
            {
                "id": category_id,
                "level_1": l1_name,
                "level_2": l2_name,
                "level_3": row["level_3"],
            }
        )
    return {
        "level_1_categories": [{"id": name, "name": name} for name in sorted(l1)],
        "level_2_categories": [
            {"id": identifier, "level_1": one, "name": two}
            for (one, two), identifier in sorted(l2.items())
        ],
        "level_3_categories": l3,
    }


def category_ids(rows: list[dict[str, Any]]) -> tuple[set[str], set[str], set[str]]:
    l3 = {row["category_id"] for row in rows}
    l2 = {identifier.rsplit("/", 1)[0] for identifier in l3}
    # The level-1 label is the stable parent identifier in the frozen source;
    # splitting an ID would be wrong for labels such as 市场/公关/广告.
    l1 = {row["level_1"] for row in rows}
    return l1, l2, l3


def selection_tags(name: str) -> list[str]:
    tags: list[tuple[str, str]] = [
        ("software_data", r"Java|JAVA|Python|C\+\+|C#|\.NET|前端|后端|算法|数据|测试|运维|嵌入|软件|开发|芯片|硬件"),
        ("design_media", r"设计|UI|UX|美术|动画|视频|摄影|编导|编辑"),
        ("sales_marketing", r"销售|客户|市场|品牌|运营|商务|电商|直播"),
        ("finance_legal", r"财务|会计|审计|税|证券|基金|期货|法务|律师"),
        ("people_admin", r"人力|HR|招聘|行政|培训|管培|管理培训"),
        ("education_medical", r"教师|讲师|医生|医师|护士|药|康复|医疗"),
        ("manufacturing_engineering", r"机械|电气|工艺|质量|生产|建筑|结构|设备"),
        ("service_creative", r"餐饮|酒店|旅游|花艺|演员|配音|模特|客服"),
        ("abbreviation_or_english", r"[A-Za-z]{2,}"),
        ("broad_or_composite", r"^(工程师|专员|经理|助理|实习生|管理培训生|管培生)$|[/、+&]"),
    ]
    return [tag for tag, pattern in tags if re.search(pattern, name, re.I)]


def choose_trial(occupations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministically take a mixed name-only sample, not a mapping result."""
    ordered = sorted(
        occupations,
        key=lambda item: hashlib.sha256(item["standard_occupation_id"].encode("utf-8")).hexdigest(),
    )
    selected: list[dict[str, Any]] = []
    used: set[str] = set()
    for tag in [
        "software_data", "design_media", "sales_marketing", "finance_legal", "people_admin",
        "education_medical", "manufacturing_engineering", "service_creative",
        "abbreviation_or_english", "broad_or_composite",
    ]:
        for item in ordered:
            identifier = item["standard_occupation_id"]
            if identifier not in used and tag in selection_tags(item["standard_name"]):
                selected.append({
                    "standard_occupation_id": identifier,
                    "standard_name": item["standard_name"],
                    "selection_strata": tag,
                })
                used.add(identifier)
                break
    for item in ordered:
        if len(selected) == TRIAL_SIZE:
            break
        identifier = item["standard_occupation_id"]
        if identifier in used:
            continue
        tags = selection_tags(item["standard_name"])
        selected.append({
            "standard_occupation_id": identifier,
            "standard_name": item["standard_name"],
            "selection_strata": tags[0] if tags else "general_name_only",
        })
        used.add(identifier)
    if len(selected) != TRIAL_SIZE:
        raise ValueError(f"Expected {TRIAL_SIZE} trial occupations; got {len(selected)}")
    return selected


def classification_messages(directory: dict[str, Any], batch: list[dict[str, Any]]) -> list[dict[str, str]]:
    if PROMPT_PROFILE in {"improved_v3", "full_v4"}:
        system = (
            "你是一名职业分类助手。根据岗位名称，将其归入提供的职业目录。允许专业判断和合理初稿，不要求唯一权威答案。\n"
            "判断原则：\n"
            "1. 按名称表达的核心职业职责分类。公司行业、语言、地点、学历、招聘状态和职级修饰不应改变核心职业。\n"
            "2. 使用最深且合理的类别。名称明确、目录能承接时归到三级；缺乏细分依据时保留一级或二级，不凭空补充技术语言、业务方向或行业。\n"
            "3. 不因通用词误判：总装不必然属于汽车，前端不必然是Web，机器人开发不必然是算法，安全不必然是网络安全。\n"
            "4. 不把正常修饰或复合职责误当多岗位。文案实习生（德语/英语）、化工外贸业务员是单职业；法务风控岗可能是复合岗位。只有明显列出多个独立职业的名称才标记multi_role，不确定则review。\n"
            "5. 可忽略明显冗余字符，如“岗理财经理”中的前缀“岗”；不补全无法识别的截断内容。\n"
            "6. 名称表达清楚但目录没有承接类别时标记taxonomy_gap，不要混称名称不足。\n"
            "7. 所有类别ID必须从提供的目录选择，不拼接、缩写或虚构ID。\n"
            "8. 允许合理职业推断，但不得选择与名称明确矛盾的类别；名称缺少技术方向时，不默认后端、软件测试或特定算法。无法支持三级时保留已确认的一级或二级。\n"
            "9. 复合职责不自动视为多个岗位；只有名称明显列出两个或以上独立职业且不能由同一目录承接时才使用multi_role。\n"
            "只输出一个合法JSON对象：{\"results\":[{\"occupation_id\":string,\"target_category_id\":string或null,\"status\":\"mapped|review|taxonomy_gap|multi_role\",\"reason\":string}]}。"
            "reason必须简短说明核心判断依据；review需说明缺少什么信息。mapped必须使用三级ID；taxonomy_gap与multi_role的target_category_id必须为null。\n"
            "以下是唯一可用目录（稳定提示词的一部分）：\n"
            + json.dumps(directory, ensure_ascii=False, separators=(",", ":"))
        )
        api_batch = [
            {"occupation_id": item["standard_occupation_id"], "occupation_name": item["standard_name"]}
            for item in batch
        ]
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps({"occupations": api_batch}, ensure_ascii=False, separators=(",", ":"))},
        ]
    system = (
        "你是职业目录分类器。只能依据每个岗位名称和给定目录判断，不要使用公司、行业、职责、技能或外部知识补全。"
        "名称明确时，选择一个给定三级目录ID并设 status=mapped。名称只能确定到一级或二级时，选择给定上级ID并设 status=review。"
        "名称本身不足以分类时设 status=review 且 target_category_id 为 null；目录无法承接时设 status=gap；名称明确粘连多个职业时设 status=multi_role。"
        "不要臆造目录ID。只在 review、gap、multi_role 时给出不超过50字的中文 reason；mapped 的 reason 必须为 null。"
        "只输出一个合法 JSON 对象，格式为 {\"results\":[{\"standard_occupation_id\":...,\"target_category_id\":string或null,\"status\":\"mapped|review|gap|multi_role\",\"reason\":string或null}]}。"
    )
    user = json.dumps({"taxonomy": directory, "occupations": batch}, ensure_ascii=False, separators=(",", ":"))
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def validate_classification(payload: Any, batch: list[dict[str, Any]], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise ValueError("Output must be a JSON object containing a results array")
    results = payload["results"]
    identifier_field = "occupation_id" if PROMPT_PROFILE in {"improved_v3", "full_v4"} else "standard_occupation_id"
    expected = {item["standard_occupation_id"] for item in batch}
    got = [item.get(identifier_field) for item in results if isinstance(item, dict)]
    if len(results) != len(batch) or set(got) != expected or len(got) != len(set(got)):
        raise ValueError("Output IDs do not exactly match the requested batch")
    l1, l2, l3 = category_ids(rows)
    allowed = l1 | l2 | l3
    checked: list[dict[str, Any]] = []
    allowed_statuses = (
        {"mapped", "review", "taxonomy_gap", "multi_role"}
        if PROMPT_PROFILE in {"improved_v3", "full_v4"}
        else {"mapped", "review", "gap", "multi_role"}
    )
    for item in results:
        if set(item) != {identifier_field, "target_category_id", "status", "reason"}:
            raise ValueError("Each result must contain exactly the four structured fields")
        status = item["status"]
        target = item["target_category_id"]
        reason = item["reason"]
        if status not in allowed_statuses:
            raise ValueError(f"Unsupported status: {status!r}")
        if target is not None and target not in allowed:
            raise ValueError(f"Unknown taxonomy ID: {target!r}")
        if status == "mapped" and target not in l3:
            raise ValueError("mapped records must use a level-3 category ID")
        if PROMPT_PROFILE in {"improved_v3", "full_v4"} and (not isinstance(reason, str) or not reason.strip() or len(reason) > 80):
            raise ValueError("improved output requires a short reason for every record")
        if PROMPT_PROFILE not in {"improved_v3", "full_v4"} and status == "mapped" and reason is not None:
            raise ValueError("mapped records must have null reason")
        if PROMPT_PROFILE not in {"improved_v3", "full_v4"} and status != "mapped" and (not isinstance(reason, str) or not reason.strip() or len(reason) > 50):
            raise ValueError("non-mapped records require a short reason")
        checked.append(item)
    return checked


def response_metadata(response: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_id": response.get("id"),
        "model": response.get("model"),
        "object": response.get("object"),
        "created": response.get("created"),
        "finish_reason": ((response.get("choices") or [{}])[0]).get("finish_reason"),
    }


def probe_body(model: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": "只输出合法JSON对象。"},
            {"role": "user", "content": "输出 {\"status\":\"ok\"}，不要包含其他字段。"},
        ],
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
        "temperature": 0,
        "max_tokens": 32,
        "stream": False,
    }


def classification_body(model: str, messages: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "model": model,
        "messages": messages,
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
        "temperature": 0,
        "max_tokens": 6000,
        "stream": False,
    }


def save_probe(base_url: str, model: str, api_key: str) -> dict[str, Any]:
    request_path = OUT_DIR / "connection_probe_request.json"
    response_path = OUT_DIR / "connection_probe_response.json"
    if response_path.exists():
        return read_json(response_path)
    body = probe_body(model)
    if not request_path.exists():
        exclusive_json(request_path, {
            "endpoint": f"{base_url}/chat/completions",
            "model": model,
            "body": body,
            "note": "No credential is stored in this request artifact.",
        })
    observed = datetime.now(timezone.utc)
    try:
        response, attempts = api_post_retry(base_url, api_key, body)
        parsed = json.loads(output_content(response))
        if parsed != {"status": "ok"}:
            raise ValueError("probe JSON did not match the expected object")
        payload = {
            "connection_valid": True,
            "endpoint": f"{base_url}/chat/completions",
            "model_requested": model,
            "response_metadata": response_metadata(response),
            "attempts": attempts,
            "usage": usage_summary(response),
            "cost_estimate": estimate_cost(usage_summary(response), observed),
            "parsed_output": parsed,
            "observed_at_utc": observed.isoformat(),
        }
        exclusive_json(response_path, payload)
        return payload
    except Exception as exc:
        error_path = OUT_DIR / "connection_probe_error.json"
        if not error_path.exists():
            exclusive_json(error_path, {
                "connection_valid": False,
                "endpoint": f"{base_url}/chat/completions",
                "model_requested": model,
                "exception_type": type(exc).__name__,
                "message": str(exc),
                "observed_at_utc": observed.isoformat(),
            })
        raise


def main() -> None:
    dotenv = read_dotenv(Path(".env"))
    # Environment variables deliberately take precedence and the key is never printed.
    api_key = os.environ.get("DEEPSEEK_API_KEY") or dotenv.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY") or dotenv.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("No DEEPSEEK_API_KEY or OPENAI_API_KEY found in environment/.env")
    base_url = canonical_base_url(os.environ.get("DEEPSEEK_BASE_URL") or dotenv.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com")
    model = os.environ.get("DEEPSEEK_MODEL") or dotenv.get("DEEPSEEK_MODEL") or "deepseek-flash"
    source = read_json(V4_PATH)
    taxonomy = read_json(TAXONOMY_PATH)
    occupations = source["occupations"]
    rows = taxonomy["rows"]
    if len(occupations) != 10998 or len(rows) != 444:
        raise ValueError("Unexpected v4/taxonomy counts; refusing to run trial")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    probe = save_probe(base_url, model, api_key)
    if not probe.get("connection_valid"):
        raise RuntimeError("Connection probe did not validate")

    manifest_path = OUT_DIR / "selection_manifest.json"
    if manifest_path.exists():
        manifest = read_json(manifest_path)
        selected = manifest["occupations"]
    else:
        if USE_ALL_OCCUPATIONS:
            selected = [
                {
                    "standard_occupation_id": item["standard_occupation_id"],
                    "standard_name": item["standard_name"],
                    "selection_strata": "full_v4_input",
                }
                for item in occupations
            ]
        elif REUSE_SELECTION_FROM:
            selection_source = read_json(Path(REUSE_SELECTION_FROM))
            selected = selection_source["occupations"]
        else:
            selected = choose_trial(occupations)
        manifest = {
            "schema_version": "deepseek-name-classification-trial-selection-v1",
            "selection_scope": "name-only; selection tags are sampling strata, not classification evidence",
            "source_v4_path": str(V4_PATH),
            "source_v4_sha256": sha256_file(V4_PATH),
            "source_occupation_count": len(occupations),
            "taxonomy_path": str(TAXONOMY_PATH),
            "taxonomy_sha256": sha256_file(TAXONOMY_PATH),
            "taxonomy_level_3_count": len(rows),
            "trial_occupation_count": len(selected),
            "reused_selection_from": REUSE_SELECTION_FROM,
            "occupations": selected,
        }
        exclusive_json(manifest_path, manifest)
    if len(selected) != TRIAL_SIZE or len({x["standard_occupation_id"] for x in selected}) != TRIAL_SIZE:
        raise ValueError("Selection manifest is not exactly 100 unique occupations")

    directory = compact_taxonomy(rows)
    completed: list[dict[str, Any]] = []
    costs: list[dict[str, Any]] = [probe["cost_estimate"]]
    usage_rows: list[dict[str, int]] = [probe["usage"]]
    total_batch_count = (TRIAL_SIZE + BATCH_SIZE - 1) // BATCH_SIZE
    batch_number_end = int(BATCH_NUMBER_END_RAW) if BATCH_NUMBER_END_RAW else total_batch_count
    if BATCH_NUMBER_START < 1 or batch_number_end < BATCH_NUMBER_START or batch_number_end > total_batch_count:
        raise ValueError("Invalid inclusive DEEPSEEK_BATCH_NUMBER_START/END range")
    partial_batch_range = BATCH_NUMBER_START != 1 or batch_number_end != total_batch_count
    for number, start in enumerate(range(0, TRIAL_SIZE, BATCH_SIZE), start=1):
        if number < BATCH_NUMBER_START or number > batch_number_end:
            continue
        batch = selected[start : start + BATCH_SIZE]
        output_path = OUT_DIR / f"batch_{number:03d}_classified.json"
        if output_path.exists():
            saved = read_json(output_path)
            completed.extend(saved["results"])
            costs.append(saved["cost_estimate"])
            usage_rows.append(saved["usage"])
            continue
        spent = sum(float(item["estimated_usd"]) for item in costs)
        if spent >= USD_BUDGET:
            raise RuntimeError(f"Trial budget reached before batch {number}: ${spent:.6f}")
        messages = classification_messages(directory, batch)
        body = classification_body(model, messages)
        input_path = OUT_DIR / f"batch_{number:03d}_api_input.json"
        if not input_path.exists():
            exclusive_json(input_path, {
                "endpoint": f"{base_url}/chat/completions",
                "model": model,
                "messages": messages,
                "response_format": body["response_format"],
                "temperature": body["temperature"],
                "max_tokens": body["max_tokens"],
                "input_sha256": hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(),
                "privacy_scope": "Only occupation ID, occupation name, and frozen taxonomy are included.",
            })
        observed = datetime.now(timezone.utc)
        try:
            raw_path = OUT_DIR / f"batch_{number:03d}_api_output.json"
            if raw_path.exists():
                # A process may stop after receiving a response but before it
                # writes the normalized batch. Resume from that exact response
                # instead of issuing a duplicate paid API request.
                raw = read_json(raw_path)
                attempts = 0
                created = raw.get("created")
                if isinstance(created, (int, float)):
                    observed = datetime.fromtimestamp(created, timezone.utc)
            else:
                raw, attempts = api_post_retry(base_url, api_key, body)
                try:
                    exclusive_json(raw_path, raw)
                except FileExistsError:
                    # Another resumed worker completed this exact raw response
                    # while this request was in flight. Preserve that first raw
                    # artifact and validate it instead of failing the run.
                    raw = read_json(raw_path)
                    attempts = 0
            validation_retry_count = 0
            validation_error: ValueError | None = None
            # Three saved reissues are deliberately narrow: they are only for
            # malformed IDs/category IDs in an otherwise completed response.
            # Each retains the provider response and resumes from it, so a
            # process interruption cannot silently re-bill an earlier retry.
            for retry_index in range(0, 4):
                try:
                    results = validate_classification(json.loads(output_content(raw)), batch, rows)
                    break
                except ValueError as exc:
                    validation_error = exc
                    if retry_index == 3:
                        raise
                    validation_retry_count = retry_index + 1
                    retry_input_path = OUT_DIR / f"batch_{number:03d}_retry_{validation_retry_count:03d}_api_input.json"
                    retry_raw_path = OUT_DIR / f"batch_{number:03d}_retry_{validation_retry_count:03d}_api_output.json"
                    retry_messages = [
                        messages[0],
                        {
                            "role": "user",
                            "content": (
                                messages[1]["content"]
                                + "\n上一次输出含有不在冻结目录中的类别ID，或未逐字回传给定职业ID。请重新输出完整results；occupation_id必须逐字匹配本次输入的每一个ID，target_category_id只能是目录给出的完整ID或null，不能拼写、缩写、翻译或新增ID。"
                            ),
                        },
                    ]
                    retry_body = classification_body(model, retry_messages)
                    if not retry_input_path.exists():
                        exclusive_json(retry_input_path, {
                            "endpoint": f"{base_url}/chat/completions",
                            "model": model,
                            "messages": retry_messages,
                            "response_format": retry_body["response_format"],
                            "temperature": retry_body["temperature"],
                            "max_tokens": retry_body["max_tokens"],
                            "validation_error": str(validation_error),
                        })
                    if retry_raw_path.exists():
                        raw = read_json(retry_raw_path)
                    else:
                        retry_raw, _retry_attempts = api_post_retry(base_url, api_key, retry_body)
                        try:
                            exclusive_json(retry_raw_path, retry_raw)
                            raw = retry_raw
                        except FileExistsError:
                            raw = read_json(retry_raw_path)
            usage = usage_summary(raw)
            cost = estimate_cost(usage, observed)
            record = {
                "schema_version": "deepseek-name-classification-trial-batch-v1",
                "batch_number": number,
                "processing_method": "deepseek_api_name_only",
                "prompt_profile": PROMPT_PROFILE,
                "model_requested": model,
                "response_metadata": response_metadata(raw),
                "attempts": attempts,
                "validation_retry_count": validation_retry_count,
                "source_v4_path": str(V4_PATH),
                "taxonomy_path": str(TAXONOMY_PATH),
                "batch_input_count": len(batch),
                "usage": usage,
                "cost_estimate": cost,
                "observed_at_utc": observed.isoformat(),
                "results": results,
            }
            try:
                exclusive_json(output_path, record)
                completed.extend(results)
                costs.append(cost)
                usage_rows.append(usage)
            except FileExistsError:
                # If another interrupted/resumed invocation won the final
                # normalized write, consume that saved batch and proceed.
                saved = read_json(output_path)
                completed.extend(saved["results"])
                costs.append(saved["cost_estimate"])
                usage_rows.append(saved["usage"])
        except Exception as exc:
            error_path = OUT_DIR / f"batch_{number:03d}_error.json"
            if not error_path.exists():
                exclusive_json(error_path, {
                    "batch_number": number,
                    "exception_type": type(exc).__name__,
                    "message": str(exc),
                    "observed_at_utc": observed.isoformat(),
                })
            raise

    if partial_batch_range:
        print(json.dumps({
            "connection_valid": True,
            "model": model,
            "prompt_profile": PROMPT_PROFILE,
            "processed_batch_range": [BATCH_NUMBER_START, batch_number_end],
            "saved_batch_result_count": len(completed),
            "output_dir": str(OUT_DIR),
        }, ensure_ascii=False))
        return

    result_identifier_field = "occupation_id" if PROMPT_PROFILE in {"improved_v3", "full_v4"} else "standard_occupation_id"
    expected = {item["standard_occupation_id"] for item in selected}
    got = [item[result_identifier_field] for item in completed]
    if len(got) != TRIAL_SIZE or set(got) != expected or len(got) != len(set(got)):
        raise ValueError("Trial batch output does not provide exactly one result for each selected occupation")
    mappings_path = OUT_DIR / "trial_100_mappings.json"
    if not mappings_path.exists():
        exclusive_json(mappings_path, {
            "schema_version": "deepseek-name-classification-trial-mappings-v1",
            "input_v4_path": str(V4_PATH),
            "input_v4_sha256": sha256_file(V4_PATH),
            "taxonomy_path": str(TAXONOMY_PATH),
            "taxonomy_sha256": sha256_file(TAXONOMY_PATH),
            "selected_standard_occupation_count": TRIAL_SIZE,
            "prompt_profile": PROMPT_PROFILE,
            "result_identifier_field": result_identifier_field,
            "status_counts": dict(Counter(item["status"] for item in completed)),
            "results": completed,
            "atomic_linkage_note": "Each standard_occupation_id resolves to untouched atomic/source links in v4; no source links were sent to the API.",
        })
    # Billable-use report includes every saved provider response, including a
    # malformed response followed by the single validation reissue.  Successful
    # batch summaries alone would understate actual usage in that situation.
    all_response_usages = [probe["usage"]]
    all_response_costs = [probe["cost_estimate"]]
    raw_response_paths = sorted(OUT_DIR.glob("batch_*_api_output.json"))
    for raw_response_path in raw_response_paths:
        response_for_cost = read_json(raw_response_path)
        response_time = datetime.now(timezone.utc)
        created = response_for_cost.get("created")
        if isinstance(created, (int, float)):
            response_time = datetime.fromtimestamp(created, timezone.utc)
        response_usage = usage_summary(response_for_cost)
        all_response_usages.append(response_usage)
        all_response_costs.append(estimate_cost(response_usage, response_time))
    total_usage = {key: sum(row[key] for row in all_response_usages) for key in all_response_usages[0]}
    total_cost = sum(float(item["estimated_usd"]) for item in all_response_costs)
    cost_path = OUT_DIR / "cost_report.json"
    if not cost_path.exists():
        exclusive_json(cost_path, {
            "schema_version": "deepseek-name-classification-trial-cost-v1",
            "model_requested": model,
            "connection_probe_included": True,
            "classified_occupation_count": TRIAL_SIZE,
            "saved_provider_response_count": len(raw_response_paths) + 1,
            "usage": total_usage,
            "estimated_cost_usd": total_cost,
            "stop_budget_usd": USD_BUDGET,
            "cost_scope": "Estimate computed from API-reported tokens and the DeepSeek Flash pricing window at each request; it is not a provider billing export.",
            "full_10998_linear_estimate_usd": total_cost * len(occupations) / TRIAL_SIZE,
        })
    print(json.dumps({
        "connection_valid": True,
        "model": model,
        "prompt_profile": PROMPT_PROFILE,
        "classified": TRIAL_SIZE,
        "status_counts": dict(Counter(item["status"] for item in completed)),
        "estimated_cost_usd": total_cost,
        "output_dir": str(OUT_DIR),
    }, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
