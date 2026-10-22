import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';

const root='data/processed/record_role_classification_v1/name_registry';
const rows=JSON.parse(readFileSync(`${root}/group_to_standard_occupation.json`)).rows
  .filter(x=>x.match_status!=='abnormal_not_displayable');
const decisions=existsSync(`${root}/pair_review/decisions.json`)
  ? JSON.parse(readFileSync(`${root}/pair_review/decisions.json`)).decisions : [];
const standardDecisions=existsSync(`${root}/pair_review/standard_decisions.json`)
  ? JSON.parse(readFileSync(`${root}/pair_review/standard_decisions.json`)).decisions : [];
const standardById=new Map();
for(const row of rows){
  if(!standardById.has(row.standard_occupation_id)) standardById.set(row.standard_occupation_id,{
    standard_occupation_id:row.standard_occupation_id,standard_name:row.standard_name,member_group_ids:[],original_names:[]
  });
  const item=standardById.get(row.standard_occupation_id);
  item.member_group_ids.push(row.record_role_group_id);item.original_names.push(row.original_name);
}
const groupToStandard=new Map(rows.map(x=>[x.record_role_group_id,x.standard_occupation_id]));
const decidedStandardPairs=new Set();
for(const x of decisions){
  const left=groupToStandard.get(x.left_group_id),right=groupToStandard.get(x.right_group_id);
  if(left&&right&&left!==right) decidedStandardPairs.add([left,right].sort().join('|'));
}
for(const x of standardDecisions){
  if(x.left_standard_occupation_id&&x.right_standard_occupation_id)
    decidedStandardPairs.add([x.left_standard_occupation_id,x.right_standard_occupation_id].sort().join('|'));
}
const generic=new Set(['工程师','专员','经理','助理','岗位','技术','管理','运营','产品','业务','开发','设计','服务','人员','应届毕业生','校招','社招','实习生','培训生']);
const pairs=new Map();let internalRawCandidatePairs=0;
for(const length of [5,4,3,2]){
  const index=new Map();
  for(const row of rows){const s=row.cleaned_name||'';for(let i=0;i<=s.length-length;i++){
    const fragment=s.slice(i,i+length);
    if(generic.has(fragment)||/[^\u4e00-\u9fa5A-Za-z]/.test(fragment))continue;
    if(!index.has(fragment))index.set(fragment,[]);index.get(fragment).push(row);
  }}
  for(const [fragment,items] of index){
    if(items.length<2||items.length>80)continue;
    for(let i=0;i<items.length;i++)for(let j=i+1;j<items.length;j++){
      const left=items[i].standard_occupation_id,right=items[j].standard_occupation_id;
      if(left===right){internalRawCandidatePairs++;continue;}
      const key=[left,right].sort().join('|');if(decidedStandardPairs.has(key))continue;
      if(!pairs.has(key)||pairs.get(key).shared_fragment.length<length)pairs.set(key,{left_standard_occupation_id:left,left_standard_name:items[i].standard_name,right_standard_occupation_id:right,right_standard_name:items[j].standard_name,shared_fragment:fragment,fragment_length:length});
    }
  }
}
const candidates=[...pairs.values()].map(x=>({...x,
  left_aliases:standardById.get(x.left_standard_occupation_id).original_names,
  right_aliases:standardById.get(x.right_standard_occupation_id).original_names
})).sort((a,b)=>b.fragment_length-a.fragment_length||a.shared_fragment.localeCompare(b.shared_fragment));
mkdirSync(`${root}/pair_review`,{recursive:true});
writeFileSync(`${root}/pair_review/standard_occupation_candidates.json`,JSON.stringify({
  schema_version:'standard-occupation-candidates-v1',candidate_unit:'current standard occupation pair',candidate_count:candidates.length,
  standard_occupation_count:standardById.size,skipped_internal_raw_name_pair_count:internalRawCandidatePairs,
  skipped_previously_decided_standard_pair_count:decidedStandardPairs.size,candidates
},null,2)+'\n');
