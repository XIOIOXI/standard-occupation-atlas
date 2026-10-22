"""Build a compact, read-only SNO-to-OCC trace index for the SNO MVP view."""
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / 'data/processed/record_role_classification_v1/targeted_name_repairs/name_only_targeted_repair_v1'
SOURCE = DATA_DIR / 'occ_sno_source_links_v1.json'
OUTPUT = DATA_DIR / 'sno_occ_trace_index_v1.json'

def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f'Refusing to overwrite existing output: {OUTPUT}')
    with SOURCE.open('r', encoding='utf-8') as stream:
        source = json.load(stream)
    by_sno: dict[str, list[str]] = defaultdict(list)
    for link in source['links']:
        by_sno[link['standard_occupation_id']].append(link['occupation_id'])
    occupations = {sno_id: {'linked_occupation_count': len(occupation_ids), 'linked_occupation_ids': occupation_ids} for sno_id, occupation_ids in sorted(by_sno.items())}
    artifact = {'schema_version': 'sno-occ-trace-index-v1', 'source_link_file': str(SOURCE.relative_to(ROOT)).replace('\\', '/'), 'link_method': 'shared_source_record_id_only', 'occupation_count': len(occupations), 'occupations': occupations}
    with OUTPUT.open('x', encoding='utf-8') as stream:
        json.dump(artifact, stream, ensure_ascii=False, separators=(',', ':'))
    print(f'wrote {OUTPUT}')
    print(f'SNO with OCC evidence: {len(occupations)}')

if __name__ == '__main__':
    main()
