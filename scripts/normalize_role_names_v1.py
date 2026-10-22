"""Deterministic, name-only formatting normalisation for role groups.

This stage deliberately does not infer occupation identity or merge synonyms.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

ROOT = Path("data/processed/record_role_classification_v1")
SOURCE = ROOT / "groups" / "record_role_groups.json"
OUTPUT = ROOT / "name_registry" / "format_normalized_names.json"

PAREN_RE = re.compile(r"[（(]([^（）()]*)[）)]")
TAIL_COUNT_RE = re.compile(r"(?:[，,、;；\s-]*(?:招聘)?\s*\d+\s*(?:人|名|位|个))+$", re.I)
SPACE_RE = re.compile(r"\s+")
# These are recruitment annotations only when the *whole* parenthetical item
# contains no occupation, technology, or business-direction wording.
RECRUIT_NOTE_RE = re.compile(
    r"^(?:\d{4}届)?(?:校招|社招|实习生?|应届生?|本科|硕士|博士|大专|学历不限|专业不限)"
    r"(?:[ /、，,]*(?:校招|社招|实习生?|应届生?|本科|硕士|博士|大专|学历不限|专业不限))*$",
    re.I,
)


def normalize_name(original: str) -> tuple[str, str, list[str]]:
    value = unicodedata.normalize("NFKC", original or "").strip()
    value = SPACE_RE.sub(" ", value)
    # Keep C++, C#, .NET and all other technical punctuation intact. Only
    # canonicalise parentheses, which NFKC does not make uniform in all cases.
    value = value.replace("（", "(").replace("）", ")")
    removed: list[str] = []

    def strip_recruit_note(match: re.Match[str]) -> str:
        content = SPACE_RE.sub("", match.group(1))
        if RECRUIT_NOTE_RE.fullmatch(content):
            removed.append(match.group(0))
            return ""
        return match.group(0)

    value = PAREN_RE.sub(strip_recruit_note, value)
    counted = TAIL_COUNT_RE.search(value)
    if counted:
        removed.append(counted.group(0))
        value = value[: counted.start()]
    value = SPACE_RE.sub(" ", value).strip(" ,，;；")
    # casefold is for matching only; the readable name preserves normalized case.
    return value, value.casefold(), removed


def main() -> None:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    rows = []
    changed = 0
    for group in data["groups"]:
        original = group["canonical_title"]
        normalized, match_key, removed = normalize_name(original)
        if normalized != original:
            changed += 1
        rows.append({
            "record_role_group_id": group["record_role_group_id"],
            "original_name": original,
            "format_normalized_name": normalized,
            "format_match_key": match_key,
            "removed_recruitment_annotations": removed,
        })
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({
        "schema_version": "role-name-format-normalization-v1",
        "policy": "NFKC; whitespace/case matching; parentheses; trailing headcount and standalone recruitment annotations only. No semantic merging.",
        "input_group_count": len(rows),
        "format_changed_group_count": changed,
        "rows": rows,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
