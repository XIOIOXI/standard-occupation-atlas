import React from 'react';

export default function PageControls({ page, pageCount, onPageChange, label = '分页' }) {
  if (pageCount <= 1) return null;
  const jump = value => {
    const requested = Number.parseInt(value, 10);
    if (!Number.isFinite(requested)) return;
    onPageChange(Math.min(pageCount - 1, Math.max(0, requested - 1)));
  };
  return <nav className="page-controls" aria-label={label}>
    <button disabled={page === 0} onClick={() => onPageChange(page - 1)}>上一页</button>
    <span>{page + 1} / {pageCount}</span>
    <label>跳至 <input key={page} type="number" min="1" max={pageCount} defaultValue={page + 1} onBlur={event => jump(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') { jump(event.currentTarget.value); event.currentTarget.blur(); } }} aria-label={`跳至第几页，共 ${pageCount} 页`} /> 页</label>
    <button disabled={page === pageCount - 1} onClick={() => onPageChange(page + 1)}>下一页</button>
  </nav>;
}
