"""Deterministic mapping of recruitment titles into a reference taxonomy.

Reference Taxonomy defines the classification space; recruitment data is mapped
into that space. This module does not create, update, or infer taxonomy entries.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable



@dataclass(frozen=True)
class TaxonomyEntry:
    occupation_id: str
    level_1: str
    level_2: str
    level_3: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class ReferenceCandidate:
    raw_title: str
    level_1: str | None
    level_2: str | None


@dataclass(frozen=True)
class SplitTitleUnit:
    unit: str
    gate_status: str
    gate_reason: str


def _text(value: Any) -> str:
    # Keep title splitting usable for the local update command without loading
    # the optional workbook reader dependency.  Pandas is imported only when a
    # workbook is actually read below.
    if value is None:
        return ""
    try:
        if value != value:  # NaN, without requiring pandas at module import.
            return ""
    except Exception:
        pass
    return str(value).strip()


def normalise_title(value: str) -> str:
    """Normalise display noise only; do not collapse different occupations."""

    text = unicodedata.normalize("NFKC", value).casefold()
    text = re.sub(r"[\s\-_/·]", "", text)
    return text.strip("，,。.;；:：")


def _split_aliases(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in re.split(r"[、,，;；\n]+", value) if item.strip())


def load_reference_taxonomy(path: str | Path) -> tuple[list[TaxonomyEntry], dict[str, ReferenceCandidate]]:
    """Read the reference workbook without modifying it."""

    import pandas as pd

    workbook = Path(path)
    taxonomy = pd.read_excel(workbook, sheet_name="occupation_taxonomy")
    entries: list[TaxonomyEntry] = []
    for _, row in taxonomy.iterrows():
        aliases = _split_aliases(_text(row["岗位别名/市场称谓"]))
        entries.append(
            TaxonomyEntry(
                occupation_id=_text(row["occupation_id"]),
                level_1=_text(row["一级大行业"]),
                level_2=_text(row["二级行业/职业领域"]),
                level_3=_text(row["三级标准岗位"]),
                aliases=aliases,
            )
        )

    candidates = pd.read_excel(workbook, sheet_name="occupation_candidates")
    reference_candidates = {
        normalise_title(_text(row["原始岗位名称"])): ReferenceCandidate(
            raw_title=_text(row["原始岗位名称"]),
            level_1=_text(row["标准一级大行业"]) or None,
            level_2=_text(row["标准二级领域"]) or None,
        )
        for _, row in candidates.iterrows()
        if _text(row["原始岗位名称"])
    }
    return entries, reference_candidates


ROLE_MARKER_PATTERN = re.compile(
    r"(?:岗|岗位|工程师|经理|专员|主管|顾问|助理|总监|分析师|研究员|培训生|管培生|运营|"
    r"设计师|教师|编辑|法务|销售|客服|会计|审计|采购|物流|翻译|护士|医生|技师|"
    r"科学家|架构师|开发|测试|策划|规划|技术支持|客户经理|管理员|实习生|职员|员|师|生)$",
    re.IGNORECASE,
)
ROLE_STRUCTURE_PATTERN = re.compile(
    r"(?:岗|岗位|工程师|经理|专员|主管|顾问|助理|总监|分析师|研究员|培训生|管培生|"
    r"运营|开发|测试|调试|工艺|履约|核算|销售|支持|代表|审核员|人员|"
    r"设计|策划|规划|采购|物流|翻译|编辑|实习|职员|教师|医生|护士|技师|科学家|架构师)$",
    re.IGNORECASE,
)
NON_JOB_FRAGMENT_PATTERN = re.compile(
    r"^(?:"
    r"北京|上海|广州|深圳|杭州|苏州|成都|西安|武汉|南京|天津|重庆|青岛|宁波|厦门|"
    r"长沙|郑州|合肥|福州|佛山|东莞|无锡|常州|珠海|全国|海外|当地|地区|"
    r"本科|硕士|博士|大专|中专|本硕|学历不限|不限|专业不限|若干|详见|具体见|"
    r"企业公告内查看|@具体见投递页面各招聘单位要求|\\.\\.\\.\\.\\.\\.|"
    r"计算机类|机械类|电气类|电子信息类|材料类|金融学类|工商管理类|法学类|化学类|"
    r"数学类|统计学类|自动化类|土木类|建筑类|管理类|经济类|财经类|专业类"
    r")$"
)
CATEGORY_FRAGMENT_PATTERN = re.compile(
    r"(?:类|方向|部门|事业部|中心|办公室|序列|专业|相关专业|岗位类别|岗位类|"
    r"技术类|业务类|职能类|营销类|管理类|项目类|研发类|产品类|生产类|支持类)$"
)
DESCRIPTION_FRAGMENT_PATTERN = re.compile(r"(?:招聘|公告|投递|要求|以上|优先|工作地点|相关专业)")
TOP_LEVEL_COLON_PATTERN = re.compile(r"^[^:：]{1,24}[:：](.+)$")
TITLE_LIST_LABEL_PATTERN = re.compile(r"(?:岗位|职位|招聘|类|方向|部门|序列|计划)$")
NON_TITLE_COLON_LABEL_PATTERN = re.compile(r"(?:专业要求|学历要求|工作地点|招聘条件|任职要求|需求专业)$")
TOP_LEVEL_REQUIREMENT_MARKER_PATTERN = re.compile(
    r"(?:专业不限|学历不限|专业要求|需求专业|相关专业|所需专业)"
)
TRAILING_REQUIREMENT_PARENS_PATTERN = re.compile(
    r"\s*[（(][^（）()]*?(?:专业不限|学历不限|相关专业|专业要求|需求专业|所需专业)[^（）()]*[）)]\s*$"
)
ROLE_TOKEN_SUFFIX_PATTERN = (
    r"(?:工程师|经理|专员|主管|顾问|助理|总监|分析师|研究员|培训生|管培生|"
    r"设计师|教师|编辑|法务|销售|客服|会计|审计|采购|物流|翻译|护士|医生|技师|"
    r"科学家|架构师|代表|审核员|人员|职员|实习生|岗)"
)
CONCATENATED_ROLE_TOKEN_PATTERN = re.compile(
    rf"[\u4e00-\u9fffA-Za-z0-9+/#&._-]{{1,40}}?{ROLE_TOKEN_SUFFIX_PATTERN}(?:[（(][^（）()]*[）)])?"
)


def _clean_title(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _strip_wrapping_punctuation(value: str) -> str:
    return value.strip(" \t\r\n，,;；、")


def _split_top_level(value: str) -> list[str]:
    """Split only on delimiters outside parentheses."""

    units: list[str] = []
    current: list[str] = []
    depth = 0
    for char in value:
        if char in "（(":
            depth += 1
            current.append(char)
            continue
        if char in "）)" and depth:
            depth -= 1
            current.append(char)
            continue
        if depth == 0 and char in "、,，;；\n":
            unit = _strip_wrapping_punctuation("".join(current))
            if unit:
                units.append(unit)
            current = []
            continue
        current.append(char)
    unit = _strip_wrapping_punctuation("".join(current))
    if unit:
        units.append(unit)
    return units


def _looks_like_role(value: str) -> bool:
    text = _strip_wrapping_punctuation(value)
    if not text:
        return False
    comparable = re.sub(r"[（(][^（）()]*[）)]", "", text)
    if ROLE_MARKER_PATTERN.search(text) or ROLE_MARKER_PATTERN.search(comparable):
        return True
    if re.search(
        r"(?:工程师|经理|专员|主管|顾问|助理|总监|分析师|研究员|培训生|管培生|"
        r"设计师|教师|法务|会计|审计|护士|医生|技师|科学家|架构师)",
        text,
    ):
        return True
    if re.search(
        r"\b(?:developer|engineer|scientist|analyst|manager|designer|trainee|intern|"
        r"officer|leader|specialist|associate|coordinator|representative)\b",
        text,
        re.I,
    ):
        return True
    # Source exports commonly use functional English labels (for example,
    # ``Womenswear Design``) rather than the noun ``Designer``.  ``Des`` is
    # retained as a source abbreviation; it is not expanded or inferred.
    if re.search(r"\b(?:design|des)\b$", text, re.I):
        return True
    return False


def _has_clear_role_structure(value: str) -> bool:
    """Recognise conservative job-shaped labels that omit the older markers."""

    text = _strip_wrapping_punctuation(value)
    comparable = re.sub(r"[（(][^（）()]*[）)]", "", text).strip()
    return bool(ROLE_STRUCTURE_PATTERN.search(comparable))


def _drop_category_list_labels(value: str) -> str:
    """Drop only top-level category labels before an explicit position list."""

    def replace(match: re.Match[str]) -> str:
        prefix, label = match.group(1), match.group(2).strip()
        if TITLE_LIST_LABEL_PATTERN.search(label) and not NON_TITLE_COLON_LABEL_PATTERN.search(label):
            return prefix
        return match.group(0)

    return re.sub(r"(^|[;；\n])\s*([^;；\n:：]{1,24})[:：]", replace, value)


def _top_level_colon_index(value: str) -> int | None:
    """Return the first colon outside parentheses, if present."""

    depth = 0
    for index, char in enumerate(value):
        if char in "（(":
            depth += 1
        elif char in "）)" and depth:
            depth -= 1
        elif depth == 0 and char in ":：":
            return index
    return None


def _strip_top_level_requirement_suffix(value: str) -> str:
    """Remove a requirement list appended to an otherwise explicit role list.

    Only markers outside parentheses are eligible.  This preserves meaningful
    parenthetical context such as ``项目经理（相关专业：计算机类）`` while fixing
    source strings such as ``客服管培生专业不限、国际贸易、物流``.
    """

    depth = 0
    for index, character in enumerate(value):
        if character in "（(":
            depth += 1
            continue
        if character in "）)" and depth:
            depth -= 1
            continue
        if depth:
            continue
        match = TOP_LEVEL_REQUIREMENT_MARKER_PATTERN.match(value, index)
        if not match or index == 0:
            continue
        prefix = _strip_wrapping_punctuation(value[:index])
        prefix_units = _split_top_level(prefix)
        if any(_looks_like_role(unit) or _has_clear_role_structure(unit) for unit in prefix_units):
            return prefix
    return value


def _clean_atomic_unit(value: str) -> str:
    """Remove only exact trailing eligibility notes from a role label."""

    return _strip_wrapping_punctuation(TRAILING_REQUIREMENT_PARENS_PATTERN.sub("", value))


def _split_concatenated_role_unit(value: str) -> list[str] | None:
    """Split only a delimiter-free sequence of complete, adjacent role tokens.

    This intentionally refuses a partial parse. Any unexplained non-whitespace
    text between tokens keeps the original unit intact for later review.
    """

    matches = list(CONCATENATED_ROLE_TOKEN_PATTERN.finditer(value))
    if len(matches) < 2:
        return None
    if value[: matches[0].start()].strip() or value[matches[-1].end() :].strip():
        return None
    if any(value[left.end() : right.start()].strip() for left, right in zip(matches, matches[1:])):
        return None
    return [_strip_wrapping_punctuation(match.group()) for match in matches]


def _contains_multiple_role_tokens(value: str) -> bool:
    return len(CONCATENATED_ROLE_TOKEN_PATTERN.findall(value)) >= 2


def _is_non_job_fragment(value: str) -> str | None:
    text = _strip_wrapping_punctuation(value).strip("（）()")
    if not text:
        return "empty_fragment"
    if NON_JOB_FRAGMENT_PATTERN.fullmatch(text):
        return "location_education_major_or_placeholder"
    if len(text) <= 2 and not _looks_like_role(text):
        return "too_short_without_role_marker"
    if CATEGORY_FRAGMENT_PATTERN.search(text):
        if "岗位" in text:
            return None
        if not _looks_like_role(text):
            return "category_department_or_major_fragment"
    if DESCRIPTION_FRAGMENT_PATTERN.search(text) and not _looks_like_role(text):
        return "descriptive_recruitment_text"
    return None


def _gate_unit(unit: str, total_units: int, raw_title: str) -> SplitTitleUnit:
    fragment_reason = _is_non_job_fragment(unit)
    if fragment_reason:
        return SplitTitleUnit(unit, "rejected_non_job_fragment", fragment_reason)
    if (CATEGORY_FRAGMENT_PATTERN.search(unit) or re.search(r"(?:类岗位|岗位[（(])", unit)) and "岗位" in unit and not re.search(
        r"(?:工程师|经理|专员|主管|顾问|助理|总监|分析师|研究员|培训生|管培生|"
        r"设计师|教师|法务|会计|审计|护士|医生|技师|科学家|架构师)",
        unit,
    ):
        return SplitTitleUnit(unit, "review_required", "generic_category_position")
    if _contains_multiple_role_tokens(unit):
        return SplitTitleUnit(unit, "review_required", "ambiguous_multi_job_concatenation")
    if _looks_like_role(unit):
        return SplitTitleUnit(unit, "accepted", "role_marker_present")
    if _has_clear_role_structure(unit):
        return SplitTitleUnit(unit, "accepted", "clear_role_structure")
    if len(unit) > 40 and any(delimiter in raw_title for delimiter in ("、", ",", "，", ";", "；", "\n")):
        return SplitTitleUnit(unit, "review_required", "complex_mixed_title_unit")
    return SplitTitleUnit(unit, "review_required", "no_clear_role_marker")


def split_title_units_with_quality(raw_job_title: str) -> list[SplitTitleUnit]:
    """Split explicit multi-position lists and attach deterministic gate metadata."""

    cleaned = _strip_top_level_requirement_suffix(_clean_title(raw_job_title))
    if not cleaned:
        return []

    colon_index = _top_level_colon_index(cleaned)
    split_source = _drop_category_list_labels(cleaned)
    if colon_index is not None and colon_index <= 24:
        label = cleaned[:colon_index].strip()
        suffix = cleaned[colon_index + 1 :].strip()
        suffix_units = _split_top_level(suffix)
        role_like_units = sum(
            1 for unit in suffix_units if _looks_like_role(unit) or _has_clear_role_structure(unit)
        )
        if (
            not NON_TITLE_COLON_LABEL_PATTERN.search(label)
            and TITLE_LIST_LABEL_PATTERN.search(label)
            and len(suffix_units) > 1
            and role_like_units >= 2
        ):
            split_source = _drop_category_list_labels(suffix)
        else:
            return [SplitTitleUnit(cleaned, "review_required", "colon_context_not_safe_to_split")]

    raw_units = _split_top_level(split_source)
    atomic_units: list[str] = []
    for unit in raw_units:
        atomic_units.extend(_split_concatenated_role_unit(unit) or [_clean_atomic_unit(unit)])
    raw_units = atomic_units
    if len(raw_units) == 1:
        unit = raw_units[0]
        if len(unit) > 80 and any(delimiter in unit for delimiter in ("、", ",", "，", ";", "；", "\n")):
            return [SplitTitleUnit(unit, "review_required", "long_unsplit_mixed_field")]
    return [_gate_unit(unit, len(raw_units), cleaned) for unit in raw_units]


def split_title_units(raw_job_title: str) -> list[str]:
    """Backward-compatible title-unit list without quality metadata."""

    return [item.unit for item in split_title_units_with_quality(raw_job_title)]


def _safe_standard_forms(title: str) -> set[str]:
    """Remove only recruitment/location qualifiers, never domain qualifiers."""

    forms = {normalise_title(title)}
    bracketed = re.search(r"[（(]([^（）()]*)[）)]$", title.strip())
    if bracketed:
        qualifier = bracketed.group(1)
        if re.search(r"(校招|实习|应届|届|北京|上海|深圳|广州|杭州|全国|海外|当地|地区)", qualifier):
            forms.add(normalise_title(title[: bracketed.start()]))
    for prefix in ("校园招聘", "校招", "应届生"):
        if title.startswith(prefix):
            forms.add(normalise_title(title[len(prefix) :]))
    return {form for form in forms if form}


# These are contextual compatibility cues, not a replacement taxonomy and not a
# source-data-derived classification. They are used only to disambiguate an
# existing Reference Taxonomy match or to retain a cautious partial suggestion.
INDUSTRY_CONTEXT_TO_LEVEL_1: dict[str, str] = {
    "互联网": "信息技术与数字产业",
    "it": "信息技术与数字产业",
    "软件": "信息技术与数字产业",
    "人工智能": "信息技术与数字产业",
    "金融": "金融与金融科技",
    "银行": "金融与金融科技",
    "证券": "金融与金融科技",
    "保险": "金融与金融科技",
    "半导体": "电子信息与通信产业",
    "通信": "电子信息与通信产业",
    "电子": "电子信息与通信产业",
    "新能源": "新能源与能源产业",
    "能源": "新能源与能源产业",
    "电力": "新能源与能源产业",
    "汽车": "汽车与智能交通",
    "航空航天": "航空航天与低空经济",
    "军工": "航空航天与低空经济",
    "生物医药": "生物医药与生命科学",
    "生命科学": "生物医药与生命科学",
    "医疗": "医疗健康与医疗器械",
    "医药": "医疗健康与医疗器械",
    "制造": "智能制造与工业",
    "机械": "智能制造与工业",
    "物流": "物流与供应链",
    "建筑": "建筑与房地产",
    "地产": "建筑与房地产",
    "教育": "教育与人力资本",
    "传媒": "市场营销与传媒",
    "广告": "市场营销与传媒",
    "电商": "电子商务与零售",
    "零售": "电子商务与零售",
    "农业": "农业食品与消费产业",
    "农林": "农业食品与消费产业",
    "环保": "环境生态与资源",
    "公共": "公共管理与社会服务",
    "政府": "公共管理与社会服务",
}


def _context_level_1(industry_category: str | None) -> str | None:
    source = normalise_title(industry_category or "")
    matched = {level_1 for token, level_1 in INDUSTRY_CONTEXT_TO_LEVEL_1.items() if token in source}
    return next(iter(matched)) if len(matched) == 1 else None


def _taxonomy_indexes(entries: list[TaxonomyEntry]) -> tuple[dict[str, list[TaxonomyEntry]], dict[str, list[TaxonomyEntry]]]:
    canonical: dict[str, list[TaxonomyEntry]] = defaultdict(list)
    aliases: dict[str, list[TaxonomyEntry]] = defaultdict(list)
    for entry in entries:
        canonical[normalise_title(entry.level_3)].append(entry)
        for alias in entry.aliases:
            aliases[normalise_title(alias)].append(entry)
    return canonical, aliases


def _select_exact_candidate(
    title: str,
    canonical_index: dict[str, list[TaxonomyEntry]],
    alias_index: dict[str, list[TaxonomyEntry]],
    context_level_1: str | None,
) -> tuple[TaxonomyEntry | None, str | None]:
    forms = _safe_standard_forms(title)
    candidates: list[tuple[TaxonomyEntry, str]] = []
    for form in forms:
        candidates.extend(
            (entry, "exact" if normalise_title(title) == form else "standard")
            for entry in canonical_index.get(form, [])
        )
        candidates.extend((entry, "alias") for entry in alias_index.get(form, []))
    candidates = list(dict.fromkeys(candidates))
    if context_level_1:
        contextual = [item for item in candidates if item[0].level_1 == context_level_1]
        if len(contextual) == 1:
            return contextual[0]
    return candidates[0] if len(candidates) == 1 else (None, None)


def _review_suggestion(
    title: str, entries: list[TaxonomyEntry], context_level_1: str | None
) -> TaxonomyEntry | None:
    """Offer a review-only suggestion; never automatically maps a fuzzy result."""

    if not context_level_1:
        return None
    normalised = normalise_title(title)
    pool = [entry for entry in entries if not context_level_1 or entry.level_1 == context_level_1]
    # A review suggestion needs an explicit title containment relationship and a
    # unique taxonomy candidate. General fuzzy similarity is intentionally not
    # used: it would invite a weak title-only classification.
    candidates = [
        entry
        for entry in pool
        if len(normalise_title(entry.level_3)) >= 3
        and (
            normalise_title(entry.level_3) in normalised
            or normalised in normalise_title(entry.level_3)
        )
    ]
    return candidates[0] if len(candidates) == 1 else None


def _map_unit(
    unit: str,
    industry_category: str | None,
    entries: list[TaxonomyEntry],
    canonical_index: dict[str, list[TaxonomyEntry]],
    alias_index: dict[str, list[TaxonomyEntry]],
    reference_candidates: dict[str, ReferenceCandidate],
) -> dict[str, Any]:
    context_level_1 = _context_level_1(industry_category)
    direct, match_type = _select_exact_candidate(unit, canonical_index, alias_index, context_level_1)
    if direct:
        return {
            "matched_level_1": direct.level_1,
            "matched_level_2": direct.level_2,
            "matched_occupation_id": direct.occupation_id,
            "matched_occupation_name": direct.level_3,
            "match_type": match_type,
            "match_confidence": "high",
            "review_status": "not_required",
        }
    candidate_reference = reference_candidates.get(normalise_title(unit))
    if candidate_reference:
        return {
            "matched_level_1": candidate_reference.level_1,
            "matched_level_2": candidate_reference.level_2,
            "matched_occupation_id": None,
            "matched_occupation_name": None,
            "match_type": "unmapped",
            "match_confidence": "not_applicable",
            "review_status": "candidate_reference",
        }
    suggestion = _review_suggestion(unit, entries, context_level_1)
    if suggestion:
        return {
            "matched_level_1": suggestion.level_1,
            "matched_level_2": suggestion.level_2,
            "matched_occupation_id": None,
            "matched_occupation_name": None,
            "match_type": "semantic_review",
            "match_confidence": "low",
            "review_status": "review_required",
        }
    return {
        "matched_level_1": context_level_1,
        "matched_level_2": None,
        "matched_occupation_id": None,
        "matched_occupation_name": None,
        "match_type": "unmapped",
        "match_confidence": "not_applicable",
        "review_status": "unmapped",
    }


def analyse_coverage(records: Iterable[dict[str, Any]], taxonomy_path: str | Path) -> pd.DataFrame:
    """Map accepted title units into the reference space and retain gated audit rows."""

    entries, reference_candidates = load_reference_taxonomy(taxonomy_path)
    canonical_index, alias_index = _taxonomy_indexes(entries)
    results: list[dict[str, Any]] = []
    mapping_cache: dict[tuple[str, str | None], dict[str, Any]] = {}
    for record in records:
        raw_job_title = _text(record.get("job_title"))
        for split_unit in split_title_units_with_quality(raw_job_title):
            unit = split_unit.unit
            if split_unit.gate_status == "accepted":
                cache_key = (normalise_title(unit), _context_level_1(record.get("industry_category")))
                mapped = mapping_cache.get(cache_key)
                if mapped is None:
                    mapped = _map_unit(
                        unit,
                        record.get("industry_category"),
                        entries,
                        canonical_index,
                        alias_index,
                        reference_candidates,
                    )
                    mapping_cache[cache_key] = mapped
            else:
                mapped = {
                    "matched_level_1": None,
                    "matched_level_2": None,
                    "matched_occupation_id": None,
                    "matched_occupation_name": None,
                    "match_type": "not_mapped_quality_gate",
                    "match_confidence": "not_applicable",
                    "review_status": split_unit.gate_status,
                }
            results.append(
                {
                    "source_record_id": record["record_id"],
                    "source_row_number": record["row_number"],
                    "raw_job_title": raw_job_title,
                    "job_title_unit": unit,
                    "generated_unit": unit,
                    "gate_status": split_unit.gate_status,
                    "gate_reason": split_unit.gate_reason,
                    "company_name": record.get("company_name"),
                    "industry_category": record.get("industry_category"),
                    "location": record.get("location"),
                    "major_requirement": record.get("major_requirement"),
                    "education_requirement": record.get("education_requirement"),
                    **mapped,
                }
            )
    return pd.DataFrame(results)
