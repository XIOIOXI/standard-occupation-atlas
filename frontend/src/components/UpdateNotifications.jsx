import React, { useEffect, useMemo, useState } from 'react';

const DATA_ROOT = '/data/processed/record_role_classification_v1/full_drafts/sno_v31_reasonable_primary_v4_display/';
const CATALOGUE_URL = `${DATA_ROOT}update_batches.json`;
const STORAGE_PREFIX = 'sno-update-notification-read:';

function hasRead(batchId) {
  return window.localStorage.getItem(`${STORAGE_PREFIX}${batchId}`) === '1';
}

function markRead(batchId) {
  window.localStorage.setItem(`${STORAGE_PREFIX}${batchId}`, '1');
}

export default function UpdateNotifications({ onViewDaily }) {
  const [batches, setBatches] = useState([]);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    let active = true;
    fetch(CATALOGUE_URL).then(response => response.ok ? response.json() : Promise.reject(new Error(`updates ${response.status}`)))
      .then(payload => {
        const next = Array.isArray(payload.batches) ? payload.batches : [];
        if (!active) return;
        setBatches(next);
        setVisible(next.some(batch => !hasRead(batch.batch_id)));
      })
      .catch(() => { if (active) setBatches([]); });
    return () => { active = false; };
  }, []);

  const latestUnread = useMemo(() => batches.find(batch => !hasRead(batch.batch_id)) || null, [batches, visible]);
  const latest = batches[0] || null;
  const close = () => {
    if (latestUnread) markRead(latestUnread.batch_id);
    setVisible(false);
  };
  const view = batch => {
    markRead(batch.batch_id);
    setVisible(false);
    onViewDaily(batches);
  };
  if (!latest) return null;
  const counts = (latestUnread || latest).counts || {};
  return <>
    {visible && latestUnread && <aside className="update-toast" aria-live="polite" aria-label="新增岗位处理通知">
      <button className="update-toast-close" onClick={close} aria-label="关闭新增岗位通知">×</button>
      <p>招聘每日新增已更新</p>
      <h2>{counts.new_atomic_jobs || 0} 个新增岗位</h2>
      <small>涉及 {counts.involved_recruitment_records || 0} 条招聘记录 · 已归类 {counts.classified || 0} · 待确认 {counts.pending || 0}</small>
      <button className="update-toast-action" onClick={() => view(latestUnread)}>查看详情 →</button>
    </aside>}
  </>;
}
