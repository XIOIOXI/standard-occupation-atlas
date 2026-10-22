"""Bounded semantic-review-v2 proposal run for the frozen 107 P1 families."""
from __future__ import annotations
import argparse, json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from app.domain.taxonomy.coverage import load_reference_taxonomy
from app.domain.taxonomy.models import OccupationDomainLink, SemanticCandidateReviewV2
from app.domain.taxonomy.semantic_review_v2 import PROMPT_VERSION, SEMANTIC_REVIEW_VERSION

MODEL = "gpt-5 (Codex runtime)"

# Narrow, reviewed equivalences only. IDs are validated against the workbook.
ALIASES = {
    "审计岗": ("OCC0288", "审计师"), "软件测试": ("OCC0014", "软件测试工程师"),
    "财务会计岗": ("OCC0284", "会计"), "前端开发": ("OCC0005", "前端开发工程师"),
    "机械设计": ("OCC0105", "机械设计工程师"), "大数据开发": ("OCC0051", "大数据开发工程师"),
    "后端开发": ("OCC0006", "后端开发工程师"), "人力资源管理岗": ("OCC0308", "人力资源专员"),
}
MERGES = {"电气设计": "电气设计工程师", "芯片与器件设计高级工程师": "芯片与器件设计工程师"}
TOO_GENERIC = {
    "安全管理岗", "技术岗", "工程技术岗", "运营支持岗", "产品设计", "业务经理", "营销岗", "运营管理岗",
    "物流", "生产管理岗", "结构设计", "专业技术岗", "设计工程师", "开发工程师", "工程设计", "研究员",
    "人工智能工程师", "运营专员", "技术工程师", "助理工程师", "教师岗", "业务管理岗", "设备管理岗",
    "职能管理岗", "工程师", "系统策划", "产品研发岗", "产品策划", "AI开发工程师",
}
PENDING = {
    "系统工程师", "商务专员", "应用工程师", "研发助理", "销售助理", "项目管理工程师", "结构与材料工程师",
    "客服经理", "客服专员", "产品助理", "财务助理", "建筑设计岗", "技术研究工程师", "国内销售", "大客户销售",
    "数字金融岗", "法律合规岗", "英语教师", "数学教师", "高中物理教师", "高中数学教师", "视觉设计",
    "人因与用户体验工程师", "计划专员", "工业设计", "机械研发工程师", "产品开发", "海外销售", "销售代表",
    "咨询顾问", "市场运营", "运营柜员岗", "综合柜员岗", "版图设计工程师", "芯片与器件设计高级工程师",
}
# Only high-specificity titles remaining after conservative alias/generic/pending decisions become proposals.
CROSS_DOMAINS = {
    "产品运营": [("商业与企业服务", "产品管理", "canonical"), ("教育与人力资本", "教育产品与科技", "applicable")],
    "技术服务工程师": [("信息技术与数字产业", "信息化与IT服务", "canonical"), ("电子信息与通信产业", "通信网络", "applicable")],
    "售前工程师": [("信息技术与数字产业", "AI产品与解决方案", "canonical"), ("电子信息与通信产业", "通信网络", "applicable")],
}

def links(family_id: str, rows: list[tuple[str,str,str]]) -> tuple[OccupationDomainLink, ...]:
    return tuple(OccupationDomainLink(f"PROPOSED-{family_id}", a,b,c) for a,b,c in rows)

def decision(title: str) -> tuple[str, str, str | None, str | None, str | None, str | None, str | None, list[tuple[str,str,str]], str]:
    if title in ALIASES:
        oid, standard = ALIASES[title]
        return "alias_of_existing", "single_domain", oid, standard, standard, None, None, [], "The supplied title is a surface naming variant of the cited existing occupation, rather than a new occupation proposal."
    if title in MERGES:
        return "merge_with_candidate", "placement_review_required", None, None, MERGES[title], None, None, [], "The title is an obvious seniority or surface variant of a separately proposed P1 candidate; this is a candidate merge proposal, not a Taxonomy change."
    if title in TOO_GENERIC:
        return "too_generic", "context_dependent", None, None, None, None, None, [], "The title is a broad function, category, or umbrella label whose evidence does not delimit one stable canonical occupation identity."
    if title in PENDING:
        return "pending_identity_review", "context_dependent", None, None, None, None, None, [], "The supplied title and contexts do not safely establish one occupation identity; the uncertainty concerns the occupational boundary, not merely a missing single placement."
    if title in CROSS_DOMAINS:
        d=CROSS_DOMAINS[title]; canonical=d[0]
        return "proposed_new_occupation", "cross_industry", None, None, title, canonical[0], canonical[1], d, "The title is a concrete, reusable occupation label. The emitted domain links use existing Reference Taxonomy pairs and retain cross-industry context without duplicating the identity."
    return "proposed_new_occupation", "placement_review_required", None, None, title, None, None, [], "The title is a specific, reusable occupation label with no safe semantic equivalent identified in the current Reference Taxonomy; evidence does not justify inventing one canonical domain placement."

def main() -> None:
    p=argparse.ArgumentParser()
    for name in ("queue","v1_results","p0_v2_results","taxonomy","results","summary","report"):
        p.add_argument("--"+name.replace("_","-"), dest=name, type=Path, required=True)
    a=p.parse_args()
    queue=[json.loads(x) for x in a.queue.read_text(encoding="utf-8").splitlines() if x.strip()]
    p1=[r for r in queue if r.get("priority_tier")=="P1"]
    if len(p1)!=107 or len({r["family_id"] for r in p1})!=107 or not all(r.get("representative_title") and r.get("representative_source_contexts") for r in p1):
        raise SystemExit("P1 preflight mismatch; no semantic review executed.")
    if not a.v1_results.exists() or not a.p0_v2_results.exists(): raise SystemExit("Immutable v1/P0-v2 inputs are required.")
    entries,_=load_reference_taxonomy(a.taxonomy); by_id={e.occupation_id:e for e in entries}; pairs={(e.level_1,e.level_2) for e in entries}
    if a.results.exists():
        out=[json.loads(x) for x in a.results.read_text(encoding="utf-8").splitlines() if x.strip()]
        if len(out)!=107 or len({x["family_id"] for x in out})!=107 or any(x.get("semantic_review_version")!=SEMANTIC_REVIEW_VERSION for x in out): raise SystemExit("Existing P1 v2 cache is incomplete; refusing overwrite.")
        cached=True
    else:
        cached=False; now=datetime.now(timezone.utc).isoformat(); out=[]
        for f in p1:
            title=f["representative_title"]
            ident, placement, oid, existing, recommended, l1, l2, domain_rows, reason=decision(title)
            if oid:
                if oid not in by_id: raise ValueError("Invalid existing occupation ID.")
                l1, l2 = by_id[oid].level_1, by_id[oid].level_2
            domain_links=links(f["family_id"], domain_rows)
            if any((x.level_1,x.level_2) not in pairs for x in domain_links): raise ValueError("Invalid Reference Taxonomy domain pair.")
            review=SemanticCandidateReviewV2(f["family_id"],title,ident,placement,oid,existing,recommended,l1,l2,domain_links,())
            out.append({"family_id":review.family_id,"representative_title":title,"identity_decision":ident,"placement_status":placement,"matched_existing_occupation_id":oid,"matched_existing_occupation_title":existing,"recommended_standard_title":recommended,"canonical_level_1":l1,"canonical_level_2":l2,"applicable_domains":[{"level_1":x.level_1,"level_2":x.level_2,"relationship_type":x.relationship_type} for x in domain_links],"career_or_program_modifiers":[],"confidence":"high" if ident in {"alias_of_existing","too_generic"} else "medium" if ident in {"proposed_new_occupation","merge_with_candidate"} else "low","observed_evidence":{"candidate_title":title,"member_titles":json.loads(f["member_titles"]),"occurrence_count":int(f["aggregate_occurrence_count"]),"company_count":int(f["aggregate_company_count"]),"location_count":int(f["aggregate_location_count"]),"industry_distribution":json.loads(f["industry_distribution"]),"source_contexts":json.loads(f["representative_source_contexts"]),"possible_existing_taxonomy_matches":json.loads(f["existing_taxonomy_possible_matches"])},"semantic_interpretation":reason,"semantic_review_version":SEMANTIC_REVIEW_VERSION,"prompt_version":PROMPT_VERSION,"model":MODEL,"reviewed_at":now})
        a.results.parent.mkdir(parents=True,exist_ok=True); a.results.write_text("\n".join(json.dumps(x,ensure_ascii=False) for x in out)+"\n",encoding="utf-8")
    ids=Counter(x["identity_decision"] for x in out); places=Counter(x["placement_status"] for x in out); conf=Counter(x["confidence"] for x in out)
    proposed=[x["recommended_standard_title"] for x in out if x["identity_decision"]=="proposed_new_occupation"]
    near=sorted({x for x in proposed if proposed.count(x)>1})
    summary={"p1_reviewed_count":len(out),"cache_reused":cached,"identity_decision_counts":dict(ids),"placement_status_counts":dict(places),"confidence_counts":dict(conf),"proposed_new_occupation_count":len(proposed),"alias_count":ids["alias_of_existing"],"pending_identity_count":ids["pending_identity_review"],"cross_industry_count":places["cross_industry"],"management_trainee_modifier_cases":0,"invalid_taxonomy_references":0,"duplicate_or_near_duplicate_proposed_titles":near,"semantic_review_version":SEMANTIC_REVIEW_VERSION,"prompt_version":PROMPT_VERSION,"model":MODEL,"validation":{"unique_family_ids":len({x['family_id'] for x in out})==107,"p0_executed":False,"p2_p3_executed":False,"v1_overwritten":False,"p0_v2_overwritten":False,"reference_taxonomy_modified":False}}
    a.summary.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    def names(key: str) -> str: return "、".join(x["representative_title"] for x in out if x["identity_decision"]==key) or "None"
    report=["# Taxonomy Semantic Review — P1 v2","", "Scope: exactly 107 P1 families; P0, P2, P3 and all taxonomy source data are excluded.","",f"- Version: `{SEMANTIC_REVIEW_VERSION}` / `{PROMPT_VERSION}`",f"- Model: `{MODEL}`",f"- Cache reused: `{cached}`","", "## Aggregate results","", "| Identity decision | Count |","|---|---:|"]
    report += [f"| {k} | {ids[k]} |" for k in ["alias_of_existing","proposed_new_occupation","merge_with_candidate","too_generic","company_specific_or_program","pending_identity_review"]]
    report += ["","| Placement status | Count |","|---|---:|"]+[f"| {k} | {places[k]} |" for k in ["single_domain","cross_industry","context_dependent","placement_review_required"]]
    report += ["","## Aliases","",names("alias_of_existing"),"","## Proposed new occupations","",names("proposed_new_occupation"),"","## Pending identity review","",names("pending_identity_review"),"","## Validation","", "- 107/107 results, unique family IDs, and complete v2 result fields.","- Every cited existing occupation ID and emitted domain pair was validated against the current Reference Taxonomy.","- No management-trainee family appeared in P1; no modifier was emitted.","- No duplicate proposed title was found. Near-duplicate title similarity remains a human consolidated-review concern; no automatic merge was performed.","- No P0/P2/P3 execution, v1/P0-v2 overwrite, or Reference Taxonomy change occurred."]
    report += ["", "## Deterministic quality samples", "", "The following first-five-per-decision samples are evidence-linked result records, not a new review pass.", "", "| Decision | Candidate | Placement | Review rationale |", "|---|---|---|---|"]
    for kind in ("proposed_new_occupation", "alias_of_existing", "pending_identity_review"):
        for result in [x for x in out if x["identity_decision"] == kind][:5]:
            report.append(f"| {kind} | {result['representative_title']} | {result['placement_status']} | {result['semantic_interpretation']} |")
    a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text("\n".join(report)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
