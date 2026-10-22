import React, { useEffect, useMemo, useState } from 'react';
import { useBrowseState } from '../hooks/useBrowseState.js';
import BubbleMap from './BubbleMap.jsx';
import SnoCategoryMarket from './SnoCategoryMarket.jsx';
import SnoOccupationDetail from './SnoOccupationDetail.jsx';
import { overlayUpdateBatches } from '../lib/updateProjection.js';

const DATA_ROOT = '/data/processed/record_role_classification_v1/full_drafts/sno_v31_reasonable_primary_v4_display/';
const PROJECTION_URL = `${DATA_ROOT}display_projection_v31_full_draft.json`;
const UPDATE_BATCHES_URL = `${DATA_ROOT}update_batches.json`;
const VIEW_LABELS = { mapped: '已映射（主归属）', review: '待复核 / 其他岗位', multi_role: '多职业待拆分', taxonomy_gap: '目录缺口', abnormal: '异常原子岗位' };

function occupationRow(occupation, extra = {}) {
  return { id: occupation.standard_occupation_id, label: occupation.label, status: occupation.status, reason: occupation.reason, originalGroupIds: occupation.original_group_ids || [], sourceAtomicIds: occupation.source_atomic_unit_ids || [], sourceRecordIds: occupation.source_record_ids || [], ...extra };
}

function atomicRoleCount(rows) {
  return new Set(rows.flatMap(row => row.sourceAtomicIds || [])).size;
}

function isAbnormalRow(row) {
  return row.id.startsWith('ABNORMAL:');
}

function displayLevel2(category) {
  return category?.display_level_2 || category?.level_2;
}

function summarizeRows(projection) {
  const mapped = Object.entries(projection.category_bubbles || {}).flatMap(([categoryId, item]) => (item.occupations || []).map(occupation => occupationRow(occupation, { categoryId, category: item.category, placement: '三级类别' })));
  const level2Direct = Object.values(projection.level2_direct_buckets || {}).flatMap(bucket => (bucket.occupations || []).map(occupation => occupationRow(occupation, { categoryId: bucket.bucket_id, category: { ...bucket.category, level_3: '本类岗位', is_direct_level2: true }, placement: '二级本类岗位' })));
  const otherById = new Map();
  const other = Object.values(projection.other_bubbles || {}).map(bucket => {
    const entry = {
      ...bucket,
      occupations: (bucket.occupations || []).map(occupation => occupationRow(occupation, { bucketId: bucket.bucket_id, placement: `${bucket.parent_level === 'level_2' ? '二级' : '一级'}其他岗位` })),
    };
    otherById.set(entry.bucket_id, entry);
    return entry;
  });
  const unplaced = (projection.unplaced || []).map(occupation => occupationRow(occupation, { placement: '待分类' }));
  const holding = Object.values(projection.holding_bubbles || {}).map(bucket => ({
    ...bucket,
    occupations: (bucket.occupations || []).map(occupation => occupationRow(occupation, { bucketId: bucket.bucket_id, placement: '展示层暂存分组' })),
  }));
  const holdingById = new Map(holding.map(bucket => [bucket.bucket_id, bucket]));
  const level1Holding = Object.values(projection.level1_holding_bubbles || {}).map(bucket => ({
    ...bucket,
    occupations: (bucket.occupations || []).map(occupation => occupationRow(occupation, { bucketId: bucket.bucket_id, placement: '展示层二级暂存分组' })),
  }));
  const level1HoldingById = new Map(level1Holding.map(bucket => [bucket.bucket_id, bucket]));
  const allRows = [...mapped, ...level2Direct, ...other.flatMap(bucket => bucket.occupations), ...holding.flatMap(bucket => bucket.occupations), ...level1Holding.flatMap(bucket => bucket.occupations), ...unplaced];
  const normalRows = allRows.filter(row => !isAbnormalRow(row));
  const review = normalRows.filter(row => row.status === 'review');
  const multiRole = normalRows.filter(row => row.status === 'multi_role');
  const gaps = normalRows.filter(row => row.status === 'taxonomy_gap');
  const abnormal = allRows.filter(isAbnormalRow);
  const mappedRows = [...mapped, ...level2Direct].filter(row => !isAbnormalRow(row));
  const statusCounts = Object.fromEntries(['mapped', 'review', 'multi_role', 'taxonomy_gap'].map(status => [status, atomicRoleCount(normalRows.filter(row => row.status === status))]));
  return { mapped: mappedRows, other, otherById, holding, holdingById, level1Holding, level1HoldingById, review, multiRole, gaps, abnormal, statusCounts };
}

function bubbleItems(rows, key, label) {
  const groups = new Map();
  rows.forEach(row => {
    const id = key(row);
    if (!id) return;
    const item = groups.get(id) || { id, label: label(row), atomicIds: new Set() };
    row.sourceAtomicIds.forEach(atomicId => item.atomicIds.add(atomicId));
    groups.set(id, item);
  });
  return [...groups.values()].map(item => ({ id: item.id, label: item.label, value: item.atomicIds.size }))
    .sort((left, right) => right.value - left.value || left.label.localeCompare(right.label, 'zh'));
}

function appendOtherBubble(items, bucket) {
  if (!bucket) return items;
  return [...items, { id: bucket.bucket_id, label: bucket.label, value: atomicRoleCount(bucket.occupations), otherBucket: bucket }]
    .sort((left, right) => right.value - left.value || left.label.localeCompare(right.label, 'zh'));
}

function appendHoldingBubbles(items, buckets) {
  return [...items, ...buckets.map(bucket => ({ id: bucket.bucket_id, label: bucket.label, value: atomicRoleCount(bucket.occupations), holdingBucket: bucket }))]
    .sort((left, right) => right.value - left.value || left.label.localeCompare(right.label, 'zh'));
}

function appendLevel1HoldingBubbles(items, buckets, level1) {
  const children = buckets.filter(bucket => bucket.parent_id === level1);
  return [...items, ...children.map(bucket => ({ id: bucket.bucket_id, label: bucket.label, value: atomicRoleCount(bucket.occupations), level1HoldingBucket: bucket }))]
    .sort((left, right) => right.value - left.value || left.label.localeCompare(right.label, 'zh'));
}

export default function SnoExplorer({ onViewDaily }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [view, setView] = useBrowseState('atlas:view', 'mapped', value => ['mapped','review','multi_role','taxonomy_gap','abnormal'].includes(value));
  const [categorySelection, setCategorySelection] = useBrowseState('atlas:category', null, value => value && typeof value.categoryId === 'string' && value.category && ['level_1','level_2','level_3'].every(key => value.category[key] == null || typeof value.category[key] === 'string') && (!value.occupationIds || Array.isArray(value.occupationIds) && value.occupationIds.every(id => typeof id === 'string')));
  const allRows = data ? [...data.groups.mapped, ...data.groups.review, ...data.groups.multiRole, ...data.groups.gaps, ...data.groups.abnormal, ...data.groups.other.flatMap(bucket => bucket.occupations), ...data.groups.holding.flatMap(bucket => bucket.occupations), ...data.groups.level1Holding.flatMap(bucket => bucket.occupations)] : [];
  const categoryDetail = categorySelection && data ? { ...categorySelection, occupations: categorySelection.occupationIds ? allRows.filter(row => categorySelection.occupationIds.includes(row.id)) : undefined } : null;
  const setCategoryDetail = selection => setCategorySelection(selection ? { categoryId: selection.categoryId, category: selection.category, occupationIds: selection.occupations?.map(row => row.id) } : null);
  const [detailId, setDetailId] = useBrowseState('atlas:occupation', '', value => typeof value === 'string');
  const detailOccupation = allRows.find(row => row.id === detailId) || null;
  const setDetailOccupation = row => setDetailId(row?.id || '');
  const [taxonomyPath, setTaxonomyPath] = useBrowseState('atlas:path', { level1: null, level2: null, level3: null }, value => value && ['level1','level2','level3'].every(key => value[key] === null || typeof value[key] === 'string'));
  useEffect(() => {
    if (!data) return;
    if (detailId && !allRows.some(row => row.id === detailId)) setDetailId('');
    if (categorySelection && !allRows.some(row => row.categoryId === categorySelection.categoryId || row.bucketId === categorySelection.categoryId || categorySelection.occupationIds?.includes(row.id))) setCategorySelection(null);
    if (taxonomyPath.level1 && !allRows.some(row => row.category?.level_1 === taxonomyPath.level1) && !data.groups.holding.some(bucket => bucket.label === taxonomyPath.level1)) {
      setTaxonomyPath({ level1:null, level2:null, level3:null });
    }
  }, [data, detailId, categorySelection, taxonomyPath.level1]);
  useEffect(() => {
    let active = true;
    Promise.all([
      fetch(PROJECTION_URL).then(response => response.ok ? response.json() : Promise.reject(new Error(`projection ${response.status}`))),
      fetch(UPDATE_BATCHES_URL).then(response => response.ok ? response.json() : { batches: [] }),
    ])
      .then(([projection, updates]) => {
        const mergedProjection = overlayUpdateBatches(projection, updates);
        if (active) setData({ projection: mergedProjection, groups: summarizeRows(mergedProjection) });
      })
      .catch(loadError => { if (active) setError(loadError); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (!data || view !== 'mapped' || !taxonomyPath.level1 || !taxonomyPath.level2 || categoryDetail) return;
    const hasLevel3 = (data.projection.catalog_level3 || []).some(category => category.level_1 === taxonomyPath.level1 && category.level_2 === taxonomyPath.level2);
    if (hasLevel3) return;
    const occupations = data.groups.mapped.filter(row => row.category?.level_1 === taxonomyPath.level1 && displayLevel2(row.category) === taxonomyPath.level2);
    setCategoryDetail({
      categoryId: `level2:${taxonomyPath.level1}/${taxonomyPath.level2}`,
      occupations,
      category: { category_id: `level2:${taxonomyPath.level1}/${taxonomyPath.level2}`, level_1: taxonomyPath.level1, level_2: taxonomyPath.level2, level_3: null, target_level: 'level_2', is_level2_aggregate: true },
    });
  }, [categorySelection, data, taxonomyPath.level1, taxonomyPath.level2, view]);
  const activeRows = useMemo(() => {
    if (!data) return [];
    const rows = view === 'review' ? data.groups.review : view === 'multi_role' ? data.groups.multiRole : view === 'taxonomy_gap' ? data.groups.gaps : view === 'abnormal' ? data.groups.abnormal : data.groups.mapped;
    return rows;
  }, [data, view]);
  const pathRows = useMemo(() => activeRows.filter(row => {
    if (view !== 'mapped') return true;
    return (!taxonomyPath.level1 || row.category?.level_1 === taxonomyPath.level1)
      && (!taxonomyPath.level2 || displayLevel2(row.category) === taxonomyPath.level2)
      && (!taxonomyPath.level3 || row.categoryId === taxonomyPath.level3);
  }), [activeRows, taxonomyPath, view]);
  const mapStage = useMemo(() => {
    if (!data || view !== 'mapped') return null;
    if (!taxonomyPath.level1) return { level: '一级', title: '一级职业大类', items: appendHoldingBubbles(bubbleItems(pathRows, row => row.category?.level_1, row => row.category.level_1), data.groups.holding) };
    if (!taxonomyPath.level2) {
      const other = data.groups.other.find(bucket => bucket.parent_level === 'level_1' && bucket.parent_id === taxonomyPath.level1);
      return { level: '二级', title: '二级职业方向', items: appendLevel1HoldingBubbles(appendOtherBubble(bubbleItems(pathRows, row => displayLevel2(row.category), row => displayLevel2(row.category)), other), data.groups.level1Holding, taxonomyPath.level1) };
    }
    // The map is driven only by genuine level-3 directory nodes.  A role
    // mapped directly to level 2 is intentionally not turned into a fake L3
    // bubble such as "本类岗位".
    const level3Rows = pathRows.filter(row => row.category?.target_level === 'level_3');
    const catalogLevel3 = (data.projection.catalog_level3 || []).filter(category => category.level_1 === taxonomyPath.level1 && category.level_2 === taxonomyPath.level2);
    if (!catalogLevel3.length) return null;
    const mappedItems = new Map(bubbleItems(level3Rows, row => row.categoryId, row => row.category.level_3).map(item => [item.id, item]));
    const items = catalogLevel3
      .map(category => {
        const mapped = mappedItems.get(category.category_id);
        return mapped || { id: category.category_id, label: category.level_3, value: 0, layoutValue: 2, empty: true };
      });
    return { level: '三级', title: '三级职业类别', items };
  }, [data, pathRows, taxonomyPath, view]);
  if (error) return <p role="alert">SNO 展示数据读取失败：{error.message}</p>;
  if (!data) return <p role="status">正在读取 SNO 职业目录…</p>;
  const counts = { ...data.groups.statusCounts, abnormal: atomicRoleCount(data.groups.abnormal) };
  const stageHeading = !taxonomyPath.level1 ? '标准职业图鉴' : taxonomyPath.level2 ? taxonomyPath.level2 : taxonomyPath.level1;
  const listTitle = VIEW_LABELS[view];
  const visibleJobCount = atomicRoleCount(pathRows);
  const listDescription = '按当前展示状态列出岗位名称分组；前端计数均按关联岗位数计算。';
  const controls = <section className="sno-status-panel" aria-label="岗位归类状态"><div className="sno-controls" aria-label="SNO 状态筛选">{Object.entries(VIEW_LABELS).map(([key, label]) => <button key={key} className={view === key ? 'is-active' : ''} onClick={() => { setView(key); setCategoryDetail(null); setTaxonomyPath({ level1: null, level2: null, level3: null }); }}>{label} <span>{counts[key]}</span></button>)}</div></section>;
  const breadcrumbs = view === 'mapped' && <nav className="sno-breadcrumbs" aria-label="SNO 展示层级"><button onClick={() => setTaxonomyPath({ level1: null, level2: null, level3: null })}>一级</button>{taxonomyPath.level1 && <><span>/</span><button onClick={() => setTaxonomyPath(path => ({ ...path, level2: null, level3: null }))}>{taxonomyPath.level1}</button></>}{taxonomyPath.level2 && <><span>/</span><button onClick={() => setTaxonomyPath(path => ({ ...path, level3: null }))}>{taxonomyPath.level2}</button></>}</nav>;
  const mapNavigation = view === 'mapped' && <nav className="sno-map-navigation" aria-label="SNO 地图层级导航">{taxonomyPath.level1 && <button className="sno-map-back" onClick={() => setTaxonomyPath(path => path.level2 ? { ...path, level2: null, level3: null } : { level1: null, level2: null, level3: null })}>← 返回上一级</button>}<button onClick={() => setTaxonomyPath({ level1: null, level2: null, level3: null })}>职业图鉴</button>{taxonomyPath.level1 && <><span>/</span><button onClick={() => setTaxonomyPath({ level1: taxonomyPath.level1, level2: null, level3: null })}>{taxonomyPath.level1}</button></>}{taxonomyPath.level2 && <><span>/</span><span aria-current="page">{taxonomyPath.level2}</span></>}</nav>;
  const globalNavigation = view === 'mapped' && <nav className="breadcrumbs sno-global-breadcrumbs" aria-label="SNO 地图层级"><button onClick={() => setTaxonomyPath({ level1: null, level2: null, level3: null })} aria-current={!taxonomyPath.level1 ? 'page' : undefined}>职业图鉴</button>{taxonomyPath.level1 && <><span>/</span><button onClick={() => setTaxonomyPath({ level1: taxonomyPath.level1, level2: null, level3: null })} aria-current={!taxonomyPath.level2 ? 'page' : undefined}>{taxonomyPath.level1}</button></>}{taxonomyPath.level2 && <><span>/</span><span aria-current="page">{taxonomyPath.level2}</span></>}</nav>;
  if (categoryDetail) {
    const categoryRows = categoryDetail.occupations || data.groups.mapped.filter(row => row.categoryId === categoryDetail.categoryId);
    const { level_1: level1, level_3: level3 } = categoryDetail.category;
    const level2 = displayLevel2(categoryDetail.category);
    const rootHolding = categoryDetail.category.is_holding_group && !level2;
    const nestedHolding = categoryDetail.category.is_holding_group && level2 === level3;
    const returnToParent = () => {
      setCategoryDetail(null);
      setTaxonomyPath({ level1, level2: categoryDetail.category.is_level2_aggregate ? null : level2 || null, level3: null });
    };
    return <section className="sno-explorer"><nav className="breadcrumbs sno-detail-breadcrumbs" aria-label="SNO 分类详情"><button className="sno-back-button" onClick={returnToParent}>← 返回上一级</button><button onClick={() => { setCategoryDetail(null); setTaxonomyPath({ level1: null, level2: null, level3: null }); }}>职业图鉴</button>{!rootHolding && <><span>/</span><button onClick={() => { setCategoryDetail(null); setTaxonomyPath({ level1, level2: null, level3: null }); }}>{level1}</button></>}{level2 && !categoryDetail.category.is_other && <><span>/</span><button onClick={returnToParent}>{level2}</button></>}{!nestedHolding && !categoryDetail.category.is_direct_level2 && <><span>/</span><span aria-current="page">{level3}</span></>}</nav><SnoCategoryMarket category={categoryDetail.category} occupations={categoryRows} /></section>;
  }
  if (detailOccupation) {
    const category = detailOccupation.category;
    const level2 = category ? displayLevel2(category) : null;
    const returnToParent = () => {
      setDetailOccupation(null);
      if (category) {
        setView('mapped');
        setTaxonomyPath({ level1: category.level_1 || null, level2: level2 || null, level3: null });
      }
    };
    return <section className="sno-explorer"><nav className="breadcrumbs sno-detail-breadcrumbs" aria-label="SNO 详情层级"><button className="sno-back-button" onClick={returnToParent}>← 返回上一级</button><button onClick={() => { setDetailOccupation(null); setTaxonomyPath({ level1: null, level2: null, level3: null }); }}>职业图鉴</button>{category && <><span>/</span><button onClick={() => { setDetailOccupation(null); setTaxonomyPath({ level1: category.level_1, level2: null, level3: null }); }}>{category.level_1}</button>{level2 && <><span>/</span><button onClick={returnToParent}>{level2}</button></>}{category.level_3 && !category.is_direct_level2 && <><span>/</span><button onClick={returnToParent}>{category.level_3}</button></>}</>}<span>/</span><span aria-current="page">{detailOccupation.label}</span></nav><SnoOccupationDetail occupation={detailOccupation} /></section>;
  }
  return <section className="sno-explorer">{mapStage && taxonomyPath.level1 && globalNavigation}
    {mapStage ? <section className={`map-scene industry field-layout sno-map-scene${taxonomyPath.level1 ? ' sno-map-scene--drilled' : ''}`}><div className="market-heading field-copy">{mapNavigation}<h1 className={taxonomyPath.level2 ? 'sno-stage-title sno-stage-title--level3' : taxonomyPath.level1 ? 'sno-stage-title sno-stage-title--level2' : 'sno-stage-title'}>{stageHeading}</h1><p className="muted"><strong>{mapStage.items.length}</strong> 个{mapStage.title}</p>{controls}</div><div className="field-stage"><BubbleMap key={`${taxonomyPath.level1 || 'root'}-${taxonomyPath.level2 || 'root'}`} items={mapStage.items} label={mapStage.title} subject={mapStage.title} countUnit="岗位" metricLabel="面积 = 关联岗位数" variant="industry" transition showInspector={false} showLegend={false} showZoomControls={false} onSelect={id => { const holding = data.groups.holdingById.get(id); const level1Holding = data.groups.level1HoldingById.get(id); const other = data.groups.otherById.get(id); const holdingHasChildren = holding && data.groups.level1Holding.some(bucket => bucket.parent_id === holding.label); if (!taxonomyPath.level1 && holdingHasChildren) setTaxonomyPath({ level1: holding.label, level2: null, level3: null }); else if (!taxonomyPath.level1 && holding) setCategoryDetail({ categoryId: holding.bucket_id, occupations: holding.occupations, category: { level_1: holding.label, level_2: null, level_3: holding.label, is_holding_group: true } }); else if (!taxonomyPath.level1) setTaxonomyPath({ level1: id, level2: null, level3: null }); else if (!taxonomyPath.level2 && level1Holding) setCategoryDetail({ categoryId: level1Holding.bucket_id, occupations: level1Holding.occupations, category: { level_1: level1Holding.level_1, level_2: level1Holding.label, level_3: level1Holding.label, is_holding_group: true } }); else if (!taxonomyPath.level2 && other) setCategoryDetail({ categoryId: other.bucket_id, occupations: other.occupations, category: { level_1: other.level_1, level_2: '其他岗位', level_3: '其他岗位', is_other: true } }); else if (!taxonomyPath.level2) setTaxonomyPath(path => ({ ...path, level2: id, level3: null })); else if (other) setCategoryDetail({ categoryId: other.bucket_id, occupations: other.occupations, category: { level_1: other.level_1, level_2: other.level_2, display_level_2: other.display_level_2, level_3: '其他岗位', is_other: true } }); else { const category = pathRows.find(row => row.categoryId === id)?.category; if (category) setCategoryDetail({ categoryId: id, category }); } }} /></div>{!taxonomyPath.level1 && <div className="sno-daily-corner"><button className="sno-daily-entry" onClick={onViewDaily}>每日新增岗位 <span aria-hidden="true">→</span></button></div>}</section> : <><div className="market-heading sno-role-list-heading"><h1>{listTitle}</h1><p className="muted"><strong>{visibleJobCount.toLocaleString()}</strong> 个关联岗位</p><p className="sno-list-description">{listDescription}</p></div>{controls}{breadcrumbs}<div className="sno-list-screen"><ul className="sno-occupation-list">{pathRows.slice(0, 500).map(row => <li key={row.id}><button onClick={() => setDetailOccupation(row)}><strong>{row.label}</strong><span>{row.placement}{row.category?.level_3 ? ` · ${row.category.level_3}` : ''}</span></button></li>)}</ul>{pathRows.length > 500 && <p className="muted">为保持浏览性能仅显示前 500 项。</p>}</div></>}
  </section>;
}
