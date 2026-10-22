"""Create a display-only snapshot that promotes only name-clear held entries.

The frozen taxonomy, SNO identities, raw recruitment records and prior snapshots
are never changed.  Each placement below was reviewed from the occupation name
alone.  Level-1 placements retain ``review`` because no Level-2/3 direction is
being invented; the UI consequently shows them in that existing L1's
``其他岗位`` bubble.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data/processed/record_role_classification_v1/targeted_name_repairs/name_only_targeted_repair_v1"
SOURCE = DATA_DIR / "display_projection_v7.json"
OUTPUT = DATA_DIR / "display_projection_v8.json"
TAXONOMY = ROOT / "data/processed/record_role_classification_v1/catalog_mappings/taxonomy_embedding_texts_v1.json"
AUDIT_OUTPUT = DATA_DIR / "display_projection_v8_clear_existing_placements.json"


# {standard occupation ID: (deepest known existing category ID, reason)}.
# No entry is assigned on the basis of a generic suffix such as 工程师/开发.
PLACEMENTS = {
    # Explicitly digital / computing / AI.  The names do not establish a formal
    # L2 or L3 specialty, so they intentionally stop at the existing L1.
    "SNO-27c20f82f604309fc07f": ("互联网/AI", "“IT研发”明确属于信息技术领域，但名称未给出可验证的二级或三级方向。"),
    "SNO-3e88d6376ab01925e931": ("互联网/AI", "名称明确为 AI 应用与软件开发，未据此补充后端、语言或算法细分。"),
    "SNO-d4afe2883eb018281ac5": ("互联网/AI", "“人工智能开发工程师”明确属于互联网/AI 一级，技术方向不足以确认三级。"),
    "SNO-943a39afa92964736bc5": ("互联网/AI", "“信息化技术”明确为数字信息技术工作，未指定实现方向。"),
    "SNO-bea5df18ef44c9e81c34": ("互联网/AI", "“信息技术”可确认到互联网/AI 一级，名称没有三级证据。"),
    "SNO-6aee239040477d7dff54": ("互联网/AI", "核心名称为“信息技术岗”；括号内专业清单不参与细分判断。"),
    "SNO-8afe68f2ca18752e4d5b": ("互联网/AI", "“信息技术相关”可确认到互联网/AI 一级，方向不明。"),
    "SNO-31509ce7a1c67e282ff4": ("互联网/AI", "“全信息技术”明确为信息技术领域，未增加具体技术栈。"),
    "SNO-3ee6836cfef88e5f348c": ("互联网/AI", "“地理信息平台开发”明确包含数字平台开发；未将 GIS 擅自细分为后端或数据开发。"),
    "SNO-22092131c6eb166ceb88": ("互联网/AI", "“平台开发工程师”可确认数字平台开发领域，无法仅由名称确定正式三级。"),
    "SNO-f2be2c7e61f4e79426b7": ("互联网/AI", "“应用开发”可确认软件/数字技术一级，未默认服务端或前端。"),
    "SNO-8f785fe6b76359fecbf6": ("互联网/AI", "“数字化工程师”明确为数字技术领域，未凭名称补充行业方向。"),
    "SNO-058bd4c93f0b5f5a97bf": ("互联网/AI", "“数字化技术工程师”可确认到互联网/AI 一级，三级依据不足。"),
    "SNO-a68495c84fae8a5c2886": ("互联网/AI", "“数字化技术应用”明确数字技术领域，未推定具体应用栈。"),
    "SNO-117ff7ed55e522caa5bb": ("互联网/AI", "“数字化技术开发”可确认到互联网/AI 一级，但没有技术方向证据。"),
    "SNO-7ab8043d98394b9be856": ("互联网/AI", "“网络数字孪生研究员”明确属于网络与数字技术领域，名称不足以细分至安全、开发或运维。"),
    "SNO-1658a6e5c6a6e8a9a02d": ("互联网/AI", "“计算机工程师”可确认计算机/数字技术领域，不能据此默认软件或硬件。"),
    "SNO-8d05173086b170d9ad24": ("互联网/AI", "“算子开发”明确为计算/AI 技术语境，未假定具体框架或算法三级。"),
    "SNO-f3756af4152689bb0611": ("互联网/AI", "“AI全栈工程师”明确属于互联网/AI；全栈不应被强行压入前端或后端三级。"),
    "SNO-d6087a47e528741b0653": ("互联网/AI", "“AI编译工程师”明确属于互联网/AI；名称未给出语言或系统平台。"),
    "SNO-f79ac6684e9e00871727": ("互联网/AI", "C++/PHP/Go 研发工程师明确为软件开发，但多语言并不支持指定单一三级。"),
    "SNO-355640918f5270ce9f1a": ("互联网/AI", "“数字工程师”明确数字技术领域，二级方向不足。"),
    "SNO-42a10e0d38e78ab4a373": ("互联网/AI", "“数字技术”可确认互联网/AI 一级，名称过宽不细分。"),
    "SNO-c06599156d452f90d19c": ("互联网/AI", "“数字研发工程师”可确认数字技术一级，未据此推定研发对象。"),
    "SNO-fb71bb61fe9ee35fb03d": ("互联网/AI", "“工程数字技术”明确数字技术方向，未增加行业或技术栈判断。"),
    "SNO-1307860c7ea99544f5f9": ("互联网/AI", "“算力技术研究”明确计算技术领域，但名称不足以确定数据、平台或算法三级。"),
    # Existing formal L3 with a direct occupational match.
    "SNO-f03e79853b6d88b73e61": ("互联网/AI/internet-sales-support/presales-customer", "“售后工程师”核心为客户技术支持；未误归为生活服务或美容服务。"),
    # Clearly named manufacturing, construction, energy, health and media work.
    "SNO-9f06e7226c3290bd0bbc": ("生产制造", "“先进材料与工艺研究员（先进制造技术）”可确认生产制造一级，但材料和工艺不足以锁定具体三级。"),
    "SNO-07d1a7552b8cab4b4420": ("生产制造", "“工艺研究员”明确制造工艺领域，但未说明机械、化工、食品等正式二级。"),
    "SNO-30107cfaf9bf3d74ed25": ("生产制造", "“技术工艺”可确认生产制造一级，不能从名称判断具体工艺行业。"),
    "SNO-f30ec024911cd17a63a2": ("生产制造", "“生产制造”明确对应生产制造一级。"),
    "SNO-7e708dd49f0a4215f9f1": ("生产制造", "“设备管理”在该职业名称中可确认生产制造领域，无法仅由名称指定机械制造或运维三级。"),
    "SNO-c80a334742b4496ce261": ("生产制造", "“材料研发”可确认生产制造一级，材料种类未明确。"),
    "SNO-ccf341451c52d17fc8eb": ("生产制造", "“材料类工程师”可确认材料制造相关一级，未强行指定研发或质量三级。"),
    "SNO-56eedb42f91dedc72c48": ("生产制造", "“船舶技术”可确认制造工程一级，名称不足以判断设计、制造或维修细分。"),
    "SNO-f74cb56c0a45d47b2f13": ("房地产/建筑", "“勘察设计”可确认建筑基础设施领域，不能由名称推定建筑、规划或测绘三级。"),
    "SNO-56f38e90ad6ecc1bab02": ("房地产/建筑", "“管网技术”可确认基础设施方向，但未据此指定市政、水利或建筑三级。"),
    "SNO-22532b4442f5e13f03b2": ("能源/环保/农业", "“动力技术”明确能源动力相关领域，名称没有细分到具体能源技术。"),
    "SNO-cbbfc4a4da51fc7b9de1": ("能源/环保/农业", "“新能源新材料通用技术”至少明确新能源领域，保留一级避免虚构材料或能源细分。"),
    "SNO-f240b0ebb77128509662": ("医疗健康", "“大健康工程师（大健康）”明确医疗健康一级，但服务对象和专业方向不足以到三级。"),
    "SNO-e0459d257f739d9a3791": ("影视/传媒", "“戏曲研究所专业技术”明确表演艺术/传媒领域，名称未说明创作、制作或运营职责。"),
    "SNO-013bd6757f2ae663af51": ("影视/传媒", "“话剧研究所专业技术”可确认影视/传媒一级，未虚构具体岗位工种。"),
    "SNO-30b7727ae851be97401e": ("影视/传媒", "“舞蹈研究所专业技术”可确认影视/传媒一级，三级职责不明。"),
    "SNO-3e93b436c3bf02d53793": ("影视/传媒", "“广播影视政策研究”明确广播影视领域，研究职责不对应现有单一三级。"),
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_exclusive(path: Path, payload: dict) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def atomic_ids(rows: list[dict]) -> set[str]:
    return {atomic_id for row in rows for atomic_id in row.get("source_atomic_unit_ids", [])}


def all_rows(projection: dict) -> list[dict]:
    return [
        *[row for value in projection["category_bubbles"].values() for row in value["occupations"]],
        *[row for value in projection.get("other_bubbles", {}).values() for row in value["occupations"]],
        *[row for value in projection.get("holding_bubbles", {}).values() for row in value["occupations"]],
        *[row for value in projection.get("level1_holding_bubbles", {}).values() for row in value["occupations"]],
        *projection.get("unplaced", []),
    ]


def main() -> None:
    if OUTPUT.exists() or AUDIT_OUTPUT.exists():
        raise FileExistsError("Refusing to overwrite an existing v8 snapshot or its change log")
    projection = load(SOURCE)
    taxonomy_rows = load(TAXONOMY)["rows"]
    categories = {row["category_id"]: row for row in taxonomy_rows}
    l1 = {row["level_1"] for row in taxonomy_rows}
    l2 = {row["category_id"].rsplit("/", 1)[0] for row in taxonomy_rows}
    valid_targets = set(categories) | l2 | l1
    unknown = set(target for target, _ in PLACEMENTS.values()) - valid_targets
    if unknown:
        raise ValueError(f"placement targets missing from frozen taxonomy: {sorted(unknown)}")

    before_rows = all_rows(projection)
    # Parent holding buckets intentionally repeat child rows to render the
    # hierarchy.  Coverage is therefore a set of SNO/atomic IDs, not a raw
    # JSON row count.
    before_ids = {row["standard_occupation_id"] for row in before_rows}
    before_atomic = atomic_ids(before_rows)

    found: dict[str, dict] = {}
    source_locations: dict[str, list[str]] = {identifier: [] for identifier in PLACEMENTS}
    sections = ("category_bubbles", "other_bubbles", "holding_bubbles", "level1_holding_bubbles")
    for section in sections:
        for bucket_id, bucket in projection.get(section, {}).items():
            for row in bucket["occupations"]:
                identifier = row["standard_occupation_id"]
                if identifier in PLACEMENTS:
                    found.setdefault(identifier, row)
                    source_locations[identifier].append(f"{section}/{bucket_id}")
    for row in projection.get("unplaced", []):
        identifier = row["standard_occupation_id"]
        if identifier in PLACEMENTS:
            found.setdefault(identifier, row)
            source_locations[identifier].append("unplaced")
    missing = set(PLACEMENTS) - set(found)
    if missing:
        raise ValueError(f"clear placement entries are not in current level-1 holding buckets: {sorted(missing)}")

    # Remove promoted rows from every old presentation location.  This also
    # removes any parent/child mirror entry, so each promoted SNO is rendered
    # through exactly one new destination.
    for section in sections:
        for bucket in projection.get(section, {}).values():
            bucket["occupations"] = [row for row in bucket["occupations"] if row["standard_occupation_id"] not in PLACEMENTS]
            if "status_counts" in bucket:
                bucket["status_counts"] = dict(sorted(Counter(row["status"] for row in bucket["occupations"]).items()))
    projection["unplaced"] = [row for row in projection.get("unplaced", []) if row["standard_occupation_id"] not in PLACEMENTS]
    projection["level1_holding_bubbles"] = {
        key: value for key, value in projection.get("level1_holding_bubbles", {}).items() if value["occupations"]
    }

    change_log = []
    for identifier, (target, reason) in PLACEMENTS.items():
        row = dict(found[identifier])
        row["reason"] = f"名称级明确归属：{reason}"
        if target in categories:
            row["status"] = "mapped"
            projection["category_bubbles"][target]["occupations"].append(row)
            destination = {"placement_level": "level_3", "bucket_id": target, "path": [categories[target][key] for key in ("level_1", "level_2", "level_3")]}
        else:
            row["status"] = "review"
            if target in l1:
                bucket_id = f"other:level_1:{target}"
                bucket = projection.setdefault("other_bubbles", {}).setdefault(bucket_id, {
                    "bucket_id": bucket_id, "label": "其他岗位", "parent_level": "level_1", "parent_id": target,
                    "level_1": target, "level_2": None, "occupations": [],
                })
                destination = {"placement_level": "level_1", "bucket_id": bucket_id, "path": [target]}
            else:
                cat = next(row for row in taxonomy_rows if row["category_id"].rsplit("/", 1)[0] == target)
                bucket_id = f"other:level_2:{target}"
                bucket = projection.setdefault("other_bubbles", {}).setdefault(bucket_id, {
                    "bucket_id": bucket_id, "label": "其他岗位", "parent_level": "level_2", "parent_id": target,
                    "level_1": cat["level_1"], "level_2": cat["level_2"], "occupations": [],
                })
                destination = {"placement_level": "level_2", "bucket_id": bucket_id, "path": [cat["level_1"], cat["level_2"]]}
            bucket["occupations"].append(row)
        change_log.append({
            "standard_occupation_id": identifier, "label": row["label"], "from_display_bucket_ids": source_locations[identifier],
            "target_category_or_parent_id": target, "status_before": found[identifier]["status"], "status_after": row["status"],
            "reason": row["reason"], **destination,
        })

    for item in projection["category_bubbles"].values():
        item["occupations"].sort(key=lambda row: (row["label"], row["standard_occupation_id"]))
    for item in projection.get("other_bubbles", {}).values():
        item["occupations"].sort(key=lambda row: (row["label"], row["standard_occupation_id"]))

    after_rows = all_rows(projection)
    after_ids = {row["standard_occupation_id"] for row in after_rows}
    after_atomic = atomic_ids(after_rows)
    if after_ids != before_ids:
        raise ValueError("standard occupation coverage changed")
    for identifier in PLACEMENTS:
        if sum(row["standard_occupation_id"] == identifier for row in after_rows) != 1:
            raise ValueError(f"promoted occupation has an unexpected number of display locations: {identifier}")
    if after_atomic != before_atomic:
        raise ValueError("atomic recruitment-role coverage changed")
    if len(after_atomic) != 20964:
        raise ValueError(f"expected 20,964 atomic roles; got {len(after_atomic)}")

    projection["schema_version"] = "name-only-display-projection-v8"
    projection["source_projection"] = str(SOURCE.relative_to(ROOT)).replace("\\", "/")
    projection["validation"] = {
        **projection["validation"],
        "v8_clear_existing_directory_placement_count": len(change_log),
        "v8_clear_existing_l3_placement_count": sum(item["placement_level"] == "level_3" for item in change_log),
        "v8_clear_existing_l1_or_l2_other_count": sum(item["placement_level"] != "level_3" for item in change_log),
        "v8_standard_occupation_unique_count": len(after_ids),
        "v8_atomic_role_unique_count": len(after_atomic),
        "v8_notice": "Only entries with name-level evidence were moved. L1/L2-only placements retain review status and are displayed through the matching existing parent’s 其他岗位 bubble.",
    }
    write_exclusive(OUTPUT, projection)
    write_exclusive(AUDIT_OUTPUT, {
        "source_projection": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "output_projection": str(OUTPUT.relative_to(ROOT)).replace("\\", "/"),
        "processing_method": "codex_name_only_clear_existing_directory_placement",
        "placement_count": len(change_log),
        "entries": sorted(change_log, key=lambda row: (row["placement_level"], row["label"])),
        "validation": {"standard_occupation_unique_count": len(after_ids), "atomic_role_unique_count": len(after_atomic)},
    })
    print(json.dumps({
        "output": str(OUTPUT), "change_log": str(AUDIT_OUTPUT), "placement_count": len(change_log),
        "level_3_count": sum(item["placement_level"] == "level_3" for item in change_log),
        "parent_other_count": sum(item["placement_level"] != "level_3" for item in change_log),
        "atomic_role_unique_count": len(after_atomic),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
