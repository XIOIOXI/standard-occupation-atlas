import React from 'react';
import SnoExplorer from './components/SnoExplorer.jsx';
import UpdateNotifications from './components/UpdateNotifications.jsx';
import DailyUpdatesView from './components/DailyUpdatesView.jsx';
import RecruitmentUpdateAdmin from './components/RecruitmentUpdateAdmin.jsx';
import JobSearch from './components/JobSearch.jsx';
import './Navigation.css';
import { useBrowseState } from './hooks/useBrowseState.js';

export default function App() {
  const [page, setPage] = useBrowseState('page', 'atlas', value => ['atlas', 'search', 'daily', 'admin'].includes(value));
  const showDailyUpdates = page === 'daily';
  const showAdmin = page === 'admin';
  const showJobSearch = page === 'search';
  const setShowDailyUpdates = value => setPage(current => value ? 'daily' : current === 'daily' ? 'atlas' : current);
  const setShowAdmin = value => setPage(current => value ? 'admin' : current === 'admin' ? 'atlas' : current);
  const setShowJobSearch = value => setPage(current => value ? 'search' : current === 'search' ? 'atlas' : current);
  const [dataRevision, setDataRevision] = React.useState(0);
  return <>
    <header className="topbar topbar-drawers">
      <span aria-hidden="true" />
      <button className="nav-directory-title" onClick={() => { setShowDailyUpdates(false); setShowAdmin(false); setShowJobSearch(false); }}>标准职业目录</button>
      <button className="nav-menu-trigger" popoverTarget="update-menu" aria-label="打开功能菜单" title="功能菜单"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16" /></svg></button>
    </header>
    <nav id="update-menu" className="nav-drawer nav-drawer-right" popover="auto" aria-label="功能菜单"><header><h2>功能菜单</h2><button popoverTarget="update-menu" popoverTargetAction="hide">关闭</button></header><button className="nav-drawer-link" onClick={event => { event.currentTarget.closest('[popover]').hidePopover(); setShowJobSearch(true); setShowAdmin(false); setShowDailyUpdates(false); }}>岗位搜索</button><button className="nav-drawer-link" onClick={event => { event.currentTarget.closest('[popover]').hidePopover(); setShowAdmin(true); setShowJobSearch(false); setShowDailyUpdates(false); }}>动态更新</button></nav>
    <main className="market-main sno-main sno-market-page">
      {showAdmin ? <RecruitmentUpdateAdmin onClose={() => setShowAdmin(false)} onCompleted={() => setDataRevision(revision => revision + 1)} /> : showJobSearch ? <JobSearch key={`search-${dataRevision}`} onBack={() => setShowJobSearch(false)} /> : showDailyUpdates ? <DailyUpdatesView key={`daily-${dataRevision}`} onBack={() => setShowDailyUpdates(false)} /> : <SnoExplorer key={`explorer-${dataRevision}`} onViewDaily={() => setShowDailyUpdates(true)} />}
    </main>
    <UpdateNotifications key={`notification-${dataRevision}`} onViewDaily={() => { setShowAdmin(false); setShowJobSearch(false); setShowDailyUpdates(true); }} />
  </>;
}
