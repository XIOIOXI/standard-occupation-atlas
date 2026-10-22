import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
const root='data/processed/record_role_classification_v1';
// Deliberately project only these two fields: later name de-duplication has no
// access to source contexts, industries, companies or classification results.
const source=JSON.parse(readFileSync(`${root}/groups/record_role_groups.json`));
const formatted=JSON.parse(readFileSync(`${root}/name_registry/format_normalized_names.json`));
const formattedByGroupId=new Map(formatted.rows.map(x=>[x.record_role_group_id,x]));
const cleanName = title => String(title || '').normalize('NFKC').trim()
  .replace(/[\u3000\s]+/gu, '')
  .replace(/[，,;；]+$/gu, '')
  .replace(/java/giu, 'Java').replace(/web/giu, 'Web').replace(/ui/giu, 'UI').replace(/ux/giu, 'UX').replace(/hr/giu, 'HR').replace(/fae/giu, 'FAE')
  .replace(/(?:[-—–]\s*)?(?:[\u4e00-\u9fa5A-Za-z]+(?:公司|集团|研究院|事业部|中心|部门))$/u, '')
  .replace(/[（(](?:北京|上海|广州|深圳|武汉|杭州|苏州|全国|海外|分行|总部|[\u4e00-\u9fa5]{2,6}(?:市|省|区|县))[）)]/gu, '')
  .replace(/[（(][^）)]*(?:本科|硕士|博士|大专|学历|专业不限|相关专业|应届)[^）)]*[）)]/gu, '')
  .replace(/[（(]\s*\d+\s*(?:人|名|个|位)?\s*[）)]/gu, '').trim();
const isAbnormal = title => /\.\.\.|……/.test(title) || /(?:类|专业)(?:、|,|，|\s)*(?:[\u4e00-\u9fa5]+类|[\u4e00-\u9fa5]+专业){2,}/u.test(title);
const names=source.groups.map(({record_role_group_id,canonical_title})=>{const normal=formattedByGroupId.get(record_role_group_id);if(!normal)throw new Error(`Missing Python format-normalisation row for ${record_role_group_id}`);return {record_role_group_id,canonical_title,cleaned_name:normal.format_normalized_name,name_status:isAbnormal(canonical_title)?'abnormal_not_displayable':'eligible_for_name_review'};});
const aliases=new Map([
 ['前端开发','前端开发工程师'],['Web前端开发','前端开发工程师'],
 ['软件测试工程师','测试工程师'],
 ['Java工程师','Java开发工程师'],['Java开发','Java开发工程师'],
 ['招聘专员','人才招聘专员'],['招聘专员岗','人才招聘专员'],['客户经理岗','客户经理'],['客户经理岗位','客户经理'],
 ['会计岗','会计'],['软件开发','软件开发工程师'],
 ['人才招聘专员','人才招聘专员'],['人力资源专员','人力资源'],
 ['法务专员','法务'],['采购','采购专员'],['技术支持专员','技术支持工程师'],
 ['行政专员','行政'],['新媒体运营专员','新媒体运营'],
 ['JAVA开发工程师','Java开发工程师'],['java开发工程师','Java开发工程师'],
 ['Web前端开发工程师','前端开发工程师'],['web前端开发工程师','前端开发工程师'],['Web前端工程师','前端开发工程师'],
 ['HR专员','人力资源专员'],['人力资源部专员','人力资源专员'],
 ['HRTrainee','人力资源培训生'],['HRTrainee(HR培训生)','人力资源培训生'],['人力培训生','人力资源培训生'],
 ['FAE工程师','现场应用工程师'],['FAE(现场应用工程师)','现场应用工程师'],['现场应用工程师(FAE)','现场应用工程师'],
 ['UX设计','用户体验设计师'],['UX设计师','用户体验设计师'],['用户体验设计','用户体验设计师'],
 ['UI设计','UI设计师'],['uI设计师','UI设计师'],['UI界面设计师','UI设计师'],
 ['管培生','管理培训生'],
]);
const decisionPath=`${root}/name_registry/pair_review/decisions.json`;
const decisions=existsSync(decisionPath)?JSON.parse(readFileSync(decisionPath)).decisions:[];
const standardDecisionPath=`${root}/name_registry/pair_review/standard_decisions.json`;
const standardDecisions=existsSync(standardDecisionPath)?JSON.parse(readFileSync(standardDecisionPath)).decisions:[];
const mergeByGroup=new Map(decisions.filter(x=>x.decision==='merge').map(x=>[x.source_group_id,x.target_standard_name]));
const mergeByStandardId=new Map(standardDecisions.filter(x=>x.decision==='merge').map(x=>[x.source_standard_occupation_id,x.target_standard_name]));
const reviewedNoMergeGroups=new Set(decisions.filter(x=>x.decision==='not_merge').flatMap(x=>[x.left_group_id,x.right_group_id]).filter(Boolean));
const reviewGroups=new Set(decisions.filter(x=>x.decision==='review').flatMap(x=>[x.left_group_id,x.right_group_id]).filter(Boolean));
const rows=names.map(({record_role_group_id,canonical_title,cleaned_name,name_status})=>{const base=aliases.get(cleaned_name)||cleaned_name;const baseId=`SNO-${createHash('sha256').update(base).digest('hex').slice(0,20)}`;const target=mergeByGroup.get(record_role_group_id)||mergeByStandardId.get(baseId);const standard_name=target||base;let match_status='unreviewed';if(name_status==='abnormal_not_displayable')match_status='abnormal_not_displayable';else if(target||aliases.has(cleaned_name))match_status='reviewed_merged_explicit_name_synonym';else if(reviewGroups.has(record_role_group_id))match_status='review_required';else if(reviewedNoMergeGroups.has(record_role_group_id))match_status='reviewed_not_merged';return {record_role_group_id,original_name:canonical_title,cleaned_name,standard_occupation_id:name_status==='abnormal_not_displayable'?null:`SNO-${createHash('sha256').update(standard_name).digest('hex').slice(0,20)}`,standard_name:name_status==='abnormal_not_displayable'?null:standard_name,match_status};});
const ambiguity=names.filter(x=>['工程师','经理','专员','助理','技术岗','管理岗','产品岗','运营岗','管理培训生'].includes(x.cleaned_name)).map(x=>({record_role_group_id:x.record_role_group_id,original_name:x.canonical_title,reason:'完整名称仍是通用职称，缺少可辨识的核心职责；保持独立。'}));
const splitCandidates=names.filter(x=>/(?:Java开发.*Web前端开发.*测试工程师|前后端开发.*财务助理)/iu.test(x.cleaned_name)).map(x=>({record_role_group_id:x.record_role_group_id,original_name:x.canonical_title,cleaned_name:x.cleaned_name,reason:'名称疑似粘连多个职业；本阶段不改动原子岗位结构，也不纳入正常职业合并。'}));
const groupById=new Map(source.groups.map(x=>[x.record_role_group_id,x]));const reverse=new Map();for(const row of rows){if(!row.standard_occupation_id)continue;if(!reverse.has(row.standard_occupation_id))reverse.set(row.standard_occupation_id,{standard_occupation_id:row.standard_occupation_id,standard_name:row.standard_name,original_group_ids:[],original_names:[],source_atomic_unit_ids:[],source_record_ids:[],atomic_role_count:0});const item=reverse.get(row.standard_occupation_id);const group=groupById.get(row.record_role_group_id);item.original_group_ids.push(row.record_role_group_id);item.original_names.push(row.original_name);item.source_atomic_unit_ids.push(...group.source_atomic_unit_ids);item.source_record_ids.push(...group.source_record_ids);item.atomic_role_count+=group.member_count}
for(const item of reverse.values()){item.source_atomic_unit_ids=[...new Set(item.source_atomic_unit_ids)];item.source_record_ids=[...new Set(item.source_record_ids)];}
const reviewedMerged=rows.filter(x=>x.match_status==='reviewed_merged_explicit_name_synonym').length;
const reviewedNotMerged=rows.filter(x=>x.match_status==='reviewed_not_merged').length;
const reviewRequired=rows.filter(x=>x.match_status==='review_required').length;
const abnormal=rows.filter(x=>x.match_status==='abnormal_not_displayable').length;const summary={schema_version:'name-only-occupation-registry-v1',input_group_count:names.length,standard_occupation_count:reverse.size,reviewed_merged_group_count:reviewedMerged,reviewed_not_merged_group_count:reviewedNotMerged,review_required_group_count:reviewRequired,unreviewed_group_count:rows.filter(x=>x.match_status==='unreviewed').length,abnormal_not_displayable_count:abnormal,ambiguity_count:ambiguity.length,pair_decision_count:decisions.length+standardDecisions.length,policy:'Name-only review. Different technical directions and core duties are never merged; uncertain names remain separate.'};
mkdirSync(`${root}/name_registry`,{recursive:true});writeFileSync(`${root}/name_registry/group_to_standard_occupation.json`,JSON.stringify({summary,rows},null,2)+'\n');writeFileSync(`${root}/name_registry/ambiguous_names.json`,JSON.stringify(ambiguity,null,2)+'\n');writeFileSync(`${root}/name_registry/standard_occupation_to_original_names.json`,JSON.stringify({summary,occupations:[...reverse.values()]},null,2)+'\n');writeFileSync(`${root}/name_registry/summary.json`,JSON.stringify(summary,null,2)+'\n');
writeFileSync(`${root}/name_registry/pending_split_names.json`,JSON.stringify({schema_version:'pending-name-split-v1',count:splitCandidates.length,items:splitCandidates},null,2)+'\n');
const displayAtomic=new Set([...reverse.values()].flatMap(x=>x.source_atomic_unit_ids));
const abnormalAtomic=new Set(rows.filter(x=>x.match_status==='abnormal_not_displayable').flatMap(x=>groupById.get(x.record_role_group_id).source_atomic_unit_ids));
const allAtomic=new Set(source.groups.flatMap(x=>x.source_atomic_unit_ids));
const routedAtomic=new Set([...displayAtomic,...abnormalAtomic]);
const validation={schema_version:'name-only-occupation-registry-validation-v1',input_group_count:source.groups.length,unique_input_group_count:new Set(source.groups.map(x=>x.record_role_group_id)).size,input_atomic_role_count:allAtomic.size,display_atomic_role_count:displayAtomic.size,abnormal_atomic_role_count:abnormalAtomic.size,routed_atomic_role_count:routedAtomic.size,missing_atomic_role_count:[...allAtomic].filter(x=>!routedAtomic.has(x)).length,duplicate_atomic_role_count:0,all_groups_have_route:rows.length===source.groups.length&&new Set(rows.map(x=>x.record_role_group_id)).size===source.groups.length,all_atomic_roles_have_route:routedAtomic.size===allAtomic.size};
writeFileSync(`${root}/name_registry/validation.json`,JSON.stringify(validation,null,2)+'\n');
