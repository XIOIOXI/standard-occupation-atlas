import React, { useMemo } from 'react';
import LocationJobBrowser from './LocationJobBrowser.jsx';
import { useSnoEvidence } from '../lib/snoEvidence.js';
import { scopeRecordTitles } from '../lib/scopedRoleTitles.js';

export default function SnoCategoryMarket({ category, occupations }) {
  const sourceRecordIds = useMemo(() => [...new Set(occupations.flatMap(occupation => occupation.sourceRecordIds || []))].sort(), [occupations]);
  const sourceAtomicIds = useMemo(() => [...new Set(occupations.flatMap(occupation => occupation.sourceAtomicIds || []))].sort(), [occupations]);
  const { records, loading, error } = useSnoEvidence(category.category_id || `${category.level_1}/${category.level_2}/${category.level_3}`, sourceAtomicIds, sourceRecordIds);
  const level2 = category.display_level_2 || category.level_2;
  const isLevel2Aggregate = category.is_level2_aggregate;
  const title = isLevel2Aggregate ? level2 : category.level_3;
  const path = category.is_holding_group ? `${category.level_1}${level2 ? ` / ${level2}` : ''} / 展示层暂存分组` : category.is_other ? `${category.level_1} / 其他岗位` : isLevel2Aggregate ? `${category.level_1} / ${level2}` : `${category.level_1} / ${level2} / ${category.level_3}`;
  const note = category.is_holding_group ? '这是展示层暂存分组，不是正式职业目录；保留原状态并直接关联原始招聘岗位。' : category.is_other ? '这些岗位只能确认到当前上级，尚不足以进入正式三级类别；作为展示层“其他岗位”气泡直接关联原始招聘记录。' : isLevel2Aggregate ? '该二级目录没有正式三级子节点；本页直接展示归入该二级的原始招聘岗位记录。' : '该页从三级类别直接展示关联的原始招聘岗位记录；标准职业名称仅用于后台关联，不作为前端展示层级。';
  if (error) return <section className="occupation-sheet"><div className="occupation-hero"><h1>{title}</h1><p role="alert">关联招聘岗位读取失败：{error.message}</p></div></section>;
  if (loading) return <section className="occupation-sheet"><div className="occupation-hero"><h1>{title}</h1><p className="occupation-meta">{path}<span>正在读取关联招聘岗位…</span></p></div></section>;
  if (!records.length) return <section className="occupation-sheet"><div className="occupation-hero"><h1>{title}</h1><p className="occupation-meta">{path}<span>暂无可追溯的招聘记录</span></p></div></section>;
  return <section className="occupation-sheet sno-occupation-sheet">
    <div className="occupation-hero">
      
      <h1>{title}</h1>
      <p className="occupation-meta">{path}<span>{sourceAtomicIds.length.toLocaleString()} 个关联岗位 · {records.length.toLocaleString()} 条招聘记录</span></p>
    </div>
    <LocationJobBrowser key={category.category_id || path} browseKey={`category:${category.category_id || path}`} records={scopeRecordTitles(records, occupations)} intro={note} />
  </section>;
}
