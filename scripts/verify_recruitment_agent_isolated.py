"""Explicit synthetic, isolated, budget-limited recruitment update check."""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "scripts")]
from app.domain.recruitment.csv_import import create_snapshot
from app.infrastructure.sqlite_snapshot_repository import SqliteSnapshotRepository
from build_daily_jobs_calendar import update_items

HEADERS = ["更新时间", "公司", "企业类型", "招聘届次", "批次（暑期实习）", "行业类别", "工作地点", "招聘岗位", "截止时间", "简历投递链接", "公告链接", "学历要求", "专业要求"]


def write_rows(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(HEADERS)
        writer.writerows(rows)


def main():
    output = ROOT / "outputs" / ("recruitment-agent-isolated-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    output.mkdir(parents=True, exist_ok=False)
    baseline = ["2026/10/18", "测试基准公司", "民营", "2027届", "秋招", "互联网", "上海", "测试工程师", "", "", "", "本科", "计算机"]
    rows = [baseline,
        ["2026/10/19", "测试甲公司", "民营", "2027届", "秋招", "互联网", "上海", "量子算法工程师", "", "", "", "本科", "计算机"],
        ["2026/10/19", "测试乙公司", "民营", "2027届", "秋招", "互联网", "北京", "前端工程师、后端工程师", "", "", "", "本科", "计算机"],
        ["2026/10/19", "测试丙公司", "民营", "2027届", "秋招", "互联网", "深圳", "产品经理", "", "", "", "本科", "计算机"]]
    write_rows(output / "baseline.csv", [baseline])
    write_rows(output / "update.csv", rows)
    SqliteSnapshotRepository(output / "baseline.sqlite").save(create_snapshot(output / "baseline.csv"))
    # Reserve headroom for the earlier uncertain request and first live run.
    command = [sys.executable, str(ROOT / "scripts/process_recruitment_update.py"), str(output / "update.csv"), "--sandbox-dir", str(output), "--mapping-mode", "model", "--budget-usd", "0.17"]
    env = os.environ.copy(); env["PYTHONIOENCODING"] = "utf-8"
    first = subprocess.run(command, cwd=ROOT, env=env, text=True, encoding="utf-8", capture_output=True)
    (output / "first.stdout.txt").write_text(first.stdout, encoding="utf-8")
    (output / "first.stderr.txt").write_text(first.stderr, encoding="utf-8")
    if first.returncode:
        raise RuntimeError(f"isolated process failed ({first.returncode}); see {output / 'first.stderr.txt'}")
    second = subprocess.run(command, cwd=ROOT, env=env, text=True, encoding="utf-8", capture_output=True)
    (output / "repeat.stdout.txt").write_text(second.stdout, encoding="utf-8")
    (output / "repeat.stderr.txt").write_text(second.stderr, encoding="utf-8")
    batches = json.loads((output / "display/update_batches.json").read_text(encoding="utf-8"))
    daily = update_items(batches)
    (output / "display/daily_jobs_v1.json").write_text(json.dumps({"items": daily}, ensure_ascii=False, indent=2), encoding="utf-8")
    ledgers = list((output / "runs").glob("*/shared_budget.json"))
    ledger = json.loads(ledgers[0].read_text(encoding="utf-8")) if ledgers else {}
    summary = {"isolated_dir": str(output), "repeat_returncode": second.returncode, "repeat_output": second.stdout.strip(), "batch_count": len(batches.get("batches", [])), "counts": batches.get("batches", [{}])[0].get("counts", {}), "items": [{"title": item.get("title_unit"), "status": item.get("result_status"), "category": [item.get("level_1"), item.get("level_2"), item.get("level_3")], "trace": [{"action": step["action"], "outcome": step["result"].get("outcome"), "reason": step.get("reason")} for step in item.get("agent_trace", [])]} for batch in batches.get("batches", []) for item in batch.get("items", [])], "daily_items": len(daily), "budget": {key: ledger.get(key) for key in ("limit_usd", "committed_usd", "uncertain")}, "requests": [{key: entry.get(key) for key in ("stage", "status", "usage", "estimated_usd_peak", "error_type")} for entry in ledger.get("requests", [])]}
    (output / "verification_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
