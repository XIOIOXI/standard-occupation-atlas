import React from 'react';
import LocationJobBrowser from './LocationJobBrowser.jsx';
import { useSnoEvidence } from '../lib/snoEvidence.js';
import { scopeRecordTitles } from '../lib/scopedRoleTitles.js';

export default function SnoOccupationDetail({ occupation }) {
  const { records, loading, error } = useSnoEvidence(occupation?.id, occupation?.sourceAtomicIds || [], occupation?.sourceRecordIds || []);
  const path = occupation.category ? `${occupation.category.level_1} / ${occupation.category.display_level_2 || occupation.category.level_2} / ${occupation.category.level_3}` : occupation.placement;
  if (error) return <section className="occupation-sheet"><div className="occupation-hero"><h1>{occupation.label}</h1><p role="alert">关联招聘来源读取失败：{error.message}</p></div></section>;
  if (loading) return <section className="occupation-sheet"><div className="occupation-hero"><h1>{occupation.label}</h1><p className="occupation-meta">{path}<span>正在读取关联招聘来源…</span></p></div></section>;
  if (!records.length) return <section className="occupation-sheet"><div className="occupation-hero"><h1>{occupation.label}</h1><p className="occupation-meta">{path}<span>暂无可追溯的招聘记录</span></p></div></section>;
  return <section className="occupation-sheet sno-occupation-sheet">
    <div className="occupation-hero"><h1>{occupation.label}</h1><p className="occupation-meta">{path}<span>{records.length} 条关联招聘记录</span></p></div>
    <LocationJobBrowser key={occupation.id} browseKey={`occupation:${occupation.id}`} records={scopeRecordTitles(records, [occupation])} intro="该页从标准职业关联展示原始招聘岗位记录；标准职业名称仅用于后台关联，不作为前端展示层级。" />
  </section>;
}
