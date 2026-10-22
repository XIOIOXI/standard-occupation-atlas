import { readFileSync, writeFileSync } from 'node:fs';
const root='data/processed/record_role_classification_v1/name_registry';
const artifact=JSON.parse(readFileSync(`${root}/group_to_standard_occupation.json`));
// Explicit name-only judgments.  Titles with rank/assistant distinctions are
// intentionally excluded unless the wording remains an exact duty synonym.
const approvals=new Map([
 ['客户经理岗','客户经理'],['客户经理岗位','客户经理'],
 ['会计岗','会计'],['软件开发','软件开发工程师'],
 ['Java开发','Java开发工程师'],['Java工程师','Java开发工程师'],
 ['Web前端开发','前端开发工程师'],['前端开发','前端开发工程师'],
 ['软件测试工程师','测试工程师'],['招聘专员岗','人才招聘专员'],
]);
const reviewed=[];for(const row of artifact.rows){if(!approvals.has(row.cleaned_name))continue;row.standard_name=approvals.get(row.cleaned_name);row.match_status='reviewed_merged_explicit_name_synonym';reviewed.push({record_role_group_id:row.record_role_group_id,original_name:row.original_name,standard_name:row.standard_name,decision:'merged_explicit_name_synonym'});}
writeFileSync(`${root}/name_review_batch_001.json`,JSON.stringify({reviewed_at:new Date().toISOString(),reviewed},null,2)+'\n');
writeFileSync(`${root}/group_to_standard_occupation.json`,JSON.stringify(artifact,null,2)+'\n');
