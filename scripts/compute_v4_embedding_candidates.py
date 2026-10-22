import json, hashlib, numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
ROOT=Path('data/processed/record_role_classification_v1'); NR=ROOT/'name_registry'; CM=ROOT/'catalog_mappings'
SRC=NR/'standard_occupation_to_original_names_final_deterministic_v4.json'; TAX=CM/'taxonomy_embedding_texts_v1.json'; OUT=CM/'v4_embedding_candidates_bge_small_zh_v1.json'; CACHE=CM/'embedding_cache_bge_small_zh_v1.npz'
MODEL='BAAI/bge-small-zh-v1.5'
def main():
 src=json.loads(SRC.read_text(encoding='utf-8'));tax=json.loads(TAX.read_text(encoding='utf-8'))
 names=[x['standard_name'] for x in src['occupations']]; texts=[x['matching_text'] for x in tax['rows']]
 model=SentenceTransformer(MODEL, local_files_only=True); a=model.encode(names,normalize_embeddings=True,show_progress_bar=True,batch_size=1024); b=model.encode(texts,normalize_embeddings=True,show_progress_bar=True,batch_size=1024)
 sim=a@b.T; idx=np.argpartition(-sim,3,axis=1)[:,:3];idx=np.take_along_axis(idx,np.argsort(-np.take_along_axis(sim,idx,axis=1),axis=1),axis=1)
 rows=[]
 for i,o in enumerate(src['occupations']):
  cs=[{'category_id':tax['rows'][j]['category_id'],'level_1':tax['rows'][j]['level_1'],'level_2':tax['rows'][j]['level_2'],'level_3':tax['rows'][j]['level_3'],'similarity':float(sim[i,j])} for j in idx[i]]
  rows.append({'standard_occupation_id':o['standard_occupation_id'],'standard_name':o['standard_name'],'candidates':cs,'top1_top2_margin':cs[0]['similarity']-cs[1]['similarity']})
 np.savez_compressed(CACHE,occupation_embeddings=a,category_embeddings=b)
 out={'schema_version':'v4-local-embedding-candidates-v1','model':MODEL,'input_version':hashlib.sha256((SRC.read_text(encoding='utf-8')+TAX.read_text(encoding='utf-8')).encode()).hexdigest(),'occupation_count':len(rows),'category_count':len(texts),'top_k':3,'candidates':rows}
 with open(OUT,'x',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,indent=2);f.write('\n')
if __name__=='__main__':main()
