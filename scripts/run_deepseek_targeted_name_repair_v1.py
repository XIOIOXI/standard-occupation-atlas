"""Resumable DeepSeek review for screened name-only mapping risks."""
from __future__ import annotations
import json, os, sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from run_deepseek_name_classification_trial_v1 import (api_post_retry, canonical_base_url, estimate_cost, exclusive_json, output_content, read_dotenv, read_json, response_metadata, usage_summary)

ROOT = Path("data/processed/record_role_classification_v1")
RISK_PATH = ROOT / "targeted_name_repairs" / "name_only_targeted_repair_v1" / "risk_candidates.json"
TAXONOMY_PATH = ROOT / "catalog_mappings" / "taxonomy_embedding_texts_v1.json"
OUT = ROOT / "targeted_name_repairs" / "name_only_targeted_repair_v1" / "deepseek_review_batches"
BATCH_SIZE = 25
BUDGET_USD = 1.35
VALID_DECISIONS = {"keep", "reclassify", "fallback_review", "multi_role", "taxonomy_gap"}

def body(model, messages):
    return {"model": model, "messages": messages, "temperature": 0, "max_tokens": 5000, "response_format": {"type": "json_object"}, "thinking": {"type": "disabled"}, "stream": False}

def compact_taxonomy(rows):
    return [{"id": r["category_id"], "l1": r["level_1"], "l2": r["level_2"], "l3": r["level_3"], "boundary": r["matching_text"]} for r in rows]

def messages(taxonomy, batch):
    system = """你是职业目录质量复核助手。只根据职业名称、原始名称别名、当前目录归属和冻结目录判断；不得读取或假设公司、行业、招聘正文、技能。合理的核心职责匹配可以保留，不要求唯一权威答案。
重点：不得把机构运营归为一线照护、景区运营归为导游或技术售后归为美容服务；不得无依据补充编程语言、后端/前端、算法、服务对象或行业；专业要求、技术栈列表或单岗位多方向不等于多个职业。未注明语言的“翻译”不能确认英语口译。复合职责不自动是 multi_role，只有明确并列多个独立职业才是。
目录是唯一有效类别来源。每项返回一个决定：keep（当前合理）、reclassify（改到有效类别）、fallback_review（三级依据不足，target_category_id填最深可确认有效上级或null）、multi_role（确有多个独立职业，target_category_id=null）、taxonomy_gap（职业明确但目录不能承接，target_category_id=null）。
必须逐字回传 occupation_id。输出 JSON：{"results":[{"occupation_id":"...","decision":"...","target_category_id":"有效目录ID或null","reason":"针对该名称的具体理由"}]}。不要把风险标签本身当结论；相关候选仅供参考，可选择目录内其他类别。\n冻结目录：""" + json.dumps(taxonomy, ensure_ascii=False, separators=(",", ":"))
    user = "请逐项复核：" + json.dumps(batch, ensure_ascii=False, separators=(",", ":"))
    return [{"role":"system","content":system},{"role":"user","content":user}]

def validate(parsed, batch, valid_ids):
    rows = parsed.get("results") if isinstance(parsed, dict) else None
    if not isinstance(rows, list) or len(rows) != len(batch): raise ValueError("result count mismatch")
    expected = {x["standard_occupation_id"] for x in batch}; got = [x.get("occupation_id") for x in rows]
    if set(got) != expected or len(got) != len(set(got)): raise ValueError("occupation IDs mismatch")
    by_id = {x["standard_occupation_id"]: x for x in batch}
    normalized=[]
    for row in rows:
        decision=row.get("decision"); target=row.get("target_category_id"); reason=row.get("reason")
        if decision not in VALID_DECISIONS or not isinstance(reason,str) or not reason.strip(): raise ValueError("invalid decision/reason")
        if target is not None and target not in valid_ids: raise ValueError(f"unknown category {target!r}")
        if decision in {"multi_role","taxonomy_gap"} and target is not None: raise ValueError("terminal decision must be null")
        if decision == "reclassify" and target is None: raise ValueError("reclassify needs category")
        if decision == "keep": target = by_id[row["occupation_id"]]["current_category_id"]
        normalized.append({"occupation_id":row["occupation_id"],"decision":decision,"target_category_id":target,"reason":reason.strip()})
    return normalized

def main():
    dotenv=read_dotenv(Path('.env')); key=os.environ.get('DEEPSEEK_API_KEY') or dotenv.get('DEEPSEEK_API_KEY') or os.environ.get('OPENAI_API_KEY') or dotenv.get('OPENAI_API_KEY')
    if not key: raise RuntimeError('No configured DeepSeek credential')
    base=canonical_base_url(os.environ.get('DEEPSEEK_BASE_URL') or dotenv.get('DEEPSEEK_BASE_URL') or 'https://api.deepseek.com'); model=os.environ.get('DEEPSEEK_MODEL') or dotenv.get('DEEPSEEK_MODEL') or 'deepseek-flash'
    risk=read_json(RISK_PATH); tax=read_json(TAXONOMY_PATH); candidates=risk['candidates']; taxonomy=compact_taxonomy(tax['rows'])
    # fallback_review may deliberately retain a valid level-1 or level-2 path.
    valid_ids={x['id'] for x in taxonomy}
    valid_ids.update(x['l1'] for x in taxonomy)
    valid_ids.update(x['id'].rsplit('/', 1)[0] for x in taxonomy)
    OUT.mkdir(parents=True,exist_ok=True); costs=[]
    for n,start in enumerate(range(0,len(candidates),BATCH_SIZE),1):
        batch=candidates[start:start+BATCH_SIZE]; final=OUT/f'batch_{n:03d}_reviewed.json'
        if final.exists(): costs.append(read_json(final)['cost_estimate']); continue
        if sum(float(c['estimated_usd']) for c in costs)>=BUDGET_USD: raise RuntimeError(f'Repair API budget reached before batch {n}')
        m=messages(taxonomy,batch); request=body(model,m); inp=OUT/f'batch_{n:03d}_api_input.json'; rawpath=OUT/f'batch_{n:03d}_api_output.json'
        if not inp.exists(): exclusive_json(inp,{"endpoint":base+'/chat/completions',"model":model,"messages":m,"privacy_scope":"Occupation ID, names/aliases, current taxonomy placement and frozen taxonomy only."})
        observed=datetime.now(timezone.utc)
        if rawpath.exists(): raw=read_json(rawpath); attempts=0
        else:
            raw,attempts=api_post_retry(base,key,request)
            try:
                exclusive_json(rawpath,raw)
            except FileExistsError:
                raw=read_json(rawpath); attempts=0
        validation_retry_count=0
        for retry_index in range(3):
            try:
                reviewed=validate(json.loads(output_content(raw)),batch,valid_ids)
                break
            except ValueError:
                if retry_index == 2: raise
                validation_retry_count=retry_index+1
                retry_in=OUT/f'batch_{n:03d}_retry_{validation_retry_count:03d}_api_input.json'; retry_out=OUT/f'batch_{n:03d}_retry_{validation_retry_count:03d}_api_output.json'
                retry_messages=[m[0],{"role":"user","content":m[1]["content"]+'\n上一轮返回的 occupation_id 不完整或不逐字匹配。请重新返回本批全部 results；occupation_id 必须完全按输入复制，target_category_id 必须是冻结目录中的完整 ID 或 null。'}]
                retry_request=body(model,retry_messages)
                if not retry_in.exists(): exclusive_json(retry_in,{"endpoint":base+'/chat/completions',"model":model,"messages":retry_messages,"validation_retry":True})
                if retry_out.exists(): raw=read_json(retry_out)
                else:
                    raw,_=api_post_retry(base,key,retry_request); exclusive_json(retry_out,raw)
        usage=usage_summary(raw); cost=estimate_cost(usage,observed)
        try:
            exclusive_json(final,{"batch_number":n,"processing_method":"deepseek_api_name_only_targeted_repair","model_requested":model,"batch_input_count":len(batch),"response_metadata":response_metadata(raw),"attempts":attempts,"validation_retry_count":validation_retry_count,"usage":usage,"cost_estimate":cost,"results":reviewed})
        except FileExistsError:
            cost=read_json(final)["cost_estimate"]
        costs.append(cost)
    print(json.dumps({"reviewed":len(candidates),"batches":(len(candidates)+BATCH_SIZE-1)//BATCH_SIZE,"cost_estimated_usd":sum(float(c['estimated_usd']) for c in costs),"status_counts":dict(Counter(x['decision'] for p in OUT.glob('batch_*_reviewed.json') for x in read_json(p)['results']))},ensure_ascii=False))
if __name__=='__main__':
    try: main()
    except Exception as exc: print(f'ERROR: {type(exc).__name__}: {exc}',file=sys.stderr); raise
