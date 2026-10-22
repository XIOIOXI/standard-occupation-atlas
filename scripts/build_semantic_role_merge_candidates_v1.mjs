import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
const root='data/processed/record_role_classification_v1';
const groups=JSON.parse(readFileSync(`${root}/groups/record_role_groups.json`)).groups;
// Explicit semantic families reviewed as the same core occupation.  These
// are not taxonomy categories and never merge different technical duties.
const aliases={
  '前端开发':'前端开发工程师','Web前端开发':'前端开发工程师','Web开发工程师':'前端开发工程师',
  'Java工程师':'Java开发工程师','Java开发':'Java开发工程师',
  'Python工程师':'Python开发工程师','Python开发':'Python开发工程师',
  '软件测试工程师':'测试工程师','QA工程师':'测试工程师',
  '采购工程师':'采购专员','采购员':'采购专员',
  '财务会计':'会计','会计师':'会计',
  '电气自动化工程师':'电气工程师','自动化工程师':'电气工程师',
  '机械设计师':'机械设计工程师','结构设计工程师':'结构工程师',
  '新媒体运营专员':'新媒体运营','新媒体运营岗':'新媒体运营',
};
const byFamily=new Map();
for(const group of groups){const family=aliases[group.canonical_title];if(!family)continue;if(!byFamily.has(family))byFamily.set(family,[]);byFamily.get(family).push(group);}
const candidates=[...byFamily].filter(([,members])=>members.length>1).map(([canonical_occupation_title,members])=>({canonical_occupation_title,candidate_status:'approved_same_core_responsibility',reason:'Manually reviewed title variants denote the same stated core duty; source contexts remain linked for later member-difference review.',member_group_ids:members.map(x=>x.record_role_group_id),member_titles:members.map(x=>x.canonical_title),member_group_count:members.length,atomic_role_count:members.reduce((n,x)=>n+x.member_count,0),source_record_count:new Set(members.flatMap(x=>x.source_record_ids)).size}));
const mergedGroupCount=groups.length-candidates.reduce((n,x)=>n+x.member_group_count-1,0);
const summary={schema_version:'semantic-role-merge-candidates-v1',input_normalized_group_count:groups.length,approved_semantic_merge_family_count:candidates.length,merged_group_count_after_approved_merges:mergedGroupCount,policy:'Only explicit reviewed same-duty title variants are merged. Category membership, company, location, pay, seniority and recruiting status are never merge reasons.'};
mkdirSync(`${root}/semantic_merges`,{recursive:true});writeFileSync(`${root}/semantic_merges/candidates.json`,JSON.stringify({summary,candidates},null,2)+'\n');writeFileSync(`${root}/semantic_merges/summary.json`,JSON.stringify(summary,null,2)+'\n');
