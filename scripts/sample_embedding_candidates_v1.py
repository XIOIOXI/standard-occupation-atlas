import json
from pathlib import Path
P=Path('data/processed/record_role_classification_v1/catalog_mappings/v4_embedding_candidates_bge_small_zh_v1.json');O=P.with_name('embedding_candidate_quality_samples_v1.json')
x=json.loads(P.read_text(encoding='utf-8'))
def band(r):
 s=r['candidates'][0]['similarity'];m=r['top1_top2_margin']
 return 'high_clear' if s>=.70 and m>=.08 else 'high_close' if s>=.70 else 'medium' if s>=.50 else 'low'
groups={}
for r in x['candidates']:
 b=band(r);l=r['candidates'][0]['level_1'];groups.setdefault((b,l),[]).append(r)
select=[]
for (b,l),v in groups.items():
 # deterministic diversity, 2 calibration + 1 validation per stratum/domain
 select.extend([{**r,'sample_role':'calibration'} for r in v[:2]])
 select.extend([{**r,'sample_role':'validation'} for r in v[2:3]])
with open(O,'x',encoding='utf-8') as f:json.dump({'schema_version':'embedding-quality-samples-v1','sampling':'stratified by similarity/margin band and top candidate level_1; first two calibration, third validation','sample_count':len(select),'samples':select},f,ensure_ascii=False,indent=2);f.write('\n')
