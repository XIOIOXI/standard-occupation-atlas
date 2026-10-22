import React, { useCallback, useMemo, useState } from 'react';
import LocationDistributionMap from './LocationDistributionMap.jsx';
import SnoEvidenceList from './SnoEvidenceList.jsx';
import { filterRecordsByProvince, PROVINCES } from '../lib/locationDistribution.js';
import './LocationJobBrowser.css';
import { useBrowseState } from '../hooks/useBrowseState.js';
import { useBrowseScroll } from '../hooks/useBrowseScroll.js';

export default function LocationJobBrowser({ records, intro, browseKey }) {
  const [province, setProvince] = useBrowseState(`region:${browseKey}`, '', value => value === '' || PROVINCES.some(([name]) => name === value));
  const scrollRef = React.useRef(null);
  useBrowseScroll(`detail:${browseKey}:${province}`, scrollRef);
  const selectProvince = useCallback(name => setProvince(name), []);
  const filtered = useMemo(() => filterRecordsByProvince(records, province), [records, province]);
  return <div className="location-job-browser">
    <LocationDistributionMap records={records} selectedProvince={province} onSelectProvince={selectProvince} />
    <section className="location-job-sidebar" aria-label="按地区浏览岗位">
      <label className="location-job-filter">地区<select value={province} onChange={event => setProvince(event.target.value)}><option value="">全部地区</option>{PROVINCES.map(([name]) => <option key={name} value={name}>{name}</option>)}</select></label>
      <div ref={scrollRef} className="location-job-results" tabIndex={0} role="region" aria-label="岗位列表滚动区域">
        <p className="location-job-status" role="status">{province || '全部地区'} · {filtered.length} 条招聘记录</p>
        {!filtered.length && <p>该地区暂无关联岗位。</p>}
        <SnoEvidenceList records={filtered} intro={intro} />
      </div>
    </section>
  </div>;
}
