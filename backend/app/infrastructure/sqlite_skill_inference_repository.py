"""SQLite schema for immutable, cacheable Skill Inference runs."""
from __future__ import annotations
import sqlite3
from pathlib import Path

class SqliteSkillInferenceRepository:
 def __init__(self,path:str|Path): self.path=Path(path)
 def initialise(self):
  c=sqlite3.connect(self.path)
  try:
   with c:
    c.executescript("""CREATE TABLE IF NOT EXISTS skill_inference_runs (run_id TEXT PRIMARY KEY, job_group_id TEXT NOT NULL, grouping_version TEXT NOT NULL, inference_version TEXT NOT NULL, input_fingerprint TEXT NOT NULL, prompt_version TEXT NOT NULL, model TEXT, context_selection_version TEXT NOT NULL, skill_normalization_version TEXT NOT NULL, inference_status TEXT NOT NULL, created_at TEXT NOT NULL, completed_at TEXT, UNIQUE(job_group_id,grouping_version,inference_version,input_fingerprint)); CREATE TABLE IF NOT EXISTS inferred_skills (inferred_skill_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, raw_skill_name TEXT NOT NULL, normalized_skill_name TEXT NOT NULL, skill_type TEXT NOT NULL, confidence TEXT NOT NULL, source_type TEXT NOT NULL, evidence_level TEXT NOT NULL, reasoning_summary TEXT NOT NULL, skill_scope TEXT NOT NULL DEFAULT 'occupation_core', FOREIGN KEY(run_id) REFERENCES skill_inference_runs(run_id)); CREATE TABLE IF NOT EXISTS skill_inference_diagnostics (diagnostic_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, job_group_id TEXT NOT NULL, inference_version TEXT NOT NULL, error_category TEXT NOT NULL, diagnostic_json TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(run_id) REFERENCES skill_inference_runs(run_id)); CREATE INDEX IF NOT EXISTS idx_skill_run_cache ON skill_inference_runs(job_group_id,grouping_version,inference_version,input_fingerprint);""")
   if 'grouping_version' not in {x[1] for x in c.execute('PRAGMA table_info(skill_inference_runs)')}:
    with c: c.execute("ALTER TABLE skill_inference_runs ADD COLUMN grouping_version TEXT NOT NULL DEFAULT 'job-grouping-v1'")
   run_cols={x[1] for x in c.execute('PRAGMA table_info(skill_inference_runs)')}
   for name, typ in [('input_tokens','INTEGER'),('output_tokens','INTEGER'),('total_tokens','INTEGER'),('estimated_cost','REAL')]:
    if name not in run_cols:
     with c: c.execute(f'ALTER TABLE skill_inference_runs ADD COLUMN {name} {typ}')
   if 'skill_scope' not in {x[1] for x in c.execute('PRAGMA table_info(inferred_skills)')}: 
    with c: c.execute("ALTER TABLE inferred_skills ADD COLUMN skill_scope TEXT NOT NULL DEFAULT 'occupation_core'")
   diag_cols={x[1] for x in c.execute('PRAGMA table_info(skill_inference_diagnostics)')}
   for name, typ in [('model','TEXT'),('exception_type','TEXT'),('http_status','INTEGER'),('openai_error_code','TEXT'),('request_stage','TEXT'),('validation_stage','TEXT'),('response_received','INTEGER'),('retryable','INTEGER'),('sanitized_message','TEXT')]:
    if name not in diag_cols:
     with c: c.execute(f'ALTER TABLE skill_inference_diagnostics ADD COLUMN {name} {typ}')
  finally: c.close()
