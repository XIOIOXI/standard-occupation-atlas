import { readFileSync, writeFileSync } from 'node:fs';
import { resolve, join } from 'node:path';

const root = resolve(process.cwd(), 'data/processed/job_market_intelligence/market_map');
const hierarchy = JSON.parse(readFileSync(join(root, 'industry_market_hierarchy.json'), 'utf8'));
const detailCache = new Map();
const MERGES = [{
  display_industry_id: 'display:information-and-electronics',
  label: '信息技术、电子信息与通信产业',
  member_labels: ['信息技术与数字产业', '电子信息与通信产业'],
}];

function detailFor(occupation) {
  if (!detailCache.has(occupation.detail_file)) detailCache.set(occupation.detail_file, JSON.parse(readFileSync(join(root, occupation.detail_file), 'utf8')));
  return detailCache.get(occupation.detail_file).occupations[occupation.node_id];
}
function recordIds(occupation, labels) {
  const detail = detailFor(occupation);
  const groupIds = new Set(detail.contexts.filter(context => labels.includes(context.industry_domain_label)).flatMap(context => context.source_job_group_ids));
  return detail.recruitment_evidence.filter(record => record.job_group_ids.some(id => groupIds.has(id))).map(record => record.source_record_id);
}

const mergedMemberLabels = new Set(MERGES.flatMap(merge => merge.member_labels));
const display_industries = hierarchy.industries
  .filter(industry => !mergedMemberLabels.has(industry.label))
  .map(industry => ({ ...industry, source_industry_labels: [industry.label] }));

for (const merge of MERGES) {
  const members = hierarchy.industries.filter(industry => merge.member_labels.includes(industry.label));
  const occupations = new Map();
  const records = new Set();
  for (const member of members) for (const occupation of member.occupations) {
    const ids = recordIds(occupation, [member.label]);
    ids.forEach(id => records.add(id));
    const current = occupations.get(occupation.node_id);
    if (current) {
      current.recruitment_evidence_count = new Set([...current.source_record_ids, ...ids]).size;
      ids.forEach(id => current.source_record_ids.add(id));
      current.source_industry_labels.push(member.label);
    } else occupations.set(occupation.node_id, {
      ...occupation,
      recruitment_evidence_count: ids.length,
      source_record_ids: new Set(ids),
      source_industry_labels: [member.label],
    });
  }
  const mergedOccupations = [...occupations.values()].map(({ source_record_ids, ...occupation }) => occupation);
  display_industries.push({
    node_id: merge.display_industry_id,
    label: merge.label,
    recruitment_evidence_count: records.size,
    occupations: mergedOccupations,
    source_industry_labels: merge.member_labels,
    member_industry_ids: members.map(member => member.node_id),
    display_relation: 'merged_overlapping_industries',
  });
}

display_industries.sort((a, b) => b.recruitment_evidence_count - a.recruitment_evidence_count || a.label.localeCompare(b.label, 'zh-Hans-CN'));
writeFileSync(join(root, 'display_industries.json'), `${JSON.stringify({
  schema_version: 'display-industries-v1',
  demand_metric: 'distinct_recruitment_record_count',
  merges: MERGES,
  display_industries,
}, null, 2)}\n`);
console.log(`Wrote ${join(root, 'display_industries.json')}`);
