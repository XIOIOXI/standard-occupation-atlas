import json,random
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; R=ROOT/'data/processed/record_role_classification_v1/name_registry/standard_occupation_to_original_names_final_deterministic_v4.json'; O=ROOT/'data/processed/record_role_classification_v1/api_trials/sno_v31_200_selection.json'; seed=2026101302
def main():
 if O.exists():raise FileExistsError(O)
 excluded=set()
 for p in [ROOT/'data/processed/record_role_classification_v1/api_trials/deepseek_sno_v3_directory_trial_100_v2_fixed/selection_manifest.json',ROOT/'data/processed/record_role_classification_v1/api_trials/deepseek_sno_v3_directory_trial_100_v2_independent/selection_manifest.json']:
  excluded|={x['occupation_id'] for x in json.loads(p.read_text(encoding='utf8'))['occupations']}
 pool=[x for x in json.loads(R.read_text(encoding='utf8'))['occupations'] if x['standard_occupation_id'] not in excluded]; chosen=random.Random(seed).sample(pool,200)
 O.write_text(json.dumps({'schema_version':'sno-v3.1-200-title-holdout-v1','random_seed':seed,'source':'v4 standard occupation registry / actual pending title corpus','deduplication_scope':'title-level trial only; not a future record-level mapping rule','source_count':len(pool),'excluded_prior_sample_count':len(excluded),'occupations':[{'standard_occupation_id':x['standard_occupation_id'],'standard_name':x['standard_name'],'selection_strata':'uniform_random'} for x in chosen]},ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(O)
if __name__=='__main__':main()
