"""Process a manually supplied recruitment CSV/XLSX as an auditable increment.

This command is deliberately local and explicit: it does not download files,
start a scheduler, or expose an upload endpoint.  It compares a supplied file
with the frozen imported snapshot, detects newly introduced *atomic jobs*, and
writes a browser-readable batch catalogue for the existing SNO explorer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from app.domain.recruitment.csv_import import create_snapshot  # noqa: E402
from app.domain.taxonomy.coverage import normalise_title, split_title_units_with_quality  # noqa: E402
from app.agent.recruitment_update_agent import RestrictedRecruitmentUpdateAgent, SimulatedPlanner  # noqa: E402
from run_deepseek_name_classification_trial_v1 import (  # noqa: E402
    api_post, api_post_retry, canonical_base_url, estimate_cost, output_content, read_dotenv, usage_summary,
)


BASELINE_DB = ROOT / "data/processed/recruitment_snapshots.sqlite"
UPDATE_DB = ROOT / "data/processed/recruitment_updates.sqlite"
DISPLAY_DIR = ROOT / "data/processed/record_role_classification_v1/full_drafts/sno_v31_reasonable_primary_v4_display"
DISPLAY_CATALOGUE = DISPLAY_DIR / "update_batches.json"
DAILY_INDEX_SCRIPT = ROOT / "scripts/build_daily_jobs_calendar.py"
SEARCH_INDEX_SCRIPT = ROOT / "scripts/build_job_search_index.py"
SNO_CATALOGUE = ROOT / "data/taxonomy/sno_v3_1/sno_occupation_catalog_v3.1.json"
FINAL_MAPPING = ROOT / "data/processed/record_role_classification_v1/full_drafts/sno_v31_reasonable_primary_v4_real/final.json"
RECORD_ROLES = ROOT / "data/processed/record_role_classification_v1/record_roles.json"
PROCESS_VERSION = "recruitment-update-agent-v2"
OUTPUT_BASE = ROOT / "data/processed/recruitment_updates"
DEFAULT_OUTPUT_BASE = OUTPUT_BASE


def run_output_base() -> Path:
    return ROOT / "data/processed/recruitment_updates" if OUTPUT_BASE == DEFAULT_OUTPUT_BASE else OUTPUT_BASE


class SharedModelBudget:
    """One conservative reservation and audit ledger for every API stage.

    Failed requests keep their reservation because a timeout may have incurred
    charges. No automatic network retries are made under the same reservation.
    """
    def __init__(self, limit: float, path: Path):
        if not 0 < limit <= 1000:
            raise ValueError("invalid budget")
        self.limit, self.path, self.entries, self.committed = limit, path, [], 0.0
        self.uncertain = False
        if path.exists():
            ledger = json.loads(path.read_text(encoding="utf-8"))
            if ledger["limit_usd"] != limit:
                raise ValueError("shared budget limit mismatch")
            self.entries = ledger["requests"]
            self.committed = ledger["committed_usd"]
            self.uncertain = ledger.get("uncertain", False) or any(e.get("status") != "completed" for e in self.entries)
        self._save()

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"limit_usd": self.limit, "committed_usd": self.committed, "uncertain": self.uncertain, "requests": self.entries}, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def call(self, stage: str, base: str, key: str, request: dict[str, Any]):
        if self.uncertain:
            raise RuntimeError("budget_stop_uncertain_previous_request")
        # DeepSeek Flash peak prices, doubled as a safety margin. UTF-8 byte
        # count bounds textual token count conservatively; add protocol margin.
        if request.get("model") != "deepseek-flash":
            raise ValueError("budget only supports deepseek-flash")
        size = len(json.dumps(request, ensure_ascii=False).encode("utf-8")) + 4096
        reserve = 2 * (size * 0.30 + int(request.get("max_tokens", 0)) * 1.20) / 1_000_000
        if self.committed + reserve > self.limit:
            raise RuntimeError("budget_stop")
        entry = {"stage": stage, "reserved_usd": reserve, "status": "in_flight", "request": request}
        self.entries.append(entry)
        self.committed += reserve
        self._save()
        try:
            response = api_post(base, key, request)
            usage = usage_summary(response)
            # Conservative peak-price accounting independent of time/holidays.
            cost = (usage["cached_input_tokens"] * 0.006 + usage["uncached_input_tokens"] * 0.30 + usage["output_tokens"] * 1.20) / 1_000_000
            entry.update({"status": "completed", "usage": usage, "estimated_usd_peak": cost, "response": response})
            self.committed += cost - reserve
            self._save()
            return response, 1
        except Exception as exc:
            entry.update({"status": "uncertain", "error_type": type(exc).__name__})
            self.uncertain = True
            self._save()
            raise

# A generic title has too little occupational identity on its own.  It must be
# sent with the company/industry/major context instead of inheriting a mapping
# merely because an older row used the same words.
GENERIC_TITLE_MARKERS = frozenset({
    "工程师", "开发工程师", "产品经理", "运营", "实习生", "管培生", "管理培训生",
    "助理", "专员", "顾问", "分析师", "设计师", "教师", "销售", "项目经理",
})


def stable_key(*parts: str | None) -> str:
    """A comparison key intentionally excluding source URLs and row positions."""

    text = "\x1f".join(normalise_title(str(part or "")) for part in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def record_key(record: dict[str, Any]) -> str:
    return stable_key(
        record.get("company_name"), record.get("job_title"),
        record.get("recruitment_session"), record.get("recruitment_batch"),
        record.get("location"),
    )


def atomic_key(record: dict[str, Any], title_unit: str) -> str:
    """Identify a job within a company/recruitment context, not by link or row."""

    return stable_key(
        record.get("company_name"), title_unit,
        record.get("recruitment_session"), record.get("recruitment_batch"),
        record.get("location"),
    )


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class UpdateRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS recruitment_update_batches (
              batch_id TEXT PRIMARY KEY, source_file_name TEXT NOT NULL,
              source_checksum TEXT NOT NULL UNIQUE, baseline_snapshot_id TEXT NOT NULL,
              created_at TEXT NOT NULL, mapping_mode TEXT NOT NULL,
              status TEXT NOT NULL, summary_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS recruitment_update_atomic_jobs (
              batch_id TEXT NOT NULL, atomic_key TEXT NOT NULL,
              source_record_key TEXT NOT NULL, source_record_id TEXT NOT NULL,
              title_unit TEXT NOT NULL, result_status TEXT NOT NULL,
              item_json TEXT NOT NULL, updated_at TEXT NOT NULL,
              PRIMARY KEY (batch_id, atomic_key),
              FOREIGN KEY (batch_id) REFERENCES recruitment_update_batches(batch_id)
            );
            CREATE INDEX IF NOT EXISTS idx_update_atomic_key
              ON recruitment_update_atomic_jobs (atomic_key);
            CREATE TABLE IF NOT EXISTS recruitment_update_runs (
              run_id TEXT PRIMARY KEY, batch_id TEXT NOT NULL, started_at TEXT NOT NULL,
              completed_at TEXT, process_version TEXT NOT NULL, mapping_mode TEXT NOT NULL,
              budget_usd REAL NOT NULL, status TEXT NOT NULL, usage_json TEXT NOT NULL,
              error_text TEXT, FOREIGN KEY (batch_id) REFERENCES recruitment_update_batches(batch_id)
            );
            """
        )
        return connection

    def existing_batch(self, checksum: str) -> sqlite3.Row | None:
        with closing(self.connect()) as connection:
            return connection.execute(
                "SELECT * FROM recruitment_update_batches WHERE source_checksum = ?", (checksum,)
            ).fetchone()

    def known_atomic_keys(self) -> set[str]:
        with closing(self.connect()) as connection:
            return {
                row[0] for row in connection.execute(
                    # A failed item remains owned by its original batch and is retried
                    # explicitly.  A fresh file must never create a duplicate item.
                    "SELECT DISTINCT atomic_key FROM recruitment_update_atomic_jobs"
                )
            }

    def save_run(self, run: dict[str, Any]) -> None:
        with closing(self.connect()) as connection, connection:
            connection.execute(
                """INSERT OR REPLACE INTO recruitment_update_runs
                   (run_id, batch_id, started_at, completed_at, process_version, mapping_mode,
                    budget_usd, status, usage_json, error_text)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (run["run_id"], run["batch_id"], run["started_at"], run.get("completed_at"),
                 PROCESS_VERSION, run["mapping_mode"], run["budget_usd"], run["status"],
                 json.dumps(run.get("usage", {}), ensure_ascii=False, sort_keys=True), run.get("error_text")),
            )

    def save_batch(self, batch: dict[str, Any], items: list[dict[str, Any]]) -> None:
        with closing(self.connect()) as connection, connection:
            connection.execute(
                """INSERT INTO recruitment_update_batches
                   (batch_id, source_file_name, source_checksum, baseline_snapshot_id,
                    created_at, mapping_mode, status, summary_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    batch["batch_id"], batch["source_file_name"], batch["source_checksum"],
                    batch["baseline_snapshot_id"], batch["created_at"], batch["mapping_mode"],
                    batch["status"], json.dumps(batch["counts"], ensure_ascii=False, sort_keys=True),
                ),
            )
            connection.executemany(
                """INSERT INTO recruitment_update_atomic_jobs
                   (batch_id, atomic_key, source_record_key, source_record_id, title_unit,
                    result_status, item_json, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        batch["batch_id"], item["atomic_key"], item["source_record_key"],
                        item["source_record_id"], item["title_unit"], item["result_status"],
                        json.dumps(item, ensure_ascii=False, sort_keys=True), now(),
                    )
                    for item in items
                ],
            )

    def batch_for_retry(self, batch_id: str) -> dict[str, Any] | None:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT batch_id, source_file_name, source_checksum, baseline_snapshot_id, created_at, mapping_mode, status, summary_json "
                "FROM recruitment_update_batches WHERE batch_id = ?", (batch_id,)
            ).fetchone()
            if row is None:
                return None
            items = [json.loads(item[0]) for item in connection.execute(
                "SELECT item_json FROM recruitment_update_atomic_jobs WHERE batch_id = ? ORDER BY title_unit, atomic_key", (batch_id,)
            )]
        return {**dict(row), "counts": json.loads(row["summary_json"]), "items": items}

    def replace_batch_items(self, batch: dict[str, Any], items: list[dict[str, Any]]) -> None:
        with closing(self.connect()) as connection, connection:
            connection.execute(
                "UPDATE recruitment_update_batches SET mapping_mode = ?, status = ?, summary_json = ? WHERE batch_id = ?",
                (batch["mapping_mode"], batch["status"], json.dumps(batch["counts"], ensure_ascii=False, sort_keys=True), batch["batch_id"]),
            )
            connection.executemany(
                "UPDATE recruitment_update_atomic_jobs SET result_status = ?, item_json = ?, updated_at = ? WHERE batch_id = ? AND atomic_key = ?",
                [(item["result_status"], json.dumps(item, ensure_ascii=False, sort_keys=True), now(), batch["batch_id"], item["atomic_key"]) for item in items],
            )

    def archive_and_remove_batch(self, batch_id: str, archive_root: Path) -> dict[str, Any]:
        """Create a recoverable audit archive before removing one active batch.

        This is deliberately not a general data purge: the batch payload,
        runs, a byte-for-byte SQLite backup and its run artifacts are retained
        under ``archive_root``.  Removing the active rows lets the identical
        source checksum be explicitly re-tested after the user approves it.
        """
        batch = self.batch_for_retry(batch_id)
        if batch is None:
            raise RuntimeError(f"Unknown update batch: {batch_id}")
        archive_dir = archive_root / f"{batch_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        archive_dir.mkdir(parents=True, exist_ok=False)
        (archive_dir / "batch.json").write_text(json.dumps({**batch, "archived_at": now()}, ensure_ascii=False, indent=2), encoding="utf-8")
        with closing(self.connect()) as connection:
            runs = [dict(row) for row in connection.execute(
                "SELECT * FROM recruitment_update_runs WHERE batch_id = ? ORDER BY started_at", (batch_id,)
            )]
            with sqlite3.connect(archive_dir / "recruitment_updates_before_removal.sqlite") as backup:
                connection.backup(backup)
        (archive_dir / "runs.json").write_text(json.dumps(runs, ensure_ascii=False, indent=2), encoding="utf-8")
        source_run_dir = run_output_base() / batch_id
        if source_run_dir.exists():
            # A batch id is deterministic for a source checksum.  Moving (not
            # copying) its ledger out of the active run root is essential: a
            # user-approved re-test of the identical file must start with a
            # fresh budget, never inherit the prior batch's reservations.
            shutil.move(str(source_run_dir), str(archive_dir / "run_artifacts"))
        with closing(self.connect()) as connection, connection:
            connection.execute("DELETE FROM recruitment_update_runs WHERE batch_id = ?", (batch_id,))
            connection.execute("DELETE FROM recruitment_update_atomic_jobs WHERE batch_id = ?", (batch_id,))
            connection.execute("DELETE FROM recruitment_update_batches WHERE batch_id = ?", (batch_id,))
        return {"batch_id": batch_id, "archive_dir": str(archive_dir), "removed_atomic_jobs": len(batch["items"]), "prior_counts": batch["counts"]}

    def batches_for_display(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                "SELECT batch_id, source_file_name, baseline_snapshot_id, created_at, mapping_mode, status, summary_json "
                "FROM recruitment_update_batches ORDER BY created_at DESC"
            ).fetchall()
            result = []
            for row in rows:
                items = [json.loads(item[0]) for item in connection.execute(
                    "SELECT item_json FROM recruitment_update_atomic_jobs WHERE batch_id = ? ORDER BY title_unit, atomic_key",
                    (row["batch_id"],),
                )]
                result.append({
                    "batch_id": row["batch_id"], "source_file_name": row["source_file_name"],
                    "baseline_snapshot_id": row["baseline_snapshot_id"], "created_at": row["created_at"],
                    "mapping_mode": row["mapping_mode"], "status": row["status"],
                    "counts": json.loads(row["summary_json"]), "items": items,
                })
            return result


def imported_baseline_records(database: Path) -> tuple[str, list[dict[str, Any]]]:
    """Return every persisted snapshot, not only the most recently imported file."""
    with closing(sqlite3.connect(database)) as connection:
        connection.row_factory = sqlite3.Row
        snapshots = connection.execute("SELECT snapshot_id FROM dataset_snapshots ORDER BY imported_at").fetchall()
        if not snapshots:
            raise RuntimeError("No imported recruitment snapshot is available for the update baseline")
        rows = connection.execute(
            """SELECT record_id, company_name, job_title, recruitment_session, recruitment_batch,
                      location, industry_category, company_type, recruitment_url, announcement_url
                 FROM recruitment_records
                WHERE eligible_for_market_analysis = 1 AND record_status != 'duplicate'""",
        ).fetchall()
    # The joined identity is stable across snapshots; it is only an audit
    # pointer, never a rule saying that dates decide whether a role is new.
    return "all-imported-snapshots:" + str(len(snapshots)), [dict(row) for row in rows]


def accepted_units(record: dict[str, Any]) -> list[str]:
    return [unit.unit for unit in split_title_units_with_quality(record.get("job_title") or "") if unit.gate_status == "accepted"]


def cached_mappings() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, str]]]:
    """Reuse the completed mapping for an exactly matching prior title only."""

    roles = {row["record_role_id"]: row for row in json.loads(RECORD_ROLES.read_text(encoding="utf-8"))["roles"]}
    final = json.loads(FINAL_MAPPING.read_text(encoding="utf-8"))
    mappings: dict[str, dict[str, Any]] = {}
    for row in final["records"]:
        source = roles.get(row["record_role_id"])
        if source and row.get("display_eligibility") == "eligible":
            title = source["source_title"]
            candidate = {**row["effective_result"], "_reuse_source": {"industry_category": source.get("industry_category"), "source_title": title}}
            previous = mappings.get(title)
            if previous is None:
                mappings[title] = candidate
            elif previous.get("target_category_id") != candidate.get("target_category_id") or previous.get("_reuse_source", {}).get("industry_category") != candidate["_reuse_source"]["industry_category"]:
                mappings[title] = {"_conflicting_sources": True}
    catalogue = json.loads(SNO_CATALOGUE.read_text(encoding="utf-8"))
    categories: dict[str, dict[str, str]] = {}
    for level_1 in catalogue["taxonomy"]:
        for level_2 in level_1["level_2"]:
            categories[level_2["level_2_id"]] = {"level_1": level_1["name"], "level_2": level_2["name"], "level_3": ""}
            for level_3 in level_2["level_3"]:
                categories[level_3["level_3_id"]] = {"level_1": level_1["name"], "level_2": level_2["name"], "level_3": level_3["name"]}
    return mappings, categories


def must_use_context(title: str) -> bool:
    normalised = normalise_title(title)
    return normalised in {normalise_title(marker) for marker in GENERIC_TITLE_MARKERS}


def evidence_is_sufficient(item: dict[str, Any], mapping: dict[str, Any], categories: dict[str, dict[str, str]], *, reuse: bool = False) -> bool:
    """Conservative role-specific evidence gate; neighbouring titles are not evidence."""
    if mapping.get("status") != "mapped":
        return not reuse
    title = normalise_title(item.get("title_unit") or "")
    category = categories.get(mapping.get("target_category_id"))
    if not title or not category or mapping.get("target_level") not in {"level_2", "level_3"}:
        return False
    if bool(category.get("level_3")) != (mapping.get("target_level") == "level_3"):
        return False
    if reuse:
        source = mapping.get("_reuse_source") or {}
        evidence = normalise_title(mapping.get("title_evidence") or "")
        if (must_use_context(title) or mapping.get("_conflicting_sources") or not evidence or evidence not in title
                or normalise_title(source.get("source_title") or "") != title
                or not source.get("industry_category") or not item.get("industry_category")
                or normalise_title(source["industry_category"]) != normalise_title(item["industry_category"])):
            return False
    if mapping.get("target_level") == "level_3":
        evidence = normalise_title(mapping.get("level_3_evidence") or "")
        if not evidence or evidence not in title:
            return False
        if category["level_3"] == "预测与统计学习" and not any(normalise_title(word) in title for word in ("机器学习", "统计学习", "预测", "machine learning", "predictive")):
            return False
    return True


def model_context(item: dict[str, Any]) -> dict[str, str | None]:
    """Minimum context sufficient for a cautious role placement decision."""
    return {key: item.get(key) for key in (
        "company_name", "company_type", "industry_category", "location",
        "recruitment_session", "recruitment_batch", "raw_job_title",
    )}


class DeepSeekDecisionPlanner:
    """A bounded LLM planner that can choose only host-provided tools."""
    def __init__(self, budget_usd: float, shared_budget: SharedModelBudget | None = None) -> None:
        self.budget_usd = budget_usd
        self.shared_budget = shared_budget
        self.spent_usd = 0.0
        self.calls = 0
        self.errors: list[str] = []

    def choose(self, item: dict[str, Any], history: list[dict[str, Any]], allowed: set[str]) -> dict[str, str]:
        reserve = 0.02
        if self.spent_usd + reserve > self.budget_usd:
            return {"action": "hold", "reason": "剩余预算不足以安全发起下一次模型决策。"}
        dotenv = read_dotenv(ROOT / ".env")
        key = os.getenv("DEEPSEEK_API_KEY") or dotenv.get("DEEPSEEK_API_KEY")
        if not key:
            return {"action": "hold", "reason": "后端未配置 DEEPSEEK_API_KEY，无法请求模型决策。"}
        context = {"title_unit": item.get("title_unit"), "raw_job_title": item.get("raw_job_title"), **model_context(item), "has_reusable_mapping": item.get("has_reusable_mapping"), "split_review_needed": item.get("split_review_needed")}
        steps = [{"action": step["action"], "outcome": step["result"].get("outcome"), **({"accepted_units": step["result"]["accepted_units"]} if "accepted_units" in step["result"] else {})} for step in history]
        request = {"model": os.getenv("DEEPSEEK_MODEL") or dotenv.get("DEEPSEEK_MODEL") or "deepseek-flash", "messages": [
            {"role": "system", "content": "你是受限招聘更新决策器。只能从 allowed_actions 选择下一步；不能执行代码、不能创建目录、不能修改历史分类、不能声称统计数。根据当前岗位和工具结果返回 JSON：action,reason。依据不足选择hold。"},
            {"role": "user", "content": json.dumps({"item": context, "tool_history": steps, "allowed_actions": sorted(allowed)}, ensure_ascii=False)},
        ], "response_format": {"type": "json_object"}, "thinking": {"type": "disabled"}, "temperature": 0, "max_tokens": 180}
        try:
            base = canonical_base_url(os.getenv("DEEPSEEK_BASE_URL") or dotenv.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com")
            response, _ = self.shared_budget.call("decision", base, key, request) if self.shared_budget else api_post_retry(base, key, request)
            cost = estimate_cost(usage_summary(response), datetime.now(timezone.utc))
            self.spent_usd += cost["estimated_usd"]; self.calls += 1
            decision = json.loads(output_content(response))
            if not isinstance(decision, dict) or decision.get("action") not in allowed or not isinstance(decision.get("reason"), str):
                return {"action": "hold", "reason": "模型决策不符合受限工具契约。"}
            return {"action": decision["action"], "reason": decision["reason"][:240]}
        except Exception as exc:
            self.errors.append(str(exc))
            return {"action": "hold", "reason": "模型决策调用失败，程序保留待确认。"}

    def choose_batch(self, items: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
        """Choose one bounded next tool per small batch, not per HTTP call."""
        dotenv = read_dotenv(ROOT / ".env")
        key = os.getenv("DEEPSEEK_API_KEY") or dotenv.get("DEEPSEEK_API_KEY")
        if not key:
            return {item["atomic_key"]: {"action": "hold", "reason": "后端未配置 DEEPSEEK_API_KEY。"} for item in items}
        # ``classify`` does not assert a taxonomy placement.  It asks the
        # program to run its separate, validated mapping tool.  Giving the
        # decision model that distinction is important: a concrete job title
        # without enough evidence for a *final* placement should normally be
        # sent to that tool, not silently held here.
        records = [{
            "id": item["atomic_key"],
            "title": item["title_unit"],
            "context": model_context(item),
            "safe_reuse": item.get("safe_reuse"),
            "title_is_generic": must_use_context(item["title_unit"]),
            "split_checked": item.get("split_review_needed"),
            "classification_tool_available": True,
        } for item in items]
        request = {"model": os.getenv("DEEPSEEK_MODEL") or dotenv.get("DEEPSEEK_MODEL") or "deepseek-flash", "messages": [
            {"role": "system", "content": "你是受限招聘更新决策器。对每项只能选择 reuse、classify 或 hold；拆分已由程序完成并给出单岗位。reuse 仅当 safe_reuse=true，且不得修改已有分类。classify 的含义是请求后续受限分类工具判断候选目录，绝不是现在断言最终三级分类；其输出仍会由程序做证据和目录校验。只要岗位名称能识别为具体职业功能，而又不能安全复用，就应选择 classify，即使当前描述不足以自行确定目录。只有 title_is_generic=true、标题不是职业名称、或上下文不足以识别任何职业身份时才选择 hold。不得因“尚不能确认最终分类”而把具体职位 hold。返回 JSON {decisions:[{id,action,reason}]}，每个 id 恰好一项。"},
            {"role": "user", "content": json.dumps({"items": records}, ensure_ascii=False)},
        ], "response_format": {"type": "json_object"}, "thinking": {"type": "disabled"}, "temperature": 0, "max_tokens": min(1800, 80 * len(items) + 120)}
        try:
            base = canonical_base_url(os.getenv("DEEPSEEK_BASE_URL") or dotenv.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com")
            response, _ = self.shared_budget.call("decision", base, key, request) if self.shared_budget else api_post_retry(base, key, request)
            cost = estimate_cost(usage_summary(response), datetime.now(timezone.utc)); self.spent_usd += cost["estimated_usd"]; self.calls += 1
            returned = {str(x.get("id")): x for x in json.loads(output_content(response)).get("decisions", []) if isinstance(x, dict)}
            return {item["atomic_key"]: ({"action": row.get("action"), "reason": str(row.get("reason", ""))[:240]} if row and row.get("action") in {"reuse", "classify", "hold"} else {"action": "hold", "reason": "批量模型决策不符合契约。"}) for item in items for row in [returned.get(item["atomic_key"]) ]}
        except Exception as exc:
            self.errors.append(str(exc)); return {item["atomic_key"]: {"action": "hold", "reason": "模型决策调用失败，程序保留待确认。"} for item in items}


def map_unknown_items(batch_dir: Path, items: list[dict[str, Any]], mode: str, budget_usd: float, shared_budget: SharedModelBudget | None = None, fault_inject_invalid: bool = False) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Use the existing versioned SNO mapping executor only when explicitly requested."""

    if not items or mode == "cached":
        return {}, {"api_calls": 0, "estimated_usd": 0.0}
    # The existing executor owns prompt versioning, raw-response retention,
    # retry behaviour and mapping-contract validation.  This small invocation
    # scopes it to unseen update titles rather than reclassifying the baseline.
    import run_sno_v31_full_draft as sno_runner  # type: ignore
    from run_sno_v31_full_draft import BATCH, Engine, body, mp, rp, levels  # type: ignore
    from sno_v31_mapping_contract import validate  # type: ignore
    if shared_budget:
        def tracked_post(base: str, key: str, request: dict[str, Any]):
            prompt = request["messages"][0]["content"]
            stage = "repair" if "上一次输出未通过" in prompt else "review" if prompt.startswith("AI合理性复核") else "classification"
            return shared_budget.call(stage, base, key, request)
        sno_runner.api_post_retry = tracked_post
    else:
        sno_runner.api_post_retry = api_post_retry

    catalogue = json.loads(SNO_CATALOGUE.read_text(encoding="utf-8"))
    title_rows = [{"occupation_id": "UP-" + item["atomic_key"], "title": item["title_unit"], "context": model_context(item)} for item in items]
    args = SimpleNamespace(simulate=False, budget_usd=budget_usd)
    engine = Engine(batch_dir / "mapping_run", catalogue, args)
    mapped: list[dict[str, Any]] = []
    processing_errors: list[str] = []
    for index in range(0, len(title_rows), BATCH):
        group = title_rows[index:index + BATCH]
        try:
            mapped.extend(engine.call("map", index // BATCH + 1, body(mp(catalogue["taxonomy"]), {"occupations": group}), group))
        except Exception as exc:
            processing_errors.append(f"map batch {index // BATCH + 1}: {exc}")
    expected = {row["occupation_id"] for row in title_rows}
    by_id = {row["occupation_id"]: row for row in mapped if row.get("occupation_id") in expected}
    if fault_inject_invalid and by_id:
        occupation_id = next(iter(by_id))
        by_id[occupation_id] = {**by_id[occupation_id], "status": "mapped", "target_category_id": "FAULT-INJECTED-INVALID-ID", "target_level": "level_3"}
        (batch_dir / "fault_injection.json").write_text(json.dumps({"test_only": True, "injected_result": by_id[occupation_id]}, ensure_ascii=False, indent=2), encoding="utf-8")
    level_by_id = levels(catalogue)
    invalid_ids: list[str] = []
    for occupation_id, mapping in by_id.items():
        try:
            validate({"sample_id": occupation_id, **{key: mapping.get(key) for key in ("status", "target_category_id", "candidate_category_ids", "target_level", "reason", "level_3_evidence")}}, level_by_id, set(catalogue["retired_category_ids"]))
        except Exception:
            invalid_ids.append(occupation_id)
    # One bounded corrective request for malformed/invalid mappings.  It uses a
    # separate, persisted run directory so the original charged response and
    # its validation failure remain auditable and resumable.
    if invalid_ids:
        repair_items = [row for row in title_rows if row["occupation_id"] in invalid_ids]
        first_ledger = json.loads((batch_dir / "mapping_run" / "ledger.json").read_text(encoding="utf-8"))
        remaining_budget = max(0.0, budget_usd - first_ledger.get("spent_usd", 0.0))
        repair_args = SimpleNamespace(simulate=False, budget_usd=remaining_budget)
        repair_engine = Engine(batch_dir / "mapping_repair", catalogue, repair_args)
        repaired: list[dict[str, Any]] = []
        for index in range(0, len(repair_items), BATCH):
            group = repair_items[index:index + BATCH]
            corrective_prompt = mp(catalogue["taxonomy"]) + " 上一次输出未通过结构校验。只返回每个原 occupation_id 一项，严格遵守JSON字段和目录ID。"
            try:
                repaired.extend(repair_engine.call("map", index // BATCH + 1, body(corrective_prompt, {"occupations": group, "invalid_results": [by_id[row["occupation_id"]] for row in group], "validation_error": "结构或目录 ID 不符合契约"}), group))
            except Exception as exc:
                processing_errors.append(f"repair batch {index // BATCH + 1}: {exc}")
        for row in repaired:
            if row.get("occupation_id") in invalid_ids:
                by_id[row["occupation_id"]] = row
    reviewed: list[dict[str, Any]] = []
    for index in range(0, len(title_rows), BATCH):
        group = title_rows[index:index + BATCH]
        request_records = [{"occupation_id": item["occupation_id"], "title": item["title"], "context": item["context"], "current": by_id[item["occupation_id"]]} for item in group if item["occupation_id"] in by_id]
        if not request_records:
            continue
        try:
            reviewed.extend(engine.call("review", index // BATCH + 1, body(rp(catalogue["taxonomy"]), {"records": request_records}), group))
        except Exception as exc:
            processing_errors.append(f"review batch {index // BATCH + 1}: {exc}")
    review_by_id = {row["occupation_id"]: row for row in reviewed}
    result: dict[str, dict[str, Any]] = {}
    for item in title_rows:
        mapping = by_id.get(item["occupation_id"])
        if mapping is None:
            continue
        try:
            validate({"sample_id": item["occupation_id"], **{key: mapping.get(key) for key in ("status", "target_category_id", "candidate_category_ids", "target_level", "reason", "level_3_evidence")}}, level_by_id, set(catalogue["retired_category_ids"]))
        except Exception:
            # The raw response has already been retained by Engine.  This item
            # stays pending and is never promoted from an invalid JSON result.
            continue
        review = review_by_id.get(item["occupation_id"], {})
        suggestion = review.get("suggested_target_category_id")
        if review.get("verdict") == "correction_required" and suggestion in level_by_id:
            mapping = {**mapping, "status": "mapped", "target_category_id": suggestion, "target_level": level_by_id[suggestion], "candidate_category_ids": [], "reason": review.get("issue") or "review correction"}
        try:
            validate({"sample_id": item["occupation_id"], **{key: mapping.get(key) for key in ("status", "target_category_id", "candidate_category_ids", "target_level", "reason", "level_3_evidence")}}, level_by_id, set(catalogue["retired_category_ids"]))
            if mapping.get("status") == "mapped" and mapping.get("target_level") not in {"level_2", "level_3"}:
                raise ValueError("mapping must target level 2 or 3")
        except Exception:
            continue
        result[item["occupation_id"].removeprefix("UP-")] = mapping
    ledgers = [batch_dir / "mapping_run" / "ledger.json", batch_dir / "mapping_repair" / "ledger.json"]
    ledger_rows = [json.loads(path.read_text(encoding="utf-8")) for path in ledgers if path.exists()]
    return result, {"api_calls": sum(len(row.get("responses", [])) for row in ledger_rows), "estimated_usd": sum(row.get("spent_usd", 0.0) for row in ledger_rows), "ledgers": [str(path) for path in ledgers if path.exists()], "invalid_initial_results": len(invalid_ids), "errors": processing_errors}


def display_catalogue(repository: UpdateRepository) -> None:
    DISPLAY_CATALOGUE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "recruitment-update-batches-v1",
        "generated_at": now(),
        "batches": repository.batches_for_display(),
    }
    DISPLAY_CATALOGUE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # The daily calendar is user-facing and follows source update dates.  Keep
    # it current whenever the real display catalogue changes; tests may point
    # DISPLAY_CATALOGUE at a temporary output and must not rewrite production data.
    if DISPLAY_CATALOGUE == DISPLAY_DIR / "update_batches.json":
        subprocess.run([sys.executable, str(DAILY_INDEX_SCRIPT)], cwd=ROOT, check=True)
        subprocess.run([sys.executable, str(SEARCH_INDEX_SCRIPT)], cwd=ROOT, check=True)
    elif OUTPUT_BASE != DEFAULT_OUTPUT_BASE:
        from build_daily_jobs_calendar import DATE_FROM, update_items
        items = update_items(payload)
        daily = {"schema_version": "daily-jobs-v1", "date_from": DATE_FROM, "date_field": "source_updated_at", "statistics": {"items": len(items), "baseline_items": 0, "update_items": len(items)}, "items": items}
        (DISPLAY_CATALOGUE.parent / "daily_jobs_v1.json").write_text(json.dumps(daily, ensure_ascii=False, indent=2), encoding="utf-8")


def retry_failed_batch(repository: UpdateRepository, batch_id: str, mode: str, budget_usd: float) -> dict[str, Any]:
    batch = repository.batch_for_retry(batch_id)
    if batch is None:
        raise RuntimeError(f"Unknown update batch: {batch_id}")
    failed = [item for item in batch["items"] if item.get("result_status") == "failed" or item.get("retry_eligible")]
    if not failed:
        return {"status": "nothing_to_retry", "batch_id": batch_id}
    _, categories = cached_mappings()
    batch_dir = run_output_base() / batch_id
    retry_dir = batch_dir / ("retry-" + hashlib.sha256(now().encode()).hexdigest()[:12])
    budget = SharedModelBudget(budget_usd, retry_dir / "shared_budget.json") if mode == "model" else None
    results, usage = map_unknown_items(retry_dir, failed, mode, budget_usd, budget)
    if budget:
        usage.update({"shared_budget_ledger": str(budget.path), "conservative_committed_usd": budget.committed})
    for item in failed:
        mapping = results.get(item["atomic_key"])
        if mapping is None:
            continue
        item.pop("retry_eligible", None)
        item["mapping_status"] = mapping.get("status", "review")
        item["reason"] = mapping.get("reason")
        category = categories.get(mapping.get("target_category_id"))
        if mapping.get("status") == "mapped" and category:
            item.update({"result_status": "classified", "category_id": mapping.get("target_category_id"), **category})
        elif mapping.get("status") in {"review", "taxonomy_gap", "multi_role", "non_role_text"}:
            item["result_status"] = "pending"
    counts = Counter(item["result_status"] for item in batch["items"])
    batch["mapping_mode"] = mode
    batch["status"] = "completed" if not counts["failed"] else "completed_with_failures"
    batch["counts"] = {**batch["counts"], "classified": counts["classified"], "pending": counts["pending"], "failed": counts["failed"]}
    repository.replace_batch_items(batch, batch["items"])
    repository.save_run({"run_id": f"RUN-{batch_id}-retry-{hashlib.sha256(now().encode()).hexdigest()[:8]}", "batch_id": batch_id,
                         "started_at": now(), "completed_at": now(), "mapping_mode": mode, "budget_usd": budget_usd,
                         "status": batch["status"], "usage": usage})
    display_catalogue(repository)
    return {"status": "retried", "batch_id": batch_id, "counts": batch["counts"]}


def archive_and_remove_batch(repository: UpdateRepository, batch_id: str) -> dict[str, Any]:
    if repository.path != UPDATE_DB:
        raise RuntimeError("archiving an active batch is restricted to the formal update database")
    result = repository.archive_and_remove_batch(batch_id, ROOT / "data/processed/recruitment_update_archives")
    display_catalogue(repository)
    return {"status": "archived_and_removed", **result}


def main() -> None:
    global DISPLAY_CATALOGUE, OUTPUT_BASE
    parser = argparse.ArgumentParser(description="Process a manually supplied recruitment CSV/XLSX update")
    parser.add_argument("source", type=Path, nargs="?")
    parser.add_argument("--retry-failed", metavar="BATCH_ID", help="retry only failed atomic jobs in an existing batch")
    parser.add_argument("--archive-and-remove-batch", metavar="BATCH_ID", help="archive one approved formal batch, withdraw it from display, and allow its source to be re-tested")
    parser.add_argument("--mapping-mode", choices=("cached", "model"), default="cached", help="model makes explicit API calls only for unseen titles")
    parser.add_argument("--budget-usd", type=float, default=2.0)
    parser.add_argument("--baseline-database", type=Path, default=BASELINE_DB)
    parser.add_argument("--update-database", type=Path, default=UPDATE_DB)
    parser.add_argument("--sandbox-dir", type=Path, help="isolate all mutable update outputs under this directory")
    parser.add_argument("--budget-ledger", type=Path, help="shared budget ledger for sequential isolated runs")
    parser.add_argument("--fault-inject-invalid", action="store_true", help="isolated test only: replace one initial model result to exercise repair")
    args = parser.parse_args()

    if args.sandbox_dir:
        isolated = args.sandbox_dir.resolve()
        isolated.mkdir(parents=True, exist_ok=True)
        args.baseline_database = isolated / "baseline.sqlite"
        args.update_database = isolated / "updates.sqlite"
        DISPLAY_CATALOGUE = isolated / "display" / "update_batches.json"
        OUTPUT_BASE = isolated / "runs"
    if args.fault_inject_invalid and not args.sandbox_dir:
        raise ValueError("fault injection is allowed only with --sandbox-dir")

    repository = UpdateRepository(args.update_database)
    if args.archive_and_remove_batch:
        if args.sandbox_dir:
            raise ValueError("archive-and-remove is only available for the formal update database")
        print(json.dumps(archive_and_remove_batch(repository, args.archive_and_remove_batch), ensure_ascii=False, indent=2))
        return
    if args.retry_failed:
        print(json.dumps(retry_failed_batch(repository, args.retry_failed, args.mapping_mode, args.budget_usd), ensure_ascii=False, indent=2))
        return
    if args.source is None:
        raise SystemExit("source is required unless --retry-failed is used")
    snapshot = create_snapshot(args.source, source_name="manual recruitment update")
    duplicate = repository.existing_batch(snapshot.source_checksum)
    if duplicate:
        display_catalogue(repository)
        print(json.dumps({"status": "already_processed", "batch_id": duplicate["batch_id"], "message": "Same source checksum was not imported again."}, ensure_ascii=False))
        return

    baseline_id, baseline_records = imported_baseline_records(args.baseline_database)
    baseline_atomic = {atomic_key(record, unit) for record in baseline_records for unit in accepted_units(record)}
    prior_atomic = repository.known_atomic_keys()
    candidate_items: list[dict[str, Any]] = []
    candidate_by_atomic_key: dict[str, dict[str, Any]] = {}
    for record in snapshot.records:
        payload = record.model_dump(mode="json")
        if not payload["eligible_for_market_analysis"] or payload["record_status"] != "valid":
            continue
        for title_unit in accepted_units(payload):
            key = atomic_key(payload, title_unit)
            if key in baseline_atomic or key in prior_atomic:
                continue
            candidate = {
                "atomic_key": key, "source_record_key": record_key(payload), "source_record_id": payload["record_id"],
                "title_unit": title_unit, "raw_job_title": payload["job_title"], "company_name": payload["company_name"],
                "company_type": payload["company_type"], "location": payload["location"], "industry_category": payload["industry_category"],
                "recruitment_session": payload["recruitment_session"], "recruitment_batch": payload["recruitment_batch"],
                "recruitment_url": payload["recruitment_url"], "announcement_url": payload["announcement_url"],
                "source_updated_at": payload["updated_at"],
                "updated_at_original_text": payload.get("raw_payload", {}).get("更新时间") or "",
                # Preserve every incoming source-record pointer for audit, while
                # importing the stable atomic job once.
                "source_record_ids_in_file": [payload["record_id"]],
            }
            existing = candidate_by_atomic_key.get(key)
            if existing is not None:
                existing["source_record_ids_in_file"].append(payload["record_id"])
                continue
            candidate_by_atomic_key[key] = candidate
            candidate_items.append(candidate)

    # A reordered export, a link-only change, or a file containing only the
    # existing baseline must not create an empty batch or a browser notice.
    if not candidate_items:
        display_catalogue(repository)
        print(json.dumps({"status": "no_new_atomic_jobs", "message": "No new atomic jobs were imported."}, ensure_ascii=False))
        return

    batch_id = "UPD-" + hashlib.sha256((snapshot.source_checksum + baseline_id).encode("utf-8")).hexdigest()[:16]
    batch_dir = run_output_base() / batch_id
    cached, categories = cached_mappings()
    if args.budget_ledger and not args.sandbox_dir:
        raise ValueError("external shared ledger is restricted to isolated runs")
    shared_budget = SharedModelBudget(args.budget_usd, args.budget_ledger or batch_dir / "shared_budget.json") if args.mapping_mode == "model" else None
    planner = DeepSeekDecisionPlanner(args.budget_usd, shared_budget) if args.mapping_mode == "model" else SimulatedPlanner()
    usage: dict[str, Any] = {"api_calls": 0, "estimated_usd": 0.0, "errors": [], "agent_mode": "deepseek_decision_loop" if args.mapping_mode == "model" else "simulated_tools"}

    def decide_item(source_item: dict[str, Any]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        reusable = cached.get(source_item["title_unit"])
        safe_reuse = reusable is not None and evidence_is_sufficient(source_item, reusable, categories, reuse=True)
        agent_input = {**source_item, "has_reusable_mapping": safe_reuse,
                       "model_enabled": args.mapping_mode == "model",
                       "job_title": source_item.get("raw_job_title"),
                       "split_review_needed": len(accepted_units({"job_title": source_item.get("raw_job_title")})) > 1}

        def reuse(_: dict[str, Any]) -> dict[str, Any]:
            if not safe_reuse:
                return {"terminal": False, "mapping": None, "outcome": "reuse_not_safe"}
            return {"terminal": True, "mapping": reusable, "outcome": "reused"}
        def split(current: dict[str, Any]) -> dict[str, Any]:
            return {"terminal": False, "accepted_units": accepted_units(current), "outcome": "split_checked"}
        def classify(current: dict[str, Any]) -> dict[str, Any]:
            planner_spent = getattr(planner, "spent_usd", 0.0)
            remaining = max(0.0, args.budget_usd - float(usage["estimated_usd"]) - planner_spent)
            mappings, one_usage = map_unknown_items(batch_dir / "agent" / current["atomic_key"], [current], args.mapping_mode, remaining, shared_budget, args.fault_inject_invalid)
            usage["api_calls"] += one_usage.get("api_calls", 0)
            usage["estimated_usd"] += one_usage.get("estimated_usd", 0.0)
            usage["errors"].extend(one_usage.get("errors", []))
            return {"terminal": bool(mappings.get(current["atomic_key"])), "mapping": mappings.get(current["atomic_key"]), "outcome": "classified" if mappings else "classification_unavailable"}
        def hold(_: dict[str, Any]) -> dict[str, Any]:
            return {"terminal": True, "mapping": None, "outcome": "held"}
        outcome, trace = RestrictedRecruitmentUpdateAgent(planner, {"reuse": reuse, "request_split": split, "classify": classify, "repair": classify, "hold": hold}).run_item(agent_input)
        return outcome.get("mapping"), trace

    resolved: list[tuple[dict[str, Any], dict[str, Any] | None, list[dict[str, Any]]]] = []
    if args.mapping_mode == "model":
        # One planner call per small cohort; only the cohort that the Agent
        # explicitly routes to classify reaches the expensive mapping tool.
        for start in range(0, len(candidate_items), 24):
            cohort = candidate_items[start:start + 24]
            inputs = []
            for item in cohort:
                reusable = cached.get(item["title_unit"])
                safe = reusable is not None and evidence_is_sufficient(item, reusable, categories, reuse=True)
                inputs.append({**item, "safe_reuse": safe, "split_review_needed": len(accepted_units({"job_title": item["raw_job_title"]})) > 1})
            decisions = planner.choose_batch(inputs)
            classify_items = [item for item in inputs if decisions[item["atomic_key"]]["action"] == "classify"]
            remaining = max(0.0, args.budget_usd - shared_budget.committed) if shared_budget else args.budget_usd
            mappings, one_usage = map_unknown_items(batch_dir / "agent" / f"cohort-{start // 24 + 1}", classify_items, "model", remaining, shared_budget, args.fault_inject_invalid)
            usage["api_calls"] += one_usage.get("api_calls", 0); usage["estimated_usd"] += one_usage.get("estimated_usd", 0.0); usage["errors"].extend(one_usage.get("errors", []))
            for item in inputs:
                decision = decisions[item["atomic_key"]]
                action = decision["action"]
                reused_mapping = cached.get(item["title_unit"]) if action == "reuse" and item["safe_reuse"] else None
                mapping = reused_mapping or (mappings.get(item["atomic_key"]) if action == "classify" else None)
                outcome = "reused" if reused_mapping else "classified" if mapping else "held"
                resolved.append((item, mapping, [{"action": action, "reason": decision["reason"], "result": {"terminal": True, "outcome": outcome}}]))
    else:
        resolved = [(item, *decide_item(item)) for item in candidate_items]

    for item, mapping, agent_trace in resolved:
        item["agent_trace"] = agent_trace
        if mapping is not None:
            from run_sno_v31_full_draft import levels  # type: ignore
            from sno_v31_mapping_contract import validate  # type: ignore
            catalogue = json.loads(SNO_CATALOGUE.read_text(encoding="utf-8"))
            try:
                validate({"sample_id": "UP-" + item["atomic_key"], **{key: mapping.get(key) for key in ("status", "target_category_id", "candidate_category_ids", "target_level", "reason", "level_3_evidence")}}, levels(catalogue), set(catalogue["retired_category_ids"]))
                if mapping.get("status") == "mapped" and mapping.get("target_level") not in {"level_2", "level_3"}:
                    raise ValueError("invalid mapping level")
                if not evidence_is_sufficient(item, mapping, categories):
                    raise ValueError("role-specific classification evidence insufficient")
            except Exception:
                mapping = None
        if mapping is None:
            item.update({"result_status": "pending", "retry_eligible": args.mapping_mode == "model", "mapping_status": "agent_hold", "reason": "受限决策循环未取得经程序校验的分类；保留待确认。"})
            continue
        item["mapping_status"] = mapping.get("status", "review")
        item["reason"] = mapping.get("reason")
        category = categories.get(mapping.get("target_category_id"))
        if mapping.get("status") == "mapped" and category:
            item.update({"result_status": "classified", "category_id": mapping.get("target_category_id"), **category})
        elif mapping.get("status") in {"review", "taxonomy_gap", "multi_role", "non_role_text"}:
            item["result_status"] = "pending"
        else:
            item["result_status"] = "failed"

    # Model batching enriches per-cohort copies with safe planner metadata;
    # persist those same resolved objects rather than the pre-decision list.
    candidate_items = [item for item, _, _ in resolved]
    counts = Counter(item["result_status"] for item in candidate_items)
    if isinstance(planner, DeepSeekDecisionPlanner):
        usage["planner_api_calls"] = planner.calls
        usage["planner_estimated_usd"] = planner.spent_usd
        usage["errors"].extend(planner.errors)
        usage["api_calls"] += planner.calls
        usage["estimated_usd"] += planner.spent_usd
    if shared_budget:
        usage["shared_budget_ledger"] = str(shared_budget.path)
        usage["conservative_committed_usd"] = shared_budget.committed
        usage["request_count"] = len(shared_budget.entries)
    batch = {
        "batch_id": batch_id, "source_file_name": args.source.name, "source_checksum": snapshot.source_checksum,
        "baseline_snapshot_id": baseline_id, "created_at": now(), "mapping_mode": args.mapping_mode,
        "status": "completed" if not counts["failed"] else "completed_with_failures",
        "counts": {
            "new_atomic_jobs": len(candidate_items), "involved_recruitment_records": len({item["source_record_id"] for item in candidate_items}),
            "duplicate_atomic_jobs_within_file": sum(max(0, len(item.get("source_record_ids_in_file", [])) - 1) for item in candidate_items),
            "classified": counts["classified"], "pending": counts["pending"], "failed": counts["failed"],
            "reused_classification": sum(item.get("agent_trace", [{}])[0].get("action") == "reuse" for item in candidate_items), "model_classification_requested": sum(any(step["action"] == "classify" for step in item.get("agent_trace", [])) for item in candidate_items),
            "agent_tool_calls": sum(len(item.get("agent_trace", [])) for item in candidate_items),
        },
    }
    repository.save_batch(batch, candidate_items)
    repository.save_run({"run_id": "RUN-" + batch_id, "batch_id": batch_id, "started_at": batch["created_at"],
                         "completed_at": now(), "mapping_mode": args.mapping_mode, "budget_usd": args.budget_usd,
                         "status": batch["status"], "usage": usage})
    display_catalogue(repository)
    batch_dir.mkdir(parents=True, exist_ok=True)
    (batch_dir / "batch_result.json").write_text(json.dumps({**batch, "items": candidate_items}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # CLI/API callers receive the persisted per-item agent trace; the browser
    # display catalogue remains the independently regenerated source of truth.
    print(json.dumps({**batch, "items": candidate_items, "usage": usage}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
