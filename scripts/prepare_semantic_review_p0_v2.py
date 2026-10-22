"""Validate P0 re-review prerequisites without calling an LLM or writing results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.domain.taxonomy.semantic_review_v2 import prepare_p0_v2_re_review


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--v1-results", type=Path, required=True)
    parser.add_argument("--v2-results", type=Path, required=True)
    args = parser.parse_args()

    plan = prepare_p0_v2_re_review(args.queue, args.v1_results, args.v2_results)
    print(json.dumps({
        "semantic_review_version": plan.semantic_review_version,
        "prompt_version": plan.prompt_version,
        "queued_p0_family_count": plan.queued_p0_family_count,
        "prepared_targets": list(plan.p0_pending_identity_or_placement_titles),
        "legacy_v1_path": str(plan.legacy_v1_path),
        "v2_results_path": str(plan.v2_results_path),
        "execution": "not_run; this command validates preparation only and never calls an LLM or writes results",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
