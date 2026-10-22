import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';

const root = 'data/processed/record_role_classification_v1';
const roles = JSON.parse(readFileSync(`${root}/record_roles.json`, 'utf8')).roles;
const normalize = value => String(value || '').normalize('NFKC').toLowerCase()
  .replace(/[\s　]+/g, '').replace(/[，,;；、|/\\]+/g, '|').replace(/[()（）【】\[\]]/g, '');
const aliases = new Map([['客户经理岗','客户经理'],['客户经理岗位','客户经理'],['管培生','管理培训生'],['管理培训岗','管理培训生'],['管理培训生岗','管理培训生']]);
const normalizeTitle = value => {
  let title = String(value || '').normalize('NFKC').trim()
    // Remove only explicitly non-duty parenthetical annotations.  Direction,
    // domain and technology qualifiers remain part of occupational identity.
    .replace(/[（(](?:\d+人?|20\d{2}届(?:毕业生可报)?|实习|校招|社招|全国|[\u4e00-\u9fa5]{2,6}(?:市|省|区|县|办事处|分行))[）)]/g, '')
    .replace(/[\s　]+/g, '');
  // These describe recruitment/seniority state, not the occupational duty.
  title = title.replace(/(?:招聘|招募|校招|社招|实习生|实习|应届生|储备生)$/g, '');
  title = title.replace(/(?:岗位|职位|职务|岗)$/g, '');
  return aliases.get(title) || title;
};
const groups = new Map();
for (const role of roles) {
  // raw_job_title is the only available responsibility-bearing source text in
  // this artifact. Exact normalised context avoids merging same titles listed
  // in different role bundles.
  const titleKey = normalizeTitle(role.source_title);
  // Normalized profession name is the merge key.  Source bundles are retained
  // as separate evidence; direction-bearing title words are never removed.
  const key = titleKey;
  if (!groups.has(key)) groups.set(key, { key, canonical_title: titleKey, representative_title: role.source_title, representative_raw_job_title: role.raw_job_title, members: [], industries: new Set(), companies: new Set(), raw_titles: new Set(), raw_contexts: new Set() });
  const group = groups.get(key);
  group.members.push({ record_role_id: role.record_role_id, source_atomic_unit_id: role.source_atomic_unit_id, source_record_id: role.source_record_id });
  group.raw_titles.add(role.source_title); group.raw_contexts.add(role.raw_job_title);
  if (role.industry_category) group.industries.add(role.industry_category);
  if (role.company_name) group.companies.add(role.company_name);
}
const output = [...groups.values()].map(group => ({
  record_role_group_id: `RRG-${createHash('sha256').update(group.key).digest('hex').slice(0, 20)}`,
  canonical_title: group.canonical_title,
  representative_title: group.representative_title,
  representative_raw_job_title: group.representative_raw_job_title,
  member_count: group.members.length,
  member_record_role_ids: group.members.map(x => x.record_role_id),
  source_atomic_unit_ids: group.members.map(x => x.source_atomic_unit_id),
  source_record_ids: [...new Set(group.members.map(x => x.source_record_id))],
  industry_categories: [...group.industries].sort(), company_names: [...group.companies].sort(),
  original_titles: [...group.raw_titles].sort(), representative_source_contexts: [...group.raw_contexts].slice(0, 5), source_context_variant_count: group.raw_contexts.size,
  grouping_basis: 'conservative_canonical_title_with_aliases_and_preserved_source_contexts',
}));
const summary = { schema_version: 'record-role-groups-v2', source_role_count: roles.length, group_count: output.length, grouped_role_count: output.reduce((n, x) => n + x.member_count, 0), multi_member_group_count: output.filter(x => x.member_count > 1).length, grouping_policy: 'Canonical title aliases and non-duty suffix removal; assistant/supervisor/engineer and direction terms retained. Original contexts and industries are retained for conflict review.', generated_at: new Date().toISOString() };
mkdirSync(`${root}/groups`, { recursive: true });
writeFileSync(`${root}/groups/record_role_groups.json`, `${JSON.stringify({ summary, groups: output }, null, 2)}\n`);
writeFileSync(`${root}/groups/summary.json`, `${JSON.stringify(summary, null, 2)}\n`);
writeFileSync(`${root}/groups/merge_samples.json`, `${JSON.stringify(output.filter(x => x.member_count > 1).sort((a,b) => b.member_count-a.member_count).slice(0, 20), null, 2)}\n`);
