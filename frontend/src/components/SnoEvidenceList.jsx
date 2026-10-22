import React from 'react';

function displayCompany(record) {
  return record.company_name?.trim() || '未提供企业名称';
}

function displayLocation(record) {
  return record.location?.trim() || '地点未提供';
}

function displayRole(record) {
  if (record.display_job_titles) return record.display_job_titles.join('、') || '对应岗位名称待确认';
  return record.job_title_units?.filter(Boolean).join('、') || record.raw_job_title || '岗位名称未提供';
}

export default function SnoEvidenceList({ records }) {
  return <section className="evidence-list sno-evidence-list" aria-label="具体岗位列表">
    {records.map(record => <article className="sno-evidence-row" key={record.source_record_id}>
      <strong>{displayCompany(record)}{record.company_type && <span className="sno-company-type">{record.company_type}</span>}</strong>
      <span className="muted">{displayLocation(record)}</span>
      <p className="sno-evidence-role">— {displayRole(record)}</p>
      {(record.recruitment_url || record.announcement_url) && <p className="source-links">
        {record.recruitment_url && <a href={record.recruitment_url} target="_blank" rel="noreferrer">招聘来源</a>}
        {record.announcement_url && <a href={record.announcement_url} target="_blank" rel="noreferrer">招聘公告</a>}
      </p>}
    </article>)}
  </section>;
}
