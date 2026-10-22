"""Add raw recruitment company types to the SNO atomic evidence index.

This is a local, deterministic projection enrichment.  It never calls an API
or changes any mapping decision: each atomic unit is joined to its preserved
source record by ``source_record_id``.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "data/processed/record_role_classification_v1/full_drafts/sno_v31_reasonable_primary_v4_display/sno_atomic_evidence_index_v1.json"
DATABASE_PATH = ROOT / "data/processed/recruitment_snapshots.sqlite"


def main() -> None:
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    atomic_units = index.get("atomic_units", {})
    source_ids = {str(item["source_record_id"]) for item in atomic_units.values() if item.get("source_record_id") is not None}

    with sqlite3.connect(DATABASE_PATH) as connection:
        source_fields = {
            record_id: {
                "company_type": company_type,
                "recruitment_url": recruitment_url,
                "announcement_url": announcement_url,
            }
            for record_id, company_type, recruitment_url, announcement_url in connection.execute(
                "SELECT record_id, company_type, recruitment_url, announcement_url FROM recruitment_records"
            )
        }

    missing = sorted(source_ids - source_fields.keys())
    if missing:
        raise RuntimeError(f"{len(missing)} 个证据来源未能在招聘快照中找到，拒绝写入不完整投影。")

    typed_sources = 0
    for item in atomic_units.values():
        source_id = item.get("source_record_id")
        source = source_fields.get(str(source_id), {})
        company_type = source.get("company_type")
        normalized = str(company_type).strip() if company_type is not None else ""
        item["company_type"] = normalized or None
        item["recruitment_url"] = str(source.get("recruitment_url") or "").strip() or None
        item["announcement_url"] = str(source.get("announcement_url") or "").strip() or None
        if normalized:
            typed_sources += 1

    index["schema_version"] = "sno-atomic-evidence-index-v2"
    index["company_type_source"] = "recruitment_snapshots.sqlite:recruitment_records.company_type"
    index["company_type_coverage"] = {
        "atomic_units": len(atomic_units),
        "source_records": len(source_ids),
        "source_records_with_company_type": sum(bool(str(source_fields[source_id]["company_type"] or "").strip()) for source_id in source_ids),
        "atomic_units_with_company_type": typed_sources,
    }

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=INDEX_PATH.parent, suffix=".tmp") as output:
        json.dump(index, output, ensure_ascii=False, indent=2)
        output.write("\n")
        temporary_path = Path(output.name)
    temporary_path.replace(INDEX_PATH)
    print(json.dumps(index["company_type_coverage"], ensure_ascii=False))


if __name__ == "__main__":
    main()
