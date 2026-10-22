import React, { useDeferredValue, useEffect, useMemo, useRef, useState } from 'react';
import './JobSearch.css';
import { useBrowseState } from '../hooks/useBrowseState.js';
import { useBrowseScroll } from '../hooks/useBrowseScroll.js';
import { PROVINCES } from '../lib/locationDistribution';

const DATA_URL = '/data/processed/record_role_classification_v1/full_drafts/sno_v31_reasonable_primary_v4_display/job_search_index_v1.json';
const META_URL = '/data/processed/record_role_classification_v1/full_drafts/sno_v31_reasonable_primary_v4_display/job_search_index_v1.meta.json';
const FACETS_URL = '/data/processed/record_role_classification_v1/full_drafts/sno_v31_reasonable_primary_v4_display/job_search_facets_v1.json';
const LIMIT = 100;
const LOCATION_CACHE_PREFIX = 'job-search-location-options:';
const clean = value => String(value || '').trim();
const lower = value => clean(value).toLocaleLowerCase();
const matches = (value, query) => !query || lower(value).includes(lower(query));
const dateText = value => /^\d{4}-\d{2}-\d{2}$/.test(clean(value)) ? value : '未提供';
const pathLabel = item => (item.category_paths || []).map(path => [path.level_1, path.level_2, path.level_3].filter(Boolean).join(' · ')).filter(Boolean).join(' / ');
const graduationYears = value => [...new Set((clean(value).match(/20\d{2}/g) || []).map(Number))];
const sessionMatchesBucket = (session, bucket) => {
  if (!bucket) return true;
  const years = graduationYears(session);
  if (bucket === 'earlier') return years.some(year => year <= 2025);
  if (bucket === 'current') return years.includes(2026);
  return years.some(year => year >= 2027);
};
const GLOBAL_LOCATION_REGIONS = [['全国/多地', ['全国', '全国多地']], ['海外', ['海外', '新加坡', '美国', '英国', '日本', '韩国']]];
const locationMatchesRegion = (location, region) => {
  if (!region) return true;
  if (region.startsWith('city:')) return clean(location).includes(region.slice(5));
  const regionName = region.startsWith('province:') ? region.slice(9) : region;
  const groups = [...PROVINCES, ...GLOBAL_LOCATION_REGIONS];
  const matched = groups.find(([name]) => name === regionName);
  return Boolean(matched && matched[1].some(keyword => clean(location).includes(keyword)));
};
const EMPTY_FACETS = { taxonomy: [], location_values: [], city_options: [] };

function readLocationOptions(version) {
  if (!version) return null;
  try {
    const cached = JSON.parse(window.localStorage.getItem(`${LOCATION_CACHE_PREFIX}${version}`) || 'null');
    return Array.isArray(cached?.regions) && Array.isArray(cached?.cities) ? cached : null;
  } catch {
    return null;
  }
}

function saveLocationOptions(version, regions, cities) {
  if (!version) return;
  try { window.localStorage.setItem(`${LOCATION_CACHE_PREFIX}${version}`, JSON.stringify({ regions, cities })); } catch { /* The current visit remains usable without storage. */ }
}

function withinDate(value, from, to) {
  if (!from && !to) return true;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(clean(value))) return false;
  return (!from || value >= from) && (!to || value <= to);
}

export default function JobSearch({ onBack }) {
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]);
  const [resultCount, setResultCount] = useState(0);
  const [facets, setFacets] = useState(EMPTY_FACETS);
  const [facetsLoading, setFacetsLoading] = useState(true);
  const [filters, setFilters] = useBrowseState('search:filters', { query: '', company: '', location: '', industry: '', graduationBuckets: [], statuses: [], level1: '', level2: '', level3: '', updatedFrom: '', updatedTo: '', deadlineFrom: '', deadlineTo: '', sort: '' }, value => value && ['query','company','location','industry','level1','level2','level3','updatedFrom','updatedTo','deadlineFrom','deadlineTo','sort'].every(key => typeof value[key] === 'string') && ['graduationBuckets','statuses'].every(key => Array.isArray(value[key]) && value[key].every(item => typeof item === 'string')));
  const [browseLevel1, setBrowseLevel1] = useBrowseState('search:direction', '', value => typeof value === 'string');
  const [showDirectory, setShowDirectory] = useState(false);
  const [indexVersion, setIndexVersion] = useState('');
  const [cachedLocationOptions, setCachedLocationOptions] = useState(null);
  const worker = useRef(null);
  const deferredFilters = useDeferredValue(filters);

  useEffect(() => {
    let active = true;
    fetch(META_URL, { cache: 'no-store' })
      .then(response => response.ok ? response.json() : Promise.reject())
      .then(({ content_hash: version }) => {
        if (!active) return;
        setIndexVersion(version);
        setCachedLocationOptions(readLocationOptions(version));
      })
      .catch(() => { if (active) setError('岗位搜索筛选索引暂时无法读取。'); });
    fetch(FACETS_URL, { cache: 'no-store' })
      .then(response => response.ok ? response.json() : Promise.reject())
      .then(payload => { if (active) setFacets({ ...EMPTY_FACETS, ...payload }); })
      .catch(() => { if (active) setError('岗位搜索筛选索引暂时无法读取。'); })
      .finally(() => { if (active) setFacetsLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const searchWorker = new Worker(new URL('../workers/jobSearch.worker.js', import.meta.url), { type: 'module' });
    worker.current = searchWorker;
    searchWorker.onmessage = ({ data }) => {
      if (data.type === 'loading') return;
      if (data.type === 'ready') { setIndexVersion(data.version); return; }
      if (data.type === 'results') { setResults(data.results); setResultCount(data.count); setLoading(false); return; }
      if (data.type === 'error') { setError('岗位详情暂时无法读取。'); setLoading(false); }
    };
    searchWorker.postMessage({ type: 'init', metaUrl: META_URL, dataUrl: DATA_URL });
    return () => { searchWorker.terminate(); worker.current = null; };
  }, []);

  const taxonomy = facets.taxonomy;
  const visibleLevel1 = browseLevel1 || filters.level1 || taxonomy[0]?.level1 || '';
  const activeTaxonomy = taxonomy.find(item => item.level1 === visibleLevel1);
  const locationRegions = useMemo(() => [...PROVINCES, ...GLOBAL_LOCATION_REGIONS].filter(([, keywords]) => facets.location_values.some(location => keywords.some(keyword => clean(location).includes(keyword)))).map(([name]) => name), [facets.location_values]);
  const cityOptions = useMemo(() => {
    const provinceNames = new Set(PROVINCES.map(([name]) => name));
    const excluded = new Set(['全国', '全国多地', '海外', '全球', '顶级节点', '……', '......']);
    const knownFragments = [...PROVINCES, ...GLOBAL_LOCATION_REGIONS].flatMap(([, keywords]) => keywords);
    return facets.city_options.filter(city => !provinceNames.has(city) && !excluded.has(city) && !knownFragments.some(fragment => fragment !== city && city.includes(fragment))).sort(new Intl.Collator('zh-Hans-CN-u-co-pinyin').compare);
  }, [facets.city_options]);
  useEffect(() => {
    if (!indexVersion || facetsLoading) return;
    saveLocationOptions(indexVersion, locationRegions, cityOptions);
    setCachedLocationOptions({ regions: locationRegions, cities: cityOptions });
  }, [indexVersion, facetsLoading, locationRegions, cityOptions]);
  const availableLocationRegions = cachedLocationOptions?.regions || locationRegions;
  const availableCityOptions = cachedLocationOptions?.cities || cityOptions;
  const locationOptionsReady = Boolean(cachedLocationOptions) || !facetsLoading;
  const hasSearchCriteria = Boolean(deferredFilters.query || deferredFilters.company || deferredFilters.location || deferredFilters.industry || deferredFilters.graduationBuckets.length || deferredFilters.statuses.length || deferredFilters.level1 || deferredFilters.updatedFrom || deferredFilters.updatedTo || deferredFilters.deadlineFrom || deferredFilters.deadlineTo);
  useEffect(() => {
    if (!hasSearchCriteria) { setResults([]); setResultCount(0); return; }
    setLoading(true);
    worker.current?.postMessage({ type: 'search', filters: deferredFilters });
  }, [deferredFilters, hasSearchCriteria]);
  useBrowseScroll(`search:${JSON.stringify(deferredFilters)}`, null, !loading && (!hasSearchCriteria || results.length > 0));
  const set = key => event => { setShowDirectory(false); setFilters(current => ({ ...current, [key]: event.target.value })); };
  const reset = () => { setFilters({ query: '', company: '', location: '', industry: '', graduationBuckets: [], statuses: [], level1: '', level2: '', level3: '', updatedFrom: '', updatedTo: '', deadlineFrom: '', deadlineTo: '', sort: '' }); setBrowseLevel1(''); setShowDirectory(false); };
  const chooseDirection = (level1, level2 = '', level3 = '') => { setBrowseLevel1(level1); setFilters(current => ({ ...current, level1, level2, level3 })); if (level2) setShowDirectory(false); };
  const clearDirection = () => { setBrowseLevel1(''); setFilters(current => ({ ...current, level1: '', level2: '', level3: '' })); setShowDirectory(false); };
  const toggle = (key, value) => { setShowDirectory(false); setFilters(current => ({ ...current, [key]: current[key].includes(value) ? current[key].filter(item => item !== value) : [...current[key], value] })); };
  const toggleSort = value => { setShowDirectory(false); setFilters(current => ({ ...current, sort: current.sort === value ? '' : value })); };

  return <section className="job-search-page">
    <nav className="breadcrumbs" aria-label="岗位搜索导航"><button onClick={onBack}>← 返回职业图鉴</button><span>/</span><span>岗位搜索</span></nav>
    <header className="job-search-hero"><h1>岗位搜索</h1></header>
    {error ? <p className="daily-load-error">{error}</p> : <>
      <section className="job-search-command" aria-label="岗位搜索"><label className="job-search-keyword"><span>搜岗位、公司或行业</span><input value={filters.query} onChange={set('query')} placeholder="例如：产品经理、半导体、字节跳动" /></label><label className="job-search-location"><span>地点</span><select disabled={!locationOptionsReady} value={filters.location} onChange={set('location')}><option value="">{locationOptionsReady ? '选择地点' : '地点加载中…'}</option><optgroup label="省级行政区">{availableLocationRegions.map(region => <option key={region} value={`province:${region}`}>{region}</option>)}</optgroup><optgroup label="具体城市（按拼音首字母）">{availableCityOptions.map(city => <option key={city} value={`city:${city}`}>{city}</option>)}</optgroup></select></label><button className="job-search-clear" disabled={!hasSearchCriteria && !filters.sort} onClick={reset}>重置</button></section>
      {!showDirectory && <section className="job-search-quick-filters" aria-label="快捷筛选"><div className="job-search-selected-role"><span>岗位类型</span>{filters.level1 ? <><button className="is-chosen" onClick={() => setShowDirectory(true)}>{[filters.level1, filters.level2, filters.level3].filter(Boolean).join(' · ')}</button><button className="job-search-remove-role" aria-label="清除岗位类型" onClick={clearDirection}>×</button></> : <button onClick={() => setShowDirectory(true)}>选择岗位类型</button>}</div><div><span>毕业届次</span><button className={filters.graduationBuckets.includes('earlier') ? 'is-active' : ''} aria-pressed={filters.graduationBuckets.includes('earlier')} onClick={() => toggle('graduationBuckets', 'earlier')}>2025 届及以前</button><button className={filters.graduationBuckets.includes('current') ? 'is-active' : ''} aria-pressed={filters.graduationBuckets.includes('current')} onClick={() => toggle('graduationBuckets', 'current')}>2026 届</button><button className={filters.graduationBuckets.includes('future') ? 'is-active' : ''} aria-pressed={filters.graduationBuckets.includes('future')} onClick={() => toggle('graduationBuckets', 'future')}>2027 届及以后</button></div><div><span>归类状态</span><button className={filters.statuses.includes('classified') ? 'is-active' : ''} aria-pressed={filters.statuses.includes('classified')} onClick={() => toggle('statuses', 'classified')}>已归类</button><button className={filters.statuses.includes('pending') ? 'is-active' : ''} aria-pressed={filters.statuses.includes('pending')} onClick={() => toggle('statuses', 'pending')}>待确认</button></div><label className="job-search-order"><span>排序</span><select aria-label="排序" value={filters.sort || "updated"} onChange={set("sort")}><option value="updated">最新更新</option><option value="deadline">截止日期最早</option></select></label></section>}
      {showDirectory && <section className="job-search-browser" aria-label="职业方向目录"><header><div><h2>选择岗位类型</h2></div><button onClick={() => setShowDirectory(false)}>收起目录</button></header><div className="job-search-direction-grid"><nav aria-label="一级职业方向">{taxonomy.map(item => <button key={item.level1} className={visibleLevel1 === item.level1 ? 'is-active' : ''} onClick={() => setBrowseLevel1(item.level1)} aria-pressed={visibleLevel1 === item.level1}>{item.level1}<span>›</span></button>)}</nav><div className="job-search-subdirections"><button className="job-search-all-direction" onClick={() => { chooseDirection(visibleLevel1); setShowDirectory(false); }}>选择“{visibleLevel1}”全部岗位</button>{activeTaxonomy?.groups.map(group => <section key={group.label}><button className="job-search-level2" onClick={() => chooseDirection(visibleLevel1, group.label)}>{group.label}</button><div>{group.roles.length ? group.roles.map(role => <button key={role} className={filters.level3 === role && filters.level2 === group.label ? 'is-selected' : ''} onClick={() => chooseDirection(visibleLevel1, group.label, role)}>{role}</button>) : <button className={filters.level2 === group.label && !filters.level3 ? 'is-selected' : ''} onClick={() => chooseDirection(visibleLevel1, group.label)}>本方向岗位</button>}</div></section>)}</div></div></section>}
      {!hasSearchCriteria && !showDirectory && <p className="job-search-idle">输入关键词或选择筛选条件查看岗位。</p>}
      {hasSearchCriteria && <section className="job-search-results" aria-live="polite">
        <header><div><h2>{loading ? '搜索中…' : `${resultCount.toLocaleString()} 个岗位`}</h2></div></header>
        {!loading && resultCount > LIMIT && <p className="job-search-limit">为保持页面响应速度，当前展示前 {LIMIT} 个岗位；请继续缩小筛选范围。</p>}
        {!loading && !results.length && <p className="job-search-empty">没有符合条件的岗位。可尝试减少筛选条件或更换关键词。</p>}
        <div className="job-search-list" aria-busy={loading}>{!loading && results.map(item => <article key={item.search_item_id}>
          <div className="job-search-title"><h3>{item.title_unit || '岗位名称未提供'}</h3><span className={`job-search-status is-${item.result_status}`}>{item.result_status === 'classified' ? '已归类' : '待确认'}</span></div>
          <p className="job-search-company">{item.company_name || '企业未提供'}{item.company_type ? ` · ${item.company_type}` : ''}</p>
          <dl><div><dt>地点</dt><dd>{item.location || '未提供'}</dd></div><div><dt>行业</dt><dd>{item.industry_category || '未提供'}</dd></div><div><dt>源更新时间</dt><dd>{dateText(item.source_updated_at)}</dd></div><div><dt>截止日期</dt><dd>{dateText(item.deadline)}</dd></div></dl>
          {pathLabel(item) ? <p className="job-search-path">{pathLabel(item)}</p> : <p className="job-search-pending">{item.reason || '职业归属待确认'}</p>}
          {(item.recruitment_url || item.announcement_url) && <p className="source-links">{item.recruitment_url && <a href={item.recruitment_url} target="_blank" rel="noreferrer">招聘来源</a>}{item.announcement_url && <a href={item.announcement_url} target="_blank" rel="noreferrer">招聘公告</a>}</p>}
        </article>)}</div>
      </section>}
    </>}
  </section>;
}
