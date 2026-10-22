import React, { useEffect, useMemo, useState } from 'react';
import './DailyUpdatesView.css';
import { useBrowseState } from '../hooks/useBrowseState.js';
import { useBrowseScroll } from '../hooks/useBrowseScroll.js';
import SnoEvidenceList from './SnoEvidenceList.jsx';

const UNKNOWN_DATE = '日期未提供';
const WEEKDAYS = ['一', '二', '三', '四', '五', '六', '日'];
const DAILY_JOBS_URL = '/data/processed/record_role_classification_v1/full_drafts/sno_v31_reasonable_primary_v4_display/daily_jobs_v1.json';
const dateOf = item => item.source_updated_at || item.updated_at_original_text || UNKNOWN_DATE;
const parseDate = value => {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  return match ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3])) : null;
};
const dateKey = date => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
const monthLabel = date => `${date.getFullYear()} 年 ${date.getMonth() + 1} 月`;
const toEvidenceRecords = items => {
  const records = new Map();
  for (const item of items) {
    const id = item.source_record_id || item.daily_item_id;
    const record = records.get(id) || {
      source_record_id: id,
      company_name: item.company_name,
      company_type: item.company_type,
      location: item.location,
      recruitment_url: item.recruitment_url,
      announcement_url: item.announcement_url,
      job_title_units: [],
    };
    if (item.title_unit && !record.job_title_units.includes(item.title_unit)) record.job_title_units.push(item.title_unit);
    records.set(id, record);
  }
  return [...records.values()];
};

export default function DailyUpdatesView({ onBack }) {
  const [jobs, setJobs] = useState([]);
  const [dateFrom, setDateFrom] = useState(null);
  const [loadError, setLoadError] = useState(null);
  useEffect(() => {
    let active = true;
    fetch(DAILY_JOBS_URL)
      .then(response => response.ok ? response.json() : Promise.reject(new Error(`daily jobs ${response.status}`)))
      .then(payload => { if (active) { setJobs(Array.isArray(payload.items) ? payload.items : []); setDateFrom(payload.date_from || null); } })
      .catch(() => { if (active) setLoadError('每日岗位数据暂时无法读取。'); });
    return () => { active = false; };
  }, []);
  const days = useMemo(() => {
    const grouped = new Map();
    for (const item of jobs) {
      if (!['classified', 'pending'].includes(item.result_status)) continue;
      const date = dateOf(item); const group = grouped.get(date) || [];
      group.push(item); grouped.set(date, group);
    }
    return [...grouped.entries()]
      .map(([date, items]) => ({ date, items, parsedDate: parseDate(date) }))
      .sort((a, b) => (b.parsedDate?.getTime() || 0) - (a.parsedDate?.getTime() || 0));
  }, [jobs]);
  const datedDays = days.filter(day => day.parsedDate);
  const undatedDay = days.find(day => !day.parsedDate);
  const initialDate = datedDays[0]?.date || undatedDay?.date || null;
  const [selectedDate, setSelectedDate] = useBrowseState('daily:date', null, value => value === UNKNOWN_DATE || Boolean(parseDate(value)));
  const [monthKey, setMonthKey] = useBrowseState('daily:month', '', value => Boolean(parseDate(value)));
  const month = parseDate(monthKey) || parseDate(selectedDate) || datedDays[0]?.parsedDate || new Date();
  const scrollRef = React.useRef(null);
  useBrowseScroll(`daily:${selectedDate || initialDate}`, scrollRef, jobs.length > 0);

  const active = days.find(day => day.date === selectedDate) || datedDays[0] || undatedDay;
  const activeRecords = useMemo(() => toEvidenceRecords(active?.items || []), [active]);
  const daysInMonth = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const firstWeekday = (new Date(month.getFullYear(), month.getMonth(), 1).getDay() + 6) % 7;
  const countsByDate = new Map(datedDays.map(day => [day.date, day.items.length]));
  const calendarCells = Array.from({ length: firstWeekday + daysInMonth }, (_, index) => index < firstWeekday ? null : new Date(month.getFullYear(), month.getMonth(), index - firstWeekday + 1));
  const moveMonth = offset => setMonthKey(dateKey(new Date(month.getFullYear(), month.getMonth() + offset, 1)));

  return <section className="update-batch-view daily-updates-view">
    <nav className="breadcrumbs"><button onClick={onBack}>← 返回职业图鉴</button><span>/</span><span>每日新增</span></nav>
    <header className="update-batch-hero"><h1>每日新增岗位</h1><p>按招聘源更新时间浏览{dateFrom ? `（${dateFrom} 起）` : ''}。选择带气泡的日期查看当天新增；该日期不是推测的首次发布日期。</p></header>
    <div className="daily-workspace">
    {loadError ? <p className="daily-load-error">{loadError}</p> : <section className="daily-calendar" aria-label="每日新增岗位日历">
      <div className="daily-calendar-header"><button onClick={() => moveMonth(-1)} aria-label="上一个月">←</button><h2>{monthLabel(month)}</h2><button onClick={() => moveMonth(1)} aria-label="下一个月">→</button></div>
      <div className="daily-calendar-weekdays">{WEEKDAYS.map(day => <span key={day}>{day}</span>)}</div>
      <div className="daily-calendar-grid">{calendarCells.map((date, index) => {
        if (!date) return <span className="daily-calendar-blank" key={`blank-${index}`} aria-hidden="true" />;
        const key = dateKey(date); const count = countsByDate.get(key); const selected = (selectedDate || initialDate) === key;
        return <button key={key} className={`daily-calendar-day${count ? ' has-updates' : ''}${selected ? ' is-active' : ''}`} onClick={() => count && setSelectedDate(key)} disabled={!count} aria-label={`${key}${count ? `，${count} 个新增岗位` : '，无新增岗位'}`}>
          <span>{date.getDate()}</span>{count ? <b>{count}</b> : null}
        </button>;
      })}</div>
      {undatedDay && <button className={`daily-undated-button${selectedDate === UNKNOWN_DATE ? ' is-active' : ''}`} onClick={() => setSelectedDate(UNKNOWN_DATE)}>日期未提供（{undatedDay.items.length}）</button>}
    </section>}
    {!loadError && <section className="daily-evidence-section" aria-label={`${active?.date || UNKNOWN_DATE} 的新增岗位`}><h2>{active?.date || '暂无新增岗位'}</h2><div ref={scrollRef} className="daily-record-scroll" tabIndex={0} role="region" aria-label="当日岗位列表"><SnoEvidenceList records={activeRecords} /></div></section>}
    </div>
  </section>;
}
