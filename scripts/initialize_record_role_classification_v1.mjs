import { createHash } from 'node:crypto';
import { createReadStream, existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { createInterface } from 'node:readline';

const source = 'data/processed/job_groups_v2/job_group_members.jsonl';
const outputDir = 'data/processed/record_role_classification_v1';
mkdirSync(outputDir, { recursive: true });
const records = new Map(); const roles = []; const seen = new Set();
const lineReader = createInterface({ input: createReadStream(source, { encoding: 'utf8' }), crlfDelay: Infinity });
for await (const line of lineReader) {
  if (!line) continue;
  const item = JSON.parse(line);
  if (!records.has(item.source_record_id)) records.set(item.source_record_id, {
    source_record_id: item.source_record_id, raw_job_title: item.raw_job_title, company_name: item.company_name,
    industry_category: item.industry_category, location: item.location, record_status: 'pending_classification',
  });
  if (seen.has(item.source_atomic_unit_id)) continue;
  seen.add(item.source_atomic_unit_id);
  roles.push({
    record_role_id: `RR-${createHash('sha256').update(`${item.source_record_id}\u0000${item.source_atomic_unit_id}`).digest('hex').slice(0,20)}`,
    source_record_id: item.source_record_id, source_atomic_unit_id: item.source_atomic_unit_id,
    source_title: item.job_title_unit, raw_job_title: item.raw_job_title, company_name: item.company_name,
    industry_category: item.industry_category, classification_status: 'pending_classification',
  });
}
const summary = { schema_version: 'record-role-classification-v1', source: source, source_recruitment_record_count: records.size, reusable_atomic_role_count: roles.length, duplicate_source_atomic_unit_ids: 0, classification_scope: 'independent_from_legacy_display_nodes', generated_at: new Date().toISOString() };
writeFileSync(`${outputDir}/source_record_ledger.json`, `${JSON.stringify([...records.values()], null, 2)}\n`);
writeFileSync(`${outputDir}/record_roles.json`, `${JSON.stringify({ ...summary, roles }, null, 2)}\n`);
writeFileSync(`${outputDir}/summary.json`, `${JSON.stringify(summary, null, 2)}\n`);
