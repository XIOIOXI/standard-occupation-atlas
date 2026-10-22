"""Create one immutable independent 100-name holdout for SNO v3 validation."""
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data/processed/record_role_classification_v1/name_registry/standard_occupation_to_original_names_final_deterministic_v4.json"
FIXED = ROOT / "data/processed/record_role_classification_v1/api_trials/deepseek_name_classification_trial_v3/selection_manifest.json"
OUT = ROOT / "data/processed/record_role_classification_v1/api_trials/deepseek_sno_v3_directory_trial_100_v2_independent_selection.json"
SEED = 20261013

def main():
    if OUT.exists(): raise FileExistsError(OUT)
    fixed = {x["standard_occupation_id"] for x in json.loads(FIXED.read_text(encoding="utf-8"))["occupations"]}
    pool = [x for x in json.loads(REGISTRY.read_text(encoding="utf-8"))["occupations"] if x["standard_occupation_id"] not in fixed]
    rng = random.Random(SEED); chosen = rng.sample(pool, 100)
    payload = {"schema_version":"sno-v3-independent-holdout-v1","random_seed":SEED,"selection_method":"uniform random sample without replacement from v4 standard occupation registry, excluding the fixed 100-name prompt-tuning holdout","source_count":len(pool),"excluded_fixed_count":len(fixed),"occupations":[{"standard_occupation_id":x["standard_occupation_id"],"standard_name":x["standard_name"],"selection_strata":"independent_uniform"} for x in chosen]}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(OUT)
if __name__ == "__main__": main()
