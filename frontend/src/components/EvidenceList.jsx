import React, { useEffect, useState } from 'react';
import PageControls from './PageControls.jsx';
export default function EvidenceList({ records, compact = false, title = '招聘证据', countLabel = `${records.length} 条去重记录`, intro, occupationContext = false }) {
  const [page, setPage] = useState(0);
  const size = compact ? 5 : 10;
  const pageCount = Math.ceil(records.length / size);
  useEffect(() => { setPage(0); }, [records.length]);
  return <section className={`evidence-list${compact ? ' compact' : ''}`} aria-label="招聘证据">
    <h3>{title} <small>{countLabel}</small></h3>
    {intro && <p className="muted">{intro}</p>}
    {records.slice(page * size, (page + 1) * size).map(record => <article key={record.source_record_id}>
      <strong>{record.company_name || '未提供公司名称'}</strong><span className="muted">{record.location || '地点未提供'}</span>
      {occupationContext ? <>
        <p className="evidence-raw-title"><span>原始岗位文本</span>{record.raw_job_title}</p>
        <small>本职业对应岗位单元：{record.job_title_units.join('、')}{record.education_requirement ? ` · 学历：${record.education_requirement}` : ''}</small>
      </> : <>
        <p>{record.raw_job_title}</p><small>原子岗位：{record.job_title_units.join('、')}{record.education_requirement ? ` · 学历：${record.education_requirement}` : ''}</small>
      </>}
      {(record.recruitment_url || record.announcement_url) && <p className="source-links">{record.recruitment_url && <a href={record.recruitment_url} target="_blank" rel="noreferrer">招聘链接</a>}{record.announcement_url && <a href={record.announcement_url} target="_blank" rel="noreferrer">公告链接</a>}</p>}
      <details><summary>查看来源标识</summary><p>Record: {record.source_record_id}</p><p>Job Groups: {record.job_group_ids.join(', ')}</p><p>Atomic units: {record.atomic_unit_ids.join(', ')}</p><p>来源：frozen job_groups_v2/job_group_members.jsonl</p></details>
    </article>)}
    <PageControls page={page} pageCount={pageCount} onPageChange={setPage} label="招聘来源分页" />
  </section>;
}
