"""Deterministic candidate generation for unmapped occupation identities.

Candidate families are review artifacts only.  They do not change Job Groups,
Taxonomy mappings, or recruitment records.
"""
from __future__ import annotations

import re
from collections import defaultdict

from app.domain.taxonomy.coverage import normalise_title

SPECIALISATIONS = (
    "前端", "后端", "服务端", "软件", "硬件", "测试", "开发", "算法", "数据",
    "视觉", "nlp", "推荐", "嵌入式", "芯片", "电源", "结构", "工艺", "售前", "售后",
    "网络安全", "运维", "云", "java", "python", "财务", "法务", "采购", "销售",
)
PROTECTED_SPECIALISATIONS = (
    "前端", "后端", "软件", "硬件", "测试", "算法", "数据", "视觉", "nlp", "推荐",
    "嵌入式", "芯片", "电源", "结构", "工艺", "售前", "售后", "网络安全", "运维", "云",
    "java", "python",
)
GENERIC_ROOTS = {"", "工程", "工程师", "开发", "研发", "技术", "岗位", "专员", "经理", "运营", "管理", "销售", "产品", "ai"}


def remove_recruitment_noise(title: str) -> str:
    """Remove only plainly non-identity recruitment modifiers."""
    text = normalise_title(title)
    text = re.sub(r"[（(](?:20\d{2}届|校招|应届生|实习|北京|上海|广州|深圳|杭州|海外)[^）)]*[）)]", "", text)
    text = re.sub(r"^(?:初级|中级|高级|资深|校招|应届生|实习|储备)", "", text)
    text = re.sub(r"(?:校招|应届生|实习生|实习|储备)$", "", text)
    return text


def specialisation_signals(title: str) -> tuple[str, ...]:
    text = remove_recruitment_noise(title)
    return tuple(signal for signal in SPECIALISATIONS if signal in text)


def _role_family_and_root(title: str) -> tuple[str, str]:
    text = remove_recruitment_noise(title)
    text = text.replace("服务端", "后端").replace("web前端", "前端")
    for suffix in ("管理培训生", "管培生", "培训生", "实习生"):
        if text.endswith(suffix):
            return "program", text[: -len(suffix)]
    # Engineer/developer wording is a safe, narrow surface transformation.
    for suffix in ("开发软件工程师", "开发工程师", "研发工程师", "软件工程师", "工程师", "开发", "研发"):
        if text.endswith(suffix) and len(text) > len(suffix):
            return "engineering_development", text[: -len(suffix)]
    for suffix, family in (("专员", "specialist"), ("经理", "manager"), ("主管", "manager"), ("助理", "assistant"), ("运营", "operations"), ("岗", "other"), ("岗位", "other")):
        if text.endswith(suffix) and len(text) > len(suffix):
            return family, text[: -len(suffix)]
    return "other", text


def strict_identity_key(title: str) -> str | None:
    family, root = _role_family_and_root(title)
    return None if family == "program" or root in GENERIC_ROOTS or len(root) < 2 else f"{family}:{root}"


def medium_identity_key(title: str) -> str | None:
    family, root = _role_family_and_root(title)
    root = re.sub(r"(?:助理|管培生|培训生|管理培训生)$", "", root)
    return None if root in GENERIC_ROOTS or len(root) < 2 else root


def has_specialisation_conflict(groups: list[dict]) -> list[str]:
    observed = {
        tuple(signal for signal in specialisation_signals(group["representative_title"]) if signal in PROTECTED_SPECIALISATIONS)
        for group in groups
    }
    nonempty = {signals for signals in observed if signals}
    if len(nonempty) <= 1:
        return []
    return sorted({signal for signals in nonempty for signal in signals})


def blocked_clusters(groups: list[dict], key_fn) -> dict[str, list[dict]]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for group in groups:
        key = key_fn(group["representative_title"])
        if key:
            buckets[key].append(group)
    return {key: value for key, value in buckets.items() if len(value) > 1}
