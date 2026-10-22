import React, { useEffect, useState } from 'react';
import './RecruitmentUpdateAdmin.css';

const API = '/api/recruitment-updates';

export default function RecruitmentUpdateAdmin({ onCompleted, onClose }) {
  const [file, setFile] = useState(null);
  const [mode, setMode] = useState('cached');
  const [budget, setBudget] = useState('0.20');
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const submitLock = React.useRef(false);

  useEffect(() => {
    if (!job || !['queued', 'running'].includes(job.status)) return undefined;
    const timer = window.setTimeout(async () => {
      try {
        const response = await fetch(`${API}/${job.job_id}`);
        const next = await response.json();
        if (!response.ok) throw new Error(next.error?.message || '无法读取运行状态');
        setJob(next);
        if (next.status === 'completed') onCompleted();
      } catch (requestError) { setError(requestError.message); }
    }, 900);
    return () => window.clearTimeout(timer);
  }, [job, onCompleted]);

  async function submit(event) {
    event.preventDefault();
    if (!file || submitLock.current || job?.status === 'running' || job?.status === 'queued') return;
    submitLock.current = true;
    setSubmitting(true);
    setError(null);
    const body = new FormData();
    body.append('file', file);
    body.append('mapping_mode', mode);
    body.append('budget_usd', budget);
    try {
      const response = await fetch(API, { method: 'POST', body });
      const next = await response.json();
      if (!response.ok) throw new Error(next.error?.message || '无法启动更新');
      setJob(next);
    } catch (requestError) { setError(requestError.message); }
    finally { submitLock.current = false; setSubmitting(false); }
  }

  const counts = job?.result?.counts;
  const traces = job?.result?.items?.filter(item => item.agent_trace?.length) || [];
  const busy = submitting || Boolean(job && ['queued', 'running'].includes(job.status));
  return <section className="update-admin update-admin-compact" aria-label="招聘更新管理">
    <nav className="breadcrumbs" aria-label="动态更新导航"><button onClick={onClose}>← 返回职业图鉴</button><span>/</span><span aria-current="page">动态更新</span></nav>
    <header><h1>动态更新</h1></header>
    <form onSubmit={submit}>
      <label className="update-admin-file">招聘文件<input type="file" accept=".csv,.xlsx" required onChange={event => setFile(event.target.files?.[0] || null)} disabled={busy} /><small>支持 CSV、XLSX</small></label>
      <label>分类方式<select value={mode} onChange={event => setMode(event.target.value)} disabled={busy}><option value="cached">本地比对</option><option value="model">本地比对 + DeepSeek 分类</option></select><small>{mode === 'model' ? '仅新增岗位的必要上下文和目录会发送给 DeepSeek。' : '不调用模型；无法复用分类的岗位保留待确认。'}</small></label>
      {mode === 'model' && <label>模型预算上限（美元）<input type="number" required min="0.01" max="1000" step="0.01" value={budget} onChange={event => setBudget(event.target.value)} disabled={busy} /></label>}
      <div className="update-admin-actions"><button className="update-admin-start" disabled={!file || busy}>{submitting ? '提交中…' : busy ? '处理中…' : '开始更新'}</button></div>
    </form>
    <details className="update-admin-help"><summary>处理规则与数据使用</summary><p>程序负责校验、增量比对、拆分、去重、导入与统计。分类证据不足的岗位保留待确认，不新增职业目录节点。</p><p>原文件不发送给模型；API Key 仅由本机后端保存和使用。DeepSeek 仅处理程序识别出的新增岗位。</p></details>
    {error && <p className="update-admin-error" role="alert">{error}</p>}
    {job && <section className="update-admin-result" aria-live="polite" aria-busy={busy}><strong>状态：{job.status === 'queued' ? '等待启动' : job.status === 'running' ? '处理中' : job.status === 'completed' ? '已完成' : '失败'}</strong><p>分类方式：{job.mapping_mode === 'model' ? '本地比对 + DeepSeek 分类' : '本地比对'}</p>{job.duplicate_submission && <p>相同文件正在处理中，已复用现有任务。</p>}{job.error && <p className="update-admin-error">{job.error}</p>}{counts && <dl className="update-admin-counts">{[['新增岗位', counts.new_atomic_jobs], ['涉及记录', counts.involved_recruitment_records], ['已归类', counts.classified], ['待确认', counts.pending], ['失败', counts.failed]].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value ?? 0}</dd></div>)}</dl>}{job.result?.message && <p>{job.result.message}</p>}{traces.length > 0 && <details className="update-admin-trace"><summary>处理明细（{counts?.agent_tool_calls || 0} 次）</summary>{traces.map(item => <section key={item.atomic_key}><strong>{item.title_unit}</strong><ol>{item.agent_trace.map((step, index) => <li key={`${item.atomic_key}-${index}`}><code>{step.action}</code>：{step.reason || '程序工具结果要求继续处理。'}</li>)}</ol></section>)}</details>}</section>}
  </section>;
}
