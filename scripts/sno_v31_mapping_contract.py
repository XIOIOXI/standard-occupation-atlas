"""Offline structural contract for future SNO v3.1 API outputs."""
def validate(row, levels, retired):
 required={'sample_id','status','target_category_id','candidate_category_ids','target_level','reason','level_3_evidence'}
 if set(row)!=required: raise ValueError('field set')
 s,t,c=row['status'],row['target_category_id'],row['candidate_category_ids']
 if len(c)!=len(set(c)) or any(x not in levels or x in retired for x in c): raise ValueError('candidate ids')
 if t in retired or (t is not None and t not in levels): raise ValueError('target id')
 if s=='mapped':
  if t is None or row['target_level']!=levels[t]: raise ValueError('mapped target level')
  if row['level_3_evidence'] is None and levels[t]=='level_3': raise ValueError('missing L3 evidence')
  if row['level_3_evidence'] is not None and levels[t]!='level_3': raise ValueError('unexpected L3 evidence')
 elif s=='review':
  if t is not None and t in c: raise ValueError('review target cannot be uncertain candidate')
  if row['target_level'] != (levels[t] if t else None): raise ValueError('review level')
  if row['level_3_evidence'] is not None: raise ValueError('review L3 evidence')
 elif s in {'taxonomy_gap','multi_role','non_role_text'}:
  if t is not None or row['target_level'] is not None or row['level_3_evidence'] is not None: raise ValueError('nonmapped fields')
 else: raise ValueError('status')
 return True
