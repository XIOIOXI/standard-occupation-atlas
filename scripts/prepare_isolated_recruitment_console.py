"""Create a reusable browser-test data area without mutating production data."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend")); sys.path.insert(0, str(ROOT / "scripts"))
import process_recruitment_update as updates  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("sandbox", type=Path); args = parser.parse_args()
    sandbox = args.sandbox.resolve(); display = sandbox / "display"; display.mkdir(parents=True, exist_ok=True)
    baseline = sandbox / "baseline.sqlite"
    if not baseline.exists(): shutil.copy2(updates.BASELINE_DB, baseline)
    for name in ("display_projection_v31_full_draft.json", "sno_atomic_evidence_index_v1.json", "unclassified_queue_v31.json", "display_summary_v31.json", "job_search_index_v1.json", "job_search_index_v1.meta.json", "job_search_facets_v1.json"):
        target = display / name
        if not target.exists(): shutil.copy2(updates.DISPLAY_DIR / name, target)
    updates.DISPLAY_CATALOGUE = display / "update_batches.json"; updates.OUTPUT_BASE = sandbox / "runs"
    updates.display_catalogue(updates.UpdateRepository(sandbox / "updates.sqlite"))
    print(sandbox)


if __name__ == "__main__": main()
