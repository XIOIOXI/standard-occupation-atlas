"""Preparation-only contract for the next P0 semantic re-review.

No LLM client exists here.  This module validates that the frozen P0 queue and
the immutable v1 result can coexist with the independent v2 output path.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


SEMANTIC_REVIEW_VERSION = "semantic-review-v2"
PROMPT_VERSION = "semantic-candidate-review-prompt-v2"
P0_REVIEW_TARGETS = (
    "测试工程师", "客户经理", "销售工程师", "结构工程师", "产品工程师", "技术支持工程师",
    "财务专员", "销售经理", "项目工程师", "AI工程师", "项目助理", "运维工程师",
)


@dataclass(frozen=True)
class P0V2ReReviewPlan:
    semantic_review_version: str
    prompt_version: str
    queued_p0_family_count: int
    p0_pending_identity_or_placement_titles: tuple[str, ...]
    legacy_v1_path: Path
    v2_results_path: Path


def prepare_p0_v2_re_review(
    queue_path: Path, legacy_v1_path: Path, v2_results_path: Path
) -> P0V2ReReviewPlan:
    """Validate re-review inputs without writing output or invoking an LLM."""

    queue = [
        json.loads(line)
        for line in queue_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    p0 = [row for row in queue if row.get("priority_tier") == "P0"]
    if len(p0) != 22:
        raise ValueError(f"Expected frozen P0 queue of 22 families, found {len(p0)}.")
    if not legacy_v1_path.exists() or not legacy_v1_path.read_text(encoding="utf-8").strip():
        raise ValueError("The immutable semantic-review-v1 P0 results are required for compatibility.")
    p0_titles = {row["representative_title"] for row in p0}
    missing = set(P0_REVIEW_TARGETS) - p0_titles
    if missing:
        raise ValueError(f"P0 queue is missing re-review targets: {sorted(missing)}")
    return P0V2ReReviewPlan(
        semantic_review_version=SEMANTIC_REVIEW_VERSION,
        prompt_version=PROMPT_VERSION,
        queued_p0_family_count=len(p0),
        p0_pending_identity_or_placement_titles=P0_REVIEW_TARGETS,
        legacy_v1_path=legacy_v1_path,
        v2_results_path=v2_results_path,
    )
