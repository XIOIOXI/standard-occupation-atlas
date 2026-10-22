import { readFileSync, writeFileSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { DEFAULT_RULES, SUBCATEGORY_RULES, TITLE_SUFFIX_RULE } from './display_category_taxonomy.mjs';
import { buildRoleSubcategories } from './display_role_subcategory_taxonomy.mjs';

const root = resolve(process.cwd(), 'data/processed/job_market_intelligence/market_map');
const inputFile = process.argv[2] || 'display_industries.json';
const outputFile = process.argv[3] || 'display_occupation_groups.json';
const displayIndustries = JSON.parse(readFileSync(join(root, inputFile), 'utf8'));
const detailCache = new Map();

function rulesFor(label) {
  // A user-specified category is a closed directory: do not append automatic
  // suffix groups such as “客户经理岗”, which would violate the supplied
  // second-level taxonomy. Generic display categories still use the fallback.
  if (SUBCATEGORY_RULES[label]) return SUBCATEGORY_RULES[label];
  return [...DEFAULT_RULES, TITLE_SUFFIX_RULE];
}

// These are prose fragments produced when a source announcement refers readers
// to an attachment instead of naming an actual role. Records stay retained;
// only the invalid extracted "occupation" is excluded from the UI layer.
const NON_OCCUPATION_LABELS = [
  /^(?:具体|官方未说明|未说明|应届生)?招聘岗位$/u,
  /^本次计划招录员工\d+名。具体招聘岗位$/u,
];
const isNonOccupationLabel = label => NON_OCCUPATION_LABELS.some(pattern => pattern.test(label.replace(/\s+/g, '')));

function readDetail(file) {
  if (!detailCache.has(file)) detailCache.set(file, JSON.parse(readFileSync(join(root, file), 'utf8')));
  return detailCache.get(file);
}

function groupCandidates(occupations, rules, minimumMembers = 2) {
  const assigned = new Set();
  const groups = [];
  for (const rule of rules) {
    const buckets = new Map();
    for (const occupation of occupations) {
      if (assigned.has(occupation.node_id)) continue;
      const key = rule.match ? (rule.match(occupation.label) ? rule.id : null) : rule.key(occupation.label);
      if (!key || key.length < 2) continue;
      if (!buckets.has(key)) buckets.set(key, []);
      buckets.get(key).push(occupation);
    }
    for (const [key, members] of buckets) {
      if (members.length < minimumMembers) continue;
      const label = rule.label || key;
      groups.push({ rule_id: rule.id, relation: rule.relation, label, members });
      members.forEach(member => assigned.add(member.node_id));
    }
  }
  return groups;
}

function evidenceIds(industryLabels, occupation) {
  const detail = readDetail(occupation.detail_file).occupations[occupation.node_id];
  if (!detail) return [];
  const jobGroupIds = new Set(detail.contexts
    .filter(context => industryLabels.includes(context.industry_domain_label))
    .flatMap(context => context.source_job_group_ids || []));
  return detail.recruitment_evidence
    .filter(record => record.job_group_ids?.some(id => jobGroupIds.has(id)))
    .map(record => record.source_record_id);
}

const industries = {};
for (const industry of displayIndustries.display_industries) {
  const excluded_occupations = industry.occupations.filter(occupation => isNonOccupationLabel(occupation.label));
  const visibleOccupations = industry.occupations.filter(occupation => !isNonOccupationLabel(occupation.label));
  const categoryRules = rulesFor(industry.label);
  // A specifically supplied direction remains meaningful with one matching
  // title. Generic automatic families require at least two titles.
  const candidates = groupCandidates(visibleOccupations, categoryRules, SUBCATEGORY_RULES[industry.label] ? 1 : 2);
  // A user-supplied directory is structural: retain its empty directions so
  // the product does not silently rewrite the requested taxonomy when the
  // current snapshot has no matching record.
  if (SUBCATEGORY_RULES[industry.label]) {
    const presentRuleIds = new Set(candidates.map(group => group.rule_id));
    for (const rule of categoryRules) if (!presentRuleIds.has(rule.id)) candidates.push({
      rule_id: rule.id,
      relation: rule.relation,
      label: rule.label,
      members: [],
    });
  }
  const groupedIds = new Set(candidates.flatMap(group => group.members.map(member => member.node_id)));
  const ungrouped = visibleOccupations.filter(occupation => !groupedIds.has(occupation.node_id));
  // Curated display directories always retain an "其他职业" entry, even when
  // this snapshot has no unmatched titles, so the user-defined navigation
  // structure does not change with the current data slice.
  if (ungrouped.length || industry.label !== '其他职业') candidates.push({
    rule_id: 'unclustered-occupations',
    relation: 'unclustered_display_titles',
    label: '其他职业',
    members: ungrouped,
  });
  const display_groups = candidates.map((group, index) => {
    const records = new Set(group.members.flatMap(member => evidenceIds(industry.source_industry_labels || [industry.label], member)));
    const role_subcategories = buildRoleSubcategories(group.label, group.members).map((subcategory, childIndex) => ({
      role_subcategory_id: `DRS-${industry.node_id}-${String(index + 1).padStart(3, '0')}-${String(childIndex + 1).padStart(2, '0')}`,
      label: subcategory.label,
      rule_id: subcategory.id,
      relation: subcategory.relation,
      member_occupation_ids: subcategory.members.map(member => member.node_id),
      member_count: subcategory.members.length,
    }));
    return {
      display_group_id: `DOG-${industry.node_id}-${String(index + 1).padStart(3, '0')}`,
      label: group.label,
      rule_id: group.rule_id,
      relation: group.relation,
      member_occupation_ids: group.members.map(member => member.node_id),
      member_labels: group.members.map(member => member.label),
      member_count: group.members.length,
      distinct_recruitment_record_count: records.size,
      role_subcategories,
    };
  });
  industries[industry.node_id] = {
    display_groups,
    excluded_occupations: excluded_occupations.map(occupation => ({
      occupation_id: occupation.node_id,
      label: occupation.label,
      reason: 'source_prose_not_occupation',
    })),
  };
}

const output = {
  schema_version: 'display-occupation-groups-v3',
  demand_metric: 'distinct_recruitment_record_count',
  generated_from: [inputFile, 'occupation_details/*.json'],
  rules: [...new Map([...DEFAULT_RULES, ...Object.values(SUBCATEGORY_RULES).flat(), TITLE_SUFFIX_RULE].map(({ id, label, relation }) => [id, { id, label: label || '去除岗位后缀后的精确标题变体', relation }])).values(), { id: 'unclustered-occupations', label: '其他职业', relation: 'unclustered_display_titles' }],
  exclusions: [{ id: 'source-prose-not-occupation', description: '公告说明性文本被误拆为职业标签时，仅从职业展示层排除。' }],
  industries,
};
writeFileSync(join(root, outputFile), `${JSON.stringify(output, null, 2)}\n`);
console.log(`Wrote ${join(root, outputFile)}`);
