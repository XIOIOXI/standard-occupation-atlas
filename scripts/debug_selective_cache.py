import json, sqlite3
from pathlib import Path
from run_skill_inference_v2_pilot import execution_fingerprint, MODEL, INFERENCE_VERSION
r=Path('data/processed/skill_inference_v2/selective_mini_1000')
x=json.loads(r.joinpath('raw_model_outputs.jsonl').read_text(encoding='utf-8').splitlines()[-1]); inp={q['job_group_id']:q for q in map(json.loads,r.joinpath('selected_inputs.jsonl').read_text(encoding='utf-8').splitlines())}; fp=execution_fingerprint(inp[x['job_group_id']]['input_fingerprint'],MODEL); db=sqlite3.connect('data/processed/recruitment_snapshots.sqlite')
print(x['job_group_id'],fp,db.execute('select run_id,grouping_version,inference_version,input_fingerprint,model from skill_inference_runs where job_group_id=?',(x['job_group_id'],)).fetchall(),db.execute('select run_id from skill_inference_runs where job_group_id=? and inference_version=? and input_fingerprint=?',(x['job_group_id'],INFERENCE_VERSION,fp)).fetchall())
