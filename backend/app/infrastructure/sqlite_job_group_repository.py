"""Versioned SQLite persistence for deterministic Job Groups."""
from __future__ import annotations
import json, sqlite3
from pathlib import Path
class SqliteJobGroupRepository:
 def __init__(self,path:str|Path): self.path=Path(path)
 def initialise(self):
  c=sqlite3.connect(self.path)
  try:
   with c: c.executescript('''CREATE TABLE IF NOT EXISTS job_group_runs (snapshot_id TEXT NOT NULL, grouping_version TEXT NOT NULL, created_at TEXT NOT NULL, summary_json TEXT NOT NULL, PRIMARY KEY(snapshot_id,grouping_version)); CREATE TABLE IF NOT EXISTS job_groups (job_group_id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL, grouping_version TEXT NOT NULL, payload_json TEXT NOT NULL); CREATE TABLE IF NOT EXISTS job_group_members (job_group_id TEXT NOT NULL, source_record_id TEXT NOT NULL, source_atomic_unit_id TEXT NOT NULL, payload_json TEXT NOT NULL, PRIMARY KEY(job_group_id,source_atomic_unit_id), FOREIGN KEY(job_group_id) REFERENCES job_groups(job_group_id)); CREATE INDEX IF NOT EXISTS idx_job_groups_run ON job_groups(snapshot_id,grouping_version);''')
  finally: c.close()
 def save(self,snapshot_id:str,version:str,summary:dict,groups:list[dict],members:list[dict]):
  self.initialise()
  c=sqlite3.connect(self.path)
  try:
   with c:
    if c.execute('SELECT 1 FROM job_group_runs WHERE snapshot_id=? AND grouping_version=?',(snapshot_id,version)).fetchone(): raise ValueError('Job-group run already exists; versioned results are immutable.')
    c.execute('INSERT INTO job_group_runs VALUES (?,?,?,?)',(snapshot_id,version,summary['generated_at'],json.dumps(summary,ensure_ascii=False)))
    c.executemany('INSERT INTO job_groups VALUES (?,?,?,?)',[(g['job_group_id'],snapshot_id,version,json.dumps(g,ensure_ascii=False)) for g in groups])
    c.executemany('INSERT INTO job_group_members VALUES (?,?,?,?)',[(m['job_group_id'],m['source_record_id'],m['source_atomic_unit_id'],json.dumps(m,ensure_ascii=False)) for m in members])
  finally: c.close()
