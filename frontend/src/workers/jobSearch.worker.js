import { PROVINCES } from '../lib/locationDistribution';
import { loadVersionedIndex } from '../lib/versionedIndexCache';

const GLOBAL_LOCATION_REGIONS = [['全国/多地', ['全国', '全国多地']], ['海外', ['海外', '新加坡', '美国', '英国', '日本', '韩国']]];
const LIMIT = 100;
let items = null;
let pendingFilters = null;

const clean = value => String(value || '').trim();
const lower = value => clean(value).toLocaleLowerCase();
const matches = (value, query) => !query || lower(value).includes(lower(query));
const pathLabel = item => (item.category_paths || []).map(path => [path.level_1, path.level_2, path.level_3].filter(Boolean).join(' · ')).filter(Boolean).join(' / ');
const graduationYears = value => [...new Set((clean(value).match(/20\d{2}/g) || []).map(Number))];
const sessionMatchesBucket = (session, bucket) => {
  const years = graduationYears(session);
  if (bucket === 'earlier') return years.some(year => year <= 2025);
  if (bucket === 'current') return years.includes(2026);
  return years.some(year => year >= 2027);
};
const locationMatchesRegion = (location, region) => {
  if (!region) return true;
  if (region.startsWith('city:')) return clean(location).includes(region.slice(5));
  const name = region.startsWith('province:') ? region.slice(9) : region;
  const group = [...PROVINCES, ...GLOBAL_LOCATION_REGIONS].find(([label]) => label === name);
  return Boolean(group && group[1].some(keyword => clean(location).includes(keyword)));
};
const withinDate = (value, from, to) => {
  if (!from && !to) return true;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(clean(value))) return false;
  return (!from || value >= from) && (!to || value <= to);
};

function search(filters) {
  if (!items) { pendingFilters = filters; return; }
  const filtered = items.filter(item => {
    const searchable = [item.title_unit, item.raw_job_title, item.company_name, item.industry_category, item.location, item.major_requirement, pathLabel(item)].join(' ');
    return matches(searchable, filters.query)
      && matches(item.company_name, filters.company)
      && locationMatchesRegion(item.location, filters.location)
      && matches(item.industry_category, filters.industry)
      && (!filters.graduationBuckets.length || filters.graduationBuckets.some(bucket => sessionMatchesBucket(item.recruitment_session, bucket)))
      && (!filters.statuses.length || filters.statuses.includes(item.result_status))
      && (!filters.level1 || (item.category_paths || []).some(path => path.level_1 === filters.level1))
      && (!filters.level2 || (item.category_paths || []).some(path => path.level_2 === filters.level2))
      && (!filters.level3 || (item.category_paths || []).some(path => path.level_3 === filters.level3))
      && withinDate(item.source_updated_at, filters.updatedFrom, filters.updatedTo)
      && withinDate(item.deadline, filters.deadlineFrom, filters.deadlineTo);
  });
  if (filters.sort === 'deadline') filtered.sort((left, right) => (left.deadline || '9999-12-31').localeCompare(right.deadline || '9999-12-31') || (right.source_updated_at || '').localeCompare(left.source_updated_at || ''));
  postMessage({ type: 'results', count: filtered.length, results: filtered.slice(0, LIMIT) });
}

self.onmessage = async ({ data }) => {
  if (data.type === 'search') { search(data.filters); return; }
  if (data.type !== 'init') return;
  try {
    postMessage({ type: 'loading' });
    const { payload, version } = await loadVersionedIndex({ metaUrl: data.metaUrl, dataUrl: data.dataUrl });
    items = (Array.isArray(payload.items) ? payload.items : []).sort((left, right) => (right.source_updated_at || '').localeCompare(left.source_updated_at || '') || clean(left.company_name).localeCompare(clean(right.company_name), 'zh'));
    postMessage({ type: 'ready', version });
    if (pendingFilters) { const filters = pendingFilters; pendingFilters = null; search(filters); }
  } catch {
    postMessage({ type: 'error' });
  }
};
