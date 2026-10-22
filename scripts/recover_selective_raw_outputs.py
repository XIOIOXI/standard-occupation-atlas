"""Offline recovery of a response saved before a legacy SQLite conflict; never calls API."""
from __future__ import annotations
import json, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path
from run_skill_inference_v2_pilot import GROUPING_VERSION, INFERENCE_VERSION, PROMPT_VERSION, CONTEXT_SELECTION_VERSION, SKILL_NORMALIZATION_VERSION, MODEL, execution_fingerprint, parse_and_validate_response

ROOT=Path('data/processed/skill_inference_v2/selective_mini_1000'); DB=Path('data/processed/recruitment_snapshots.sqlite')
def main():
 inputs={x['job_group_id']:x for x in (json.loads(s) for s in (ROOT/'selected_inputs.jsonl').read_text(encoding='utf-8').splitlines() if s)}
 raw=[json.loads(s) for s in (ROOT/'raw_model_outputs.jsonl').read_text(encoding='utf-8').splitlines() if s]
 db=sqlite3.connect(DB); recovered=[]
 try:
  for item in raw:
   row=inputs.get(item['job_group_id']);
   if not row: continue
   fp=execution_fingerprint(row['input_fingerprint'],MODEL)
   if db.execute('SELECT 1 FROM skill_inference_runs WHERE job_group_id=? AND grouping_version=? AND inference_version=? AND input_fingerprint=?',(item['job_group_id'],GROUPING_VERSION,INFERENCE_VERSION,fp)).fetchone(): continue
   _,status,hard,soft=parse_and_validate_response({'output_text':json.dumps(item['output'],ensure_ascii=False)})
   run_id=str(uuid.uuid4());now=datetime.now(timezone.utc).isoformat()
   with db:
    db.execute('INSERT INTO skill_inference_runs (run_id,job_group_id,grouping_version,inference_version,input_fingerprint,prompt_version,model,context_selection_version,skill_normalization_version,inference_status,created_at,completed_at,input_tokens,output_tokens,total_tokens,estimated_cost) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(run_id,item['job_group_id'],GROUPING_VERSION,INFERENCE_VERSION,fp,PROMPT_VERSION,MODEL,CONTEXT_SELECTION_VERSION,SKILL_NORMALIZATION_VERSION,status,now,now,None,None,None,None))
    db.executemany('INSERT INTO inferred_skills (inferred_skill_id,run_id,raw_skill_name,normalized_skill_name,skill_type,confidence,source_type,evidence_level,reasoning_summary,skill_scope) VALUES (?,?,?,?,?,?,?,?,?,?)',[(str(uuid.uuid4()),run_id,s['raw_skill_name'],s['normalized_skill_name'],s['skill_type'],s['confidence'],s['source_type'],s['evidence_level'],s['reasoning_summary'],s['skill_scope']) for s in hard+soft])
   recovered.append(item['job_group_id'])
 finally: db.close()
 print(json.dumps({'api_calls':0,'recovered_runs':recovered},ensure_ascii=False))
if __name__=='__main__': main()
