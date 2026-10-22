"""Bounded v3.1 reasonable-primary remap for only prior review records.

Provider artifacts are append-only.  No old mapping or review file is read
for replacement, and no request is made for a non-review prior result.
"""
import hashlib, json, os, sys, time
from urllib.error import HTTPError
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_deepseek_name_classification_trial_v1 import (  # noqa: E402
    read_dotenv, api_post_retry, canonical_base_url, output_content,
    usage_summary, estimate_cost,
)
from sno_v31_mapping_contract import validate  # noqa: E402

OLD = ROOT / "data/processed/record_role_classification_v1/api_trials/deepseek_sno_v31_contract_200"
OUT = ROOT / "data/processed/record_role_classification_v1/api_trials/deepseek_sno_v31_reasonable_primary_36"
CATALOG = ROOT / "data/taxonomy/sno_v3_1/sno_occupation_catalog_v3.1.json"
SELECTION = ROOT / "data/processed/record_role_classification_v1/api_trials/sno_v31_200_selection.json"
VERSION = "sno-v3.1-reasonable-primary-v1"
BATCH_SIZE = 6
REVIEW_BATCH_SIZE = 3
BUDGET = 1.0


def load(p): return json.loads(p.read_text(encoding="utf-8"))
def atom(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    if path.exists(): return
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try: os.replace(tmp, path)
    except FileExistsError: tmp.unlink(missing_ok=True)

def levels(catalog):
    result = {}
    for l1 in catalog["taxonomy"]:
        result[l1["level_1_id"]] = "level_1"
        for l2 in l1["level_2"]:
            result[l2["level_2_id"]] = "level_2"
            for l3 in l2["level_3"]: result[l3["level_3_id"]] = "level_3"
    return result

def normalize(row):
    # Only contract-nullable empty strings are normalized; original raw stays separate.
    row = dict(row)
    for key in ("target_category_id", "target_level", "level_3_evidence"):
        if isinstance(row.get(key), str) and not row[key].strip(): row[key] = None
    return row

def prompt(directory):
    return """你是职业目录分类助手。仅依据标题与目录做“合理主归属”分类。
核心标准：不必证明类别唯一。只要所选位置有标题依据且符合目录范围，即可 mapped；其他合理位置可放 candidate_category_ids，不能因为存在歧义自动 review。
1. 先判断工作职能，再选择最直接、最符合通常职业含义的二级；仅在标题有细分证据时选三级。
2. 可使用职业名称通常含义与专业常识，但不能虚构招聘职责、公司背景或未写出的场景。
3. 没有三级依据时 mapped 到明确二级；职能明确而方向未知时，使用适用的通用二级。
4. 只有标题完全没有职能线索且没有任何有依据的合理位置，才用 review；职业明确但目录没有范围才用 taxonomy_gap。
5. 管培、培训、储备、助理等是身份/修饰，不妨碍按标题已明确的专业职能归类；仅身份而没有职能才可能 review。
6. multi_role、non_role_text 保持该状态，不强塞目录；本阶段不拆分。
7. 每条只允许一个正式 target_category_id。mapped 的候选不参与正式归属。不得使用停用/不存在 ID；三级必须属于其二级。
输出严格 JSON：{"results":[{"occupation_id":string,"status":"mapped|review|taxonomy_gap|multi_role|non_role_text","target_category_id":string或null,"target_level":"level_2|level_3"或null,"candidate_category_ids":string数组,"title_evidence":string,"level_3_evidence":string或null,"reason":string}]}。
mapped 必须唯一 target；review 未确认候选仅放 candidate_category_ids、target 只能是已确认公共父级或 null；三级必须给出直接细分证据。目录：""" + json.dumps(directory, ensure_ascii=False, separators=(",", ":"))

def review_prompt(directory):
    return """你是独立复核器，检查已有“合理主归属”而不是要求唯一答案。当前归属只要有标题依据且符合目录范围，即使其他位置也合理，也应判 pass。只有明显违反范围、忽略标题明确职能、或有更直接的专门类别时才 correction_required；完全无可用职能线索才 unresolved；目录实际缺范围才 taxonomy_issue。不能以“不能唯一确定”作为拒绝理由。检查三级是否过细、候选是否被当成目标。只输出合法 JSON 对象，每项输出 occupation_id,verdict(pass|correction_required|unresolved|taxonomy_issue),suggested_target_category_id,issue。目录：""" + json.dumps(directory, ensure_ascii=False, separators=(",", ":"))

def compact_review_directory(directory):
    """All L1/L2 sibling scopes; individual current L3 evidence is in each record."""
    result=[]
    for l1 in directory:
        result.append({"level_1_id":l1["level_1_id"],"name":l1["name"],"level_2":[
            {"level_2_id":l2["level_2_id"],"name":l2["name"],"scope":l2.get("scope"),
             "level_3": []}
            for l2 in l1["level_2"]]})
    return result

def request(model, messages):
    return {"model": model, "messages": messages, "temperature": 0, "max_tokens": 5000,
            "response_format": {"type": "json_object"}, "thinking": {"type": "disabled"}}

def existing_cost():
    total = 0.0
    for p in list(OUT.glob("map_*_parsed.json")) + list(OUT.glob("review_*_parsed.json")):
        total += float(load(p).get("cost", {}).get("estimated_usd", 0))
    return total

def call_or_load(kind, number, body, base, key, catalog_levels, retired, batch):
    parsed = OUT / f"{kind}_{number:03d}_parsed.json"; rawp = OUT / f"{kind}_{number:03d}_raw_response.json"; req = OUT / f"{kind}_{number:03d}_request.json"
    if parsed.exists(): return load(parsed)
    atom(req, {"version": VERSION, "endpoint": base + "/chat/completions", "body_without_key": body,
               "catalog_sha256": hashlib.sha256(CATALOG.read_bytes()).hexdigest()})
    invalid_path = OUT / f"{kind}_{number:03d}_invalid_model_output.json"
    if rawp.exists(): raw, attempts = load(rawp), 0
    elif kind.startswith("review") and invalid_path.exists(): raw, attempts = load(invalid_path)["raw"], 0
    else:
        if existing_cost() >= BUDGET: raise RuntimeError("$1 budget reached before new request")
        observed = datetime.now(timezone.utc)
        try:
            raw, attempts = api_post_retry(base, key, body)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            atom(OUT / f"{kind}_{number:03d}_http_error.json", {"code":exc.code,"reason":str(exc),"provider_body":detail})
            raise RuntimeError(f"provider HTTP {exc.code}: {detail}") from exc
    observed = datetime.fromtimestamp(raw["created"], timezone.utc) if isinstance(raw.get("created"), (int,float)) else datetime.now(timezone.utc)
    parsed_content = json.loads(output_content(raw))
    result_key = "records" if kind.startswith("review") else "results"
    if result_key not in parsed_content:
        atom(OUT / f"{kind}_{number:03d}_invalid_model_output.json", {"raw": raw, "parsed_content": parsed_content})
        raise ValueError(f"{kind} response lacks results")
    rows = [normalize(x) for x in parsed_content[result_key]]
    # A missing contract field is provider-format failure, not something this
    # program is permitted to invent. Preserve the first raw response and make
    # one separately recorded repair request for this exact batch.
    contract_fields = {"occupation_id", "status", "target_category_id", "target_level", "candidate_category_ids", "title_evidence", "level_3_evidence", "reason"}
    if kind == "map" and any(set(x) != contract_fields for x in rows):
        repair_req = OUT / f"{kind}_{number:03d}_format_repair_request.json"
        repair_raw = OUT / f"{kind}_{number:03d}_format_repair_raw_response.json"
        repair_body = dict(body)
        repair_body["messages"] = list(body["messages"]) + [{"role": "user", "content": "上次输出缺少合同字段。请重新输出本批完整 results；每一项必须逐字包含 occupation_id,status,target_category_id,target_level,candidate_category_ids,title_evidence,level_3_evidence,reason，所有可空字段用 null，不能省略字段。"}]
        atom(repair_req, {"version": VERSION, "reason": "raw response omitted required contract fields", "body_without_key": repair_body})
        if repair_raw.exists(): raw, repair_attempts = load(repair_raw), 0
        else:
            if existing_cost() >= BUDGET: raise RuntimeError("$1 budget reached before format repair")
            raw, repair_attempts = api_post_retry(base, key, repair_body); atom(repair_raw, raw)
        attempts += repair_attempts
        rows = [normalize(x) for x in json.loads(output_content(raw))["results"]]
    expected = {x["occupation_id"] for x in batch}
    if len(rows) != len(batch) or {x.get("occupation_id") for x in rows} != expected: raise ValueError(f"{kind} output IDs incomplete")
    if kind == "map":
        failures=[]
        for x in rows:
            try: validate({"sample_id": x["occupation_id"], **{k:x[k] for k in ("status","target_category_id","candidate_category_ids","target_level","reason","level_3_evidence")}}, catalog_levels, retired)
            except Exception as e: failures.append({"occupation_id":x.get("occupation_id"),"error":str(e)})
        if failures: raise ValueError(f"contract failures: {failures}")
    payload={"raw_response_file":rawp.name,"results":rows,"usage":usage_summary(raw),"cost":estimate_cost(usage_summary(raw),observed),"attempts":attempts,"post_processing":"nullable_empty_string_to_null"}
    atom(parsed,payload); return payload

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    lock = OUT / ".run.lock"
    try: fd=os.open(lock, os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError: raise RuntimeError(f"active lock: {lock}")
    os.write(fd, str(os.getpid()).encode()); os.close(fd)
    try:
        catalog=load(CATALOG); lv=levels(catalog); retired=set(catalog["retired_category_ids"])
        old=load(OLD / "normalized_contract_results.json")["results"]
        titles={x["standard_occupation_id"]:x["standard_name"] for x in load(SELECTION)["occupations"]}
        selected=[{"occupation_id":x["occupation_id"],"title":titles[x["occupation_id"]],"previous":x} for x in old if x["status"]=="review"]
        if len(selected)!=36: raise ValueError(f"expected 36 prior reviews, got {len(selected)}")
        atom(OUT/"manifest.json", {"version":VERSION,"source_run":str(OLD),"selected_count":36,"selection_rule":"only status=review from normalized contract-200 results","taxonomy_version":catalog["taxonomy_version"],"taxonomy_sha256":hashlib.sha256(CATALOG.read_bytes()).hexdigest(),"occupations":selected})
        dot=read_dotenv(ROOT/".env"); key=os.getenv("DEEPSEEK_API_KEY") or dot.get("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or dot.get("OPENAI_API_KEY")
        if not key: raise RuntimeError("missing API key")
        base=canonical_base_url(os.getenv("DEEPSEEK_BASE_URL") or dot.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com"); model=os.getenv("DEEPSEEK_MODEL") or dot.get("DEEPSEEK_MODEL") or "deepseek-flash"
        mapped=[]; reviewed=[]
        for i in range(0,len(selected),BATCH_SIZE):
            n=i//BATCH_SIZE+1; batch=selected[i:i+BATCH_SIZE]
            body=request(model,[{"role":"system","content":prompt(catalog["taxonomy"])},{"role":"user","content":json.dumps({"occupations":[{"occupation_id":x["occupation_id"],"title":x["title"]} for x in batch]},ensure_ascii=False)}])
            m=call_or_load("map",n,body,base,key,lv,retired,batch); mapped+=m["results"]
        mapby={x["occupation_id"]:x for x in mapped}; review_directory=compact_review_directory(catalog["taxonomy"])
        for i in range(0,len(selected),REVIEW_BATCH_SIZE):
            n=i//REVIEW_BATCH_SIZE+1; batch=selected[i:i+REVIEW_BATCH_SIZE]
            review_items=[{"occupation_id":x["occupation_id"],"title":x["title"],"current":mapby[x["occupation_id"]]} for x in batch]
            rbody=request(model,[{"role":"system","content":review_prompt(review_directory)},{"role":"user","content":json.dumps({"records":review_items},ensure_ascii=False)}])
            reviewed += call_or_load("review_v3",n,rbody,base,key,lv,retired,batch)["results"]
        oldby={x["occupation_id"]:x for x in old}; revby={x["occupation_id"]:x for x in reviewed}
        comparison=[]
        for x in mapped:
            comparison.append({"occupation_id":x["occupation_id"],"title":titles[x["occupation_id"]],"previous":oldby[x["occupation_id"]],"reasonable_primary":x,"ai_reasonableness_review":revby.get(x["occupation_id"])})
        atom(OUT/"review_to_reasonable_primary_comparison.json", {"count":len(comparison),"records":comparison})
        merged=[x for x in old if x["status"]!="review"]+mapped
        atom(OUT/"merged_200_results.json", {"count":len(merged),"results":merged,"status_counts":dict(Counter(x["status"] for x in merged))})
        costs=[]
        for p in list(OUT.glob("map_*_parsed.json"))+list(OUT.glob("review_v3_*_parsed.json")): costs.append(load(p))
        usage=Counter(); [usage.update(x["usage"]) for x in costs]
        report={"version":VERSION,"new_api_calls":len(costs),"new_usage":dict(usage),"new_estimated_usd":sum(x["cost"]["estimated_usd"] for x in costs),"budget_usd":BUDGET,"mapping_status_counts":dict(Counter(x["status"] for x in mapped)),"ai_reasonableness_review_counts":dict(Counter(x.get("verdict") for x in reviewed)),"merged_status_counts":dict(Counter(x["status"] for x in merged)),"note":"AI pass means no clear unreasonable placement found under reasonable-primary standard; it is not a unique-answer accuracy measure."}
        atom(OUT/"cost_and_summary.json",report)
        print(json.dumps(report,ensure_ascii=False))
    finally: lock.unlink(missing_ok=True)
if __name__ == "__main__": main()
