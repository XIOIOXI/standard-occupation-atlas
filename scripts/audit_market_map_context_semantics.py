"""Read-only audit of Market Map context semantics; no pipeline or API calls."""
from __future__ import annotations
import csv, json, re, unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GROUPS = ROOT / "data/processed/job_groups_v2/job_groups.jsonl"
HIERARCHY = ROOT / "data/processed/job_market_intelligence/market_map/display_hierarchy.json"
RAW = ROOT / "data/raw/26年【实习_春招_秋招】汇总新表（持续更新）-朱迪学姐_校招汇总表（优先）_秋招+补录.csv"
OUT = ROOT / "docs/reports/market-map-context-semantics-audit.json"

def norm(value: str | None) -> str:
    text = unicodedata.normalize("NFKC", value or "").casefold()
    return re.sub(r"[\s\-_/·]", "", text).strip("，,。.;；:：")

def records(rows):
    return len({rid for row in rows for rid in row["source_recruitment_record_ids"]})

def main():
    groups = [json.loads(line) for line in GROUPS.read_text(encoding="utf-8").splitlines() if line]
    hierarchy = json.loads(HIERARCHY.read_text(encoding="utf-8"))
    with RAW.open(encoding="utf-8-sig", newline="") as stream:
        raw_rows = list(csv.DictReader(stream))
    enterprise_types = {norm(row.get("企业类型")) for row in raw_rows if norm(row.get("企业类型"))}
    raw_categories = defaultdict(set)
    for row in raw_rows:
        raw_categories[norm(row.get("行业类别"))].add(row.get("行业类别") or "")

    by_context = defaultdict(list)
    for group in groups:
        by_context[group["industry_domain_context"]].append(group)
    context_nodes = {
        node["source_context"]: node
        for nodes in hierarchy["levels"]["level_1"]["nodes_by_parent"].values()
        for node in nodes
    }
    dimensions = defaultdict(list)
    ownership_values = enterprise_types - {"其他", "unknown"}
    for label, rows in sorted(by_context.items()):
        if label.startswith("l1:"):
            semantic = "Industry / Domain"
            rule = "industry_category matched exactly one frozen INDUSTRY_CONTEXT_TO_LEVEL_1 target"
        else:
            raw = label.removeprefix("raw:")
            tokens = raw.split(",")
            if raw == "unknown":
                semantic, rule = "Unknown / Ambiguous", "industry_category missing after deterministic normalization"
            elif len(tokens) > 1 and any(token in enterprise_types for token in tokens):
                semantic, rule = "Unknown / Ambiguous", "raw industry_category is a composite including an enterprise-type token; no governed split exists"
            elif raw in ownership_values:
                semantic, rule = "Organization / Ownership Type", "raw industry_category exactly equals a normalized 企业类型 value"
            else:
                semantic, rule = "Recruitment Source Category", "unmapped normalized 行业类别 value retained with raw: prefix"
        node = context_nodes.get(label, {})
        dimensions[semantic].append({
            "context_label": label, "display_label": label.split(":", 1)[-1], "job_group_count": len(rows),
            "distinct_recruitment_record_count": records(rows), "occupation_count": node.get("occupation_count"),
            "source_industry_category_values": sorted(raw_categories.get(label.removeprefix("raw:"), [])), "rule": rule,
        })
    dimensions["Occupation-related category"] = []
    result = {
        "audit_version": "market-map-context-semantics-v1", "read_only": True, "api_calls": 0, "llm_calls": 0,
        "source_column_semantics": {"行业类别": "context input", "企业类型": "ownership metadata used only for deterministic audit comparison"},
        "transformation": "run_job_grouping_v1.industry_key: one frozen mapping target => l1:<target>; otherwise raw:<normalise_title(行业类别)>",
        "dimension_counts": {key: len(value) for key, value in dimensions.items()}, "dimensions": dimensions,
        "trace_examples": {
            "国企": {"source_field": "行业类别", "normalized_value": "国企", "mapping_result": "raw:国企", "reason": "no frozen Level-1 mapping token; normalized value also equals an 企业类型 value, so classified Organization / Ownership Type"},
            "金融": {"source_field": "行业类别", "normalized_value": "金融", "mapping_result": "l1:金融与金融科技", "reason": "frozen INDUSTRY_CONTEXT_TO_LEVEL_1 maps 金融 uniquely"},
            "科技": {"source_field": "行业类别", "normalized_value": "科技", "mapping_result": "raw:科技", "reason": "no frozen Level-1 mapping token; retained raw source category"},
        },
        "mixing_location": "normalization produces both l1:* and raw:* values in the same industry_domain_context field; the previous display hierarchy exposed both branches. Frozen Product Data preserves the distinction via context_classification. Frontend did not create the mixed semantics.",
        "industry_map_eligibility": {
            "supported": True, "include": "only contexts with l1: prefix (taxonomy_domain)",
            "exclude": "all raw:* contexts from the Industry Map; retain them as provenance/evidence metadata",
            "deterministic_metrics": "from job_groups_v2: union source_recruitment_record_ids for demand; occupation identity mapping for occupation count/demand; existing Product Data skill_intelligence_available for coverage",
            "navigation": "招聘市场 → l1 Industry / Domain → occupations in that context → occupation × context Skills/Evidence; no second context selector",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "dimension_counts": result["dimension_counts"], "api_calls": 0}, ensure_ascii=False))

if __name__ == "__main__": main()
