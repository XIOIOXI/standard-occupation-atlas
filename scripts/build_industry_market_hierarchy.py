"""Create a read-only Industry-only navigation projection from display_hierarchy."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/processed/job_market_intelligence/market_map/display_hierarchy.json"
OUT = ROOT / "data/processed/job_market_intelligence/market_map/industry_market_hierarchy.json"

def main():
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    contexts = source["levels"]["level_1"]["nodes_by_parent"]["major:standardized-domains"]
    occupations = source["levels"]["level_2"]["occupations_by_context"]
    industries = []
    search = []
    for context in contexts:
        rows = occupations[context["node_id"]]
        industries.append({**context, "classification": "taxonomy_domain", "occupations": rows})
        search.extend({"occupation_id": row["node_id"], "display_name": row["label"],
                       "searchable_aliases": [row["label"]], "identity_type": row["identity_type"],
                       "recruitment_evidence_count": row["recruitment_evidence_count"],
                       "context_id": context["node_id"], "context_label": context["label"]}
                      for row in rows)
    output = {"version": "industry-market-hierarchy-v1", "demand_metric": "distinct_recruitment_record_count",
              "source": "display_hierarchy.json; l1:* contexts only", "api_calls": 0, "llm_calls": 0,
              "industries": industries, "occupation_context_search_index": search}
    OUT.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({"industry_count": len(industries), "search_routes": len(search), "api_calls": 0}, ensure_ascii=False))
if __name__ == "__main__": main()
