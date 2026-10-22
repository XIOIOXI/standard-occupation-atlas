"""One bounded DeepSeek supplement for the existing SNO v3.1 unclassified queue.

It never re-runs existing mapped title groups.  Raw responses, parsed results,
costs and a merged *copy* of final.json are saved under a new output directory.
"""
from __future__ import annotations

import hashlib, json, os, sys, time, urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_deepseek_name_classification_trial_v1 import (api_post_retry, canonical_base_url, estimate_cost, output_content, read_dotenv, response_metadata, usage_summary)
from sno_v31_mapping_contract import validate

REAL = ROOT / "data/processed/record_role_classification_v1/full_drafts/sno_v31_reasonable_primary_v4_real"
DISPLAY = ROOT / "data/processed/record_role_classification_v1/full_drafts/sno_v31_reasonable_primary_v4_display"
OUT = ROOT / "data/processed/record_role_classification_v1/full_drafts/sno_v31_reasonable_primary_v4_supplement_v1"
CAT = ROOT / "data/taxonomy/sno_v3_1/sno_occupation_catalog_v3.1.json"
BUDGET = 1.0
BATCH = 25
PROMPT_VERSION = "sno-v3.1-reasonable-primary-supplement-v1"

def load(path): return json.loads(Path(path).read_text(encoding="utf8"))
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def put(path, value, replace=False):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not replace: return
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    for attempt in range(8):
        try:
            os.replace(temp, path)
            return
        except PermissionError:
            if attempt == 7: raise
            time.sleep(0.2 * (attempt + 1))
def normalize(row):
    row = dict(row)
    for key in ("target_category_id", "target_level", "level_3_evidence"):
        if isinstance(row.get(key), str) and not row[key].strip(): row[key] = None
    return row
def level_index(catalog):
    result = {}
    for l1 in catalog["taxonomy"]:
        for l2 in l1["level_2"]:
            result[l2["level_2_id"]] = "level_2"
            for l3 in l2["level_3"]: result[l3["level_3_id"]] = "level_3"
    return result
def prompt(taxonomy):
    return """你在补充映射一批此前未分类的招聘岗位标题。采用合理主归属：有标题依据且符合目录范围即可 mapped，不要求唯一答案。先识别核心职能，再选最直接二级；有明确细分证据才选三级，否则停在二级。允许理解职业名称通常含义，不得虚构职责。管培、培训、储备、助理、实习不替代已明确专业职能。多个合理位置时选最直接者，其余可放候选；不能仅因无法唯一确定而 review。完全没有职能线索时 review；职业明确但目录无合理范围时 taxonomy_gap。\n输出 JSON 对象 {results:[...]}，每项必须有 occupation_id,status(mapped|review|taxonomy_gap|multi_role|non_role_text),target_category_id(合法二级或三级 ID 或 null),target_level(level_2|level_3|null),candidate_category_ids(合法 ID 数组),title_evidence,level_3_evidence(仅三级时的标题证据，否则 null),reason。mapped 只能有一个正式目标；review 的候选不能作为 target；非 mapped 的 target 必须 null；不得使用停用 ID或补造三级证据。\n目录：""" + json.dumps(taxonomy, ensure_ascii=False, separators=(",", ":"))
def review_prompt(taxonomy):
    return """针对已有主归属做合理性复核。当前归属有标题依据、符合范围时 pass，即使其他位置也合理；仅明显违反范围、忽略直接类别或三级过细时 correction_required。完全缺乏职能线索时 unresolved；目录确实缺项或冲突 taxonomy_issue。不要因答案不唯一而拒绝。输出 JSON {records:[{occupation_id,verdict(pass|correction_required|unresolved|taxonomy_issue),suggested_target_category_id,issue}]}。合法 ID 是否存在以程序目录为准。目录：""" + json.dumps(taxonomy, ensure_ascii=False, separators=(",", ":"))
def request(system, key, payload):
    return {"model":"deepseek-flash", "messages":[{"role":"system","content":system},{"role":"user","content":json.dumps(payload,ensure_ascii=False)}], "response_format":{"type":"json_object"}, "thinking":{"type":"disabled"}, "temperature":0, "max_tokens":6000}
def ledger():
    p=OUT/"ledger.json"
    if not p.exists(): put(p,{"budget_usd":BUDGET,"spent_usd":0,"responses":[]})
    return load(p)
def save_ledger(value):
    p=OUT/"ledger.json"; temp=p.with_suffix(".tmp"); temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    for attempt in range(8):
        try:
            os.replace(temp,p); return
        except PermissionError:
            if attempt == 7: raise
            time.sleep(0.2 * (attempt + 1))
def check_balance(key, base):
    """Persist a redacted provider-balance check; never record the credential."""
    endpoint=base.removesuffix("/v1") + "/user/balance"
    result={"checked_at":datetime.now(timezone.utc).isoformat(),"endpoint":endpoint,"ok":False}
    try:
        req=urllib.request.Request(endpoint,headers={"Authorization":f"Bearer {key}"})
        with urllib.request.urlopen(req,timeout=20) as response:
            result.update({"ok":True,"http_status":response.status,"response":json.loads(response.read().decode("utf8"))})
    except Exception as exc:
        result["error_type"]=type(exc).__name__; result["error"]=str(exc)
    put(OUT/"balance_check.json",result,replace=True)
    return result
def call(stage, number, req, ids, key, base):
    raw_path=OUT/stage/f"{number:04d}.raw.json"; parsed_path=OUT/stage/f"{number:04d}.parsed.json"; request_path=OUT/stage/f"{number:04d}.request.json"
    if parsed_path.exists(): return load(parsed_path)["results"]
    put(request_path,{"prompt_version":PROMPT_VERSION,"body_without_key":req,"input_ids":ids})
    book=ledger()
    if raw_path.exists(): raw=load(raw_path); attempts=0
    else:
        # Reserve a deliberately conservative amount before a new request.
        if book["spent_usd"] + 0.02 > BUDGET: raise RuntimeError("budget_stop_before_request")
        raw, attempts = api_post_retry(base,key,req)
        put(raw_path,raw,replace=True)
    usage=usage_summary(raw); cost=estimate_cost(usage,datetime.now(timezone.utc))
    if not any(x["stage"]==stage and x["batch"]==number for x in book["responses"]):
        book["spent_usd"] += cost["estimated_usd"]
        book["responses"].append({"stage":stage,"batch":number,"usage":usage,"cost_estimate":cost,"raw_file":raw_path.name})
        save_ledger(book)
    payload=json.loads(output_content(raw)); envelope="records" if stage=="review" else "results"
    rows=payload.get(envelope)
    if not isinstance(rows,list):
        put(OUT/"failed"/f"{stage}_{number:04d}.json",{"ids":ids,"error":"invalid_response_envelope","raw_file":raw_path.name})
        put(parsed_path,{"results":[],"usage":usage,"cost_estimate":cost,"parser_failure":True},replace=True); return []
    rows=[normalize(x) for x in rows]
    put(parsed_path,{"results":rows,"usage":usage,"cost_estimate":cost,"response_metadata":response_metadata(raw),"attempts":attempts},replace=True)
    return rows
def finalize_from_saved(final, levels, retired, unresolved, manifest):
    """Finalize strictly from persisted response IDs, never from a rebuilt queue.

    This protects resume safety when the display projection has already changed.
    """
    persisted_input_ids=[]
    for request_file in sorted((OUT/"map").glob("*.request.json")):
        body=load(request_file).get("body_without_key",{})
        try:
            payload=json.loads(body["messages"][1]["content"])
            persisted_input_ids.extend(x["occupation_id"] for x in payload.get("occupations",[]))
        except (KeyError, TypeError, json.JSONDecodeError):
            pass
    persisted_unique=set(persisted_input_ids)
    manifest["persisted_request_scope"]={"input_rows":len(persisted_input_ids),"unique_occupation_ids":len(persisted_unique),"title_groups":sum(not x.startswith("CR-") for x in persisted_unique),"child_roles":sum(x.startswith("CR-") for x in persisted_unique)}
    mapped={}
    for parsed in sorted((OUT/"map").glob("*.parsed.json")):
        for row in load(parsed).get("results",[]):
            row=normalize(row)
            try:
                validate({"sample_id":row["occupation_id"],**{k:row.get(k) for k in ("status","target_category_id","candidate_category_ids","target_level","reason","level_3_evidence")}},levels,retired)
                mapped[row["occupation_id"]]=row
            except Exception as exc:
                put(OUT/"failed"/f"map_validation_{row.get('occupation_id','unknown')}.json",{"result":row,"error":str(exc)},replace=True)
    reviews={}
    for parsed in sorted((OUT/"review").glob("*.parsed.json")):
        reviews.update({row.get("occupation_id"):row for row in load(parsed).get("results",[])})
    merged=json.loads(json.dumps(final)); changes=[]
    for record in merged["records"]:
        oid=record["title_group_id"]; result=mapped.get(oid); review=reviews.get(oid)
        if result and review and review.get("verdict")=="pass" and result.get("status")=="mapped":
            before=record["effective_result"]; record["supplement_v1"]={"previous_effective_result":before,"mapping":result,"review":review}; record["effective_result"]=result; record["processing_state"]="supplement_mapped"; record["display_eligibility"]="eligible"; changes.append({"occupation_id":oid,"kind":"title_group","from":before,"to":result})
    child_by={x["occupation_id"]:x for x in merged["child_mappings"]}
    for oid,result in mapped.items():
        if oid in child_by and reviews.get(oid,{}).get("verdict")=="pass" and result.get("status")=="mapped":
            before=dict(child_by[oid]); child_by[oid].update(result); child_by[oid]["supplement_v1"]={"previous":before,"review":reviews[oid]}; changes.append({"occupation_id":oid,"kind":"child_role","from":before,"to":result})
    for record in merged["records"]:
        oid=record["title_group_id"]
        if oid not in unresolved or oid not in reviews: continue
        review=reviews[oid]; before=record.get("effective_result"); audit_entry={"previous_effective_result":before,"review":review}; suggestion=review.get("suggested_target_category_id")
        if review.get("verdict")=="correction_required" and suggestion in levels:
            corrected=dict(before or {}); corrected.update({"status":"mapped","target_category_id":suggestion,"target_level":levels[suggestion]})
            if levels[suggestion]!="level_3": corrected["level_3_evidence"]=None
            try:
                validate({"sample_id":oid,**{k:corrected.get(k) for k in ("status","target_category_id","candidate_category_ids","target_level","reason","level_3_evidence")}},levels,retired)
                record["effective_result"]=corrected; audit_entry["applied_correction"]=True; changes.append({"occupation_id":oid,"kind":"unresolved_mapped_review","from":before,"to":corrected})
            except Exception as exc: audit_entry["correction_not_applied"]=str(exc)
        record["supplement_v1_unresolved_review"]=audit_entry
    put(OUT/"merged_final.json",merged,replace=True)
    put(OUT/"comparison.json",{"changes":changes,"still_unmapped":[{"occupation_id":oid,"result":row} for oid,row in mapped.items() if row.get("status")!="mapped" or reviews.get(oid,{}).get("verdict")!="pass"],"review_results":reviews},replace=True)
    put(OUT/"report.json",{"manifest":manifest,"partial_finalize":True,"response_id_source":"persisted_map_and_review_parsed_files","actual_mapping_responses":len(mapped),"mapped_after_review":len(changes),"status_counts":dict(Counter(x.get("status") for x in mapped.values())),"review_counts":dict(Counter(x.get("verdict") for x in reviews.values())),"unreviewed_mapping_results":len([oid for oid in mapped if oid not in reviews]),"ledger":ledger()},replace=True)
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    partial_finalize=os.getenv("SNO_SUPPLEMENT_FINALIZE_PARTIAL")=="1"
    catalog=load(CAT); levels=level_index(catalog); retired=set(catalog.get("retired_category_ids",[]))
    final=load(REAL/"final.json"); queue=load(DISPLAY/"unclassified_queue_v31.json"); audit=load(DISPLAY/"review_queue_audit_v31.json")
    title={}; child={}
    for item in queue["items"]:
        reason=item.get("queue_reason")
        if reason in {"multi_source_span_unverified","mapping_validation_failure"}: continue
        oid=item["standard_occupation_id"]
        target=child if oid.startswith("CR-") else title
        target.setdefault(oid,{"occupation_id":oid,"title":item["label"],"queue_reasons":set(),"source_record_ids":item.get("source_record_ids",[]),"source_record_role_ids":item.get("source_record_role_ids",[])})["queue_reasons"].add(reason)
    unresolved={x["title_group_id"]:x for x in audit.get("review_unresolved_effective_mapped",[])}
    manifest={"prompt_version":PROMPT_VERSION,"taxonomy_version":catalog["taxonomy_version"],"catalog_sha256":sha(CAT),"source_final":str(REAL/"final.json"),"source_final_sha256":sha(REAL/"final.json"),"budget_usd":BUDGET,"selection_counts":{"title_groups":len(title),"child_roles":len(child),"unresolved_mapped_review":len(unresolved),"locally_held_span":sum(x.get("queue_reason")=="multi_source_span_unverified" for x in queue["items"]),"locally_held_validation":sum(x.get("queue_reason")=="mapping_validation_failure" for x in queue["items"])}}
    put(OUT/"manifest.json",manifest,replace=True)
    selection=[{**x,"queue_reasons":sorted(x["queue_reasons"])} for x in [*title.values(),*child.values()]]
    put(OUT/"selection.json",{"items":selection,"unresolved_mapped_review":list(unresolved.values())},replace=True)
    dot=read_dotenv(ROOT/".env"); key=os.getenv("DEEPSEEK_API_KEY") or dot.get("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or dot.get("OPENAI_API_KEY")
    if not key: raise RuntimeError("missing DeepSeek API key")
    base=canonical_base_url(os.getenv("DEEPSEEK_BASE_URL") or dot.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com")
    # A failed balance endpoint is recorded but does not discard already-authorized
    # work; per-request reservation below remains the hard budget gate.
    if not partial_finalize:
        check_balance(key,base)
    else:
        # Do not rebuild batch inputs from a projection that this run may have
        # already changed.  The saved response IDs are the authoritative scope.
        finalize_from_saved(final,levels,retired,unresolved,manifest)
        return
    all_items=[*title.values(),*child.values()]; mapped={}
    for number,start in enumerate(range(0,len(all_items),BATCH),1):
        batch=all_items[start:start+BATCH]; rows=call("map",number,request(prompt(catalog["taxonomy"]),key,{"occupations":[{"occupation_id":x["occupation_id"],"title":x["title"]} for x in batch]}),[x["occupation_id"] for x in batch],key,base)
        for row in rows:
            try: validate({"sample_id":row["occupation_id"],**{k:row.get(k) for k in ("status","target_category_id","candidate_category_ids","target_level","reason","level_3_evidence")}},levels,retired); mapped[row["occupation_id"]]=row
            except Exception as exc: put(OUT/"failed"/f"map_validation_{row.get('occupation_id','unknown')}.json",{"result":row,"error":str(exc)})
    review_inputs=[]
    for item in all_items:
        if item["occupation_id"] in mapped: review_inputs.append({"occupation_id":item["occupation_id"],"title":item["title"],"current":mapped[item["occupation_id"]]})
    for gid,item in unresolved.items(): review_inputs.append({"occupation_id":gid,"title":item["title"],"current":item["effective_result"],"existing_unresolved_mapped":True})
    reviews={}
    for number,start in enumerate(range(0,len(review_inputs),BATCH),1):
        batch=review_inputs[start:start+BATCH]
        parsed=OUT/"review"/f"{number:04d}.parsed.json"
        if partial_finalize and not parsed.exists():
            put(OUT/"failed"/f"review_{number:04d}_not_called_payment_required.json",{"stage":"review","batch":number,"input_ids":[x["occupation_id"] for x in batch],"reason":"provider_returned_HTTP_402_Payment_Required; no new request sent during partial finalize"},replace=True)
            continue
        rows=call("review",number,request(review_prompt(catalog["taxonomy"]),key,{"records":batch}),[x["occupation_id"] for x in batch],key,base)
        reviews.update({x.get("occupation_id"):x for x in rows})
    # Apply only validated, reviewed supplement results to a copy of final.json.
    merged=json.loads(json.dumps(final)); changes=[]
    for record in merged["records"]:
        oid=record["title_group_id"]
        result=mapped.get(oid)
        review=reviews.get(oid)
        if result and review and review.get("verdict")=="pass" and result.get("status")=="mapped":
            before=record["effective_result"]; record["supplement_v1"]={"previous_effective_result":before,"mapping":result,"review":review}; record["effective_result"]=result; record["processing_state"]="supplement_mapped"; record["display_eligibility"]="eligible"; changes.append({"occupation_id":oid,"kind":"title_group","from":before,"to":result})
    child_by={x["occupation_id"]:x for x in merged["child_mappings"]}
    for oid,result in mapped.items():
        if oid in child_by and reviews.get(oid,{}).get("verdict")=="pass" and result.get("status")=="mapped":
            before=dict(child_by[oid]); child_by[oid].update(result); child_by[oid]["supplement_v1"]={"previous":before,"review":reviews[oid]}; changes.append({"occupation_id":oid,"kind":"child_role","from":before,"to":result})
    # The 15 pre-existing unresolved-but-mapped title groups are deliberately
    # reviewed separately.  Preserve a reasonable current assignment on pass or
    # unresolved; apply only a programmatically valid correction recommendation.
    for record in merged["records"]:
        oid=record["title_group_id"]
        if oid not in unresolved: continue
        review=reviews.get(oid)
        if not review: continue
        before=record.get("effective_result")
        audit_entry={"previous_effective_result":before,"review":review}
        suggestion=review.get("suggested_target_category_id")
        if review.get("verdict")=="correction_required" and suggestion in levels:
            corrected=dict(before or {})
            corrected.update({"status":"mapped","target_category_id":suggestion,"target_level":levels[suggestion]})
            if levels[suggestion]!="level_3": corrected["level_3_evidence"]=None
            try:
                validate({"sample_id":oid,**{k:corrected.get(k) for k in ("status","target_category_id","candidate_category_ids","target_level","reason","level_3_evidence")}},levels,retired)
                record["effective_result"]=corrected; audit_entry["applied_correction"]=True
                changes.append({"occupation_id":oid,"kind":"unresolved_mapped_review","from":before,"to":corrected})
            except Exception as exc:
                audit_entry["correction_not_applied"]=str(exc)
        record["supplement_v1_unresolved_review"]=audit_entry
    put(OUT/"merged_final.json",merged,replace=True)
    put(OUT/"comparison.json",{"changes":changes,"still_unmapped":[x for x in selection if x["occupation_id"] not in mapped or mapped[x["occupation_id"]].get("status")!="mapped"],"review_results":reviews},replace=True)
    put(OUT/"report.json",{"manifest":manifest,"partial_finalize":partial_finalize,"actual_mapping_responses":len(mapped),"mapped_after_review":len(changes),"status_counts":dict(Counter(x.get("status") for x in mapped.values())),"review_counts":dict(Counter(x.get("verdict") for x in reviews.values())),"unreviewed_mapping_results":len([oid for oid in mapped if oid not in reviews]),"ledger":ledger()},replace=True)
if __name__=="__main__": main()
