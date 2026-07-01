import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import './HistorySidebar.css';

/* ── history data (mirrors Report mock, grouped chronologically) ── */
const HISTORY = [
  {
    id: 'run-001', repo: 'AnshPandey18/4o4PR',
    bug: 'Issue #404: pytest failure in auth module',
    status: 'success', duration: '14.5s', pr: 73,
    branch: 'fix/auth-jwt-expiry', severity: 'High',
    passed: 3, total: 3,
    ts: '2026-07-01T09:42:11Z',
  },
  {
    id: 'run-002', repo: 'pallets/flask',
    bug: 'Issue #201: connection timeout in HTTP pool',
    status: 'success', duration: '10.2s', pr: 1482,
    branch: 'fix/http-pool-timeout', severity: 'Medium',
    passed: 8, total: 8,
    ts: '2026-07-01T08:15:03Z',
  },
  {
    id: 'run-003', repo: 'psf/requests',
    bug: 'Issue #89: memory leak in WebSocket pool',
    status: 'fail', duration: '22.1s', pr: null,
    branch: 'fix/ws-pool-leak', severity: 'High',
    passed: 3, total: 5,
    ts: '2026-06-30T22:08:44Z',
  },
  {
    id: 'run-004', repo: 'encode/httpx',
    bug: 'Issue #112: CORS header mismatch',
    status: 'success', duration: '8.7s', pr: 541,
    branch: 'fix/cors-header', severity: 'Low',
    passed: 12, total: 12,
    ts: '2026-06-30T17:33:27Z',
  },
  {
    id: 'run-005', repo: 'fastapi/fastapi',
    bug: 'Issue #303: Database connection leak',
    status: 'success', duration: '18.3s', pr: 2210,
    branch: 'fix/db-conn-leak', severity: 'Medium',
    passed: 20, total: 20,
    ts: '2026-06-29T14:20:55Z',
  },
  {
    id: 'run-006', repo: 'django/django',
    bug: 'Issue #1102: ORM query escaping regression',
    status: 'fail', duration: '31.4s', pr: null,
    branch: 'fix/orm-escape', severity: 'High',
    passed: 14, total: 20,
    ts: '2026-06-28T11:05:00Z',
  },
  {
    id: 'run-007', repo: 'AnshPandey18/4o4PR',
    bug: 'Issue #381: rate-limit bypass on /api/token',
    status: 'success', duration: '9.1s', pr: 68,
    branch: 'fix/rate-limit', severity: 'Medium',
    passed: 5, total: 5,
    ts: '2026-06-27T16:44:22Z',
  },
];

/* ── helpers ── */
function relTime(iso) {
  const d = Date.now() - new Date(iso).getTime();
  const m = Math.floor(d / 60000);
  if (m < 1)  return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function dateLabel(iso) {
  const d = new Date(iso);
  const today = new Date();
  const yest  = new Date(); yest.setDate(today.getDate() - 1);
  if (d.toDateString() === today.toDateString()) return 'Today';
  if (d.toDateString() === yest.toDateString())  return 'Yesterday';
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function groupByDate(runs) {
  const groups = {};
  runs.forEach(r => {
    const lbl = dateLabel(r.ts);
    if (!groups[lbl]) groups[lbl] = [];
    groups[lbl].push(r);
  });
  return Object.entries(groups); // [[label, runs[]], ...]
}

/* ── severity dot colour ── */
const SEV_COLOR = { High: '#e6714f', Medium: '#ffb764', Low: '#27c93f' };

/* ── expandable run row ── */
function RunRow({ run, index, isOpen, onClick }) {
  return (
    <div
      className={`hs-run ${isOpen ? 'hs-run-open' : ''} hs-run-${run.status}`}
      style={{ '--delay': `${index * 45}ms` }}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={e => e.key === 'Enter' && onClick()}
    >
      {/* accent line */}
      <div className={`hs-run-line hs-line-${run.status}`} />

      <div className="hs-run-main">
        {/* status orb */}
        <div className={`hs-orb hs-orb-${run.status}`} />

        <div className="hs-run-info">
          <span className="hs-run-repo">{run.repo}</span>
          <span className="hs-run-bug">{run.bug}</span>
          <div className="hs-run-meta">
            <span className="hs-run-time">{relTime(run.ts)}</span>
            <span className="hs-run-dur">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
              </svg>
              {run.duration}
            </span>
          </div>
        </div>

        <div className="hs-run-right">
          <span className={`hs-badge hs-badge-${run.status}`}>
            {run.status === 'success' ? 'Pass' : 'Fail'}
          </span>
          <svg
            className={`hs-chevron ${isOpen ? 'hs-chevron-open' : ''}`}
            width="12" height="12" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
          >
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </div>
      </div>

      {/* expanded detail */}
      <div className={`hs-run-detail ${isOpen ? 'hs-detail-open' : ''}`}>
        <div className="hs-detail-grid">
          <div className="hs-detail-row">
            <span className="hs-detail-lbl">Branch</span>
            <span className="hs-detail-val hs-mono">⎇ {run.branch}</span>
          </div>
          <div className="hs-detail-row">
            <span className="hs-detail-lbl">Tests</span>
            <span className="hs-detail-val">
              <span style={{ color: 'var(--color-vivid-mint)' }}>{run.passed}</span>
              <span style={{ color: 'var(--color-fog)' }}> / {run.total}</span>
            </span>
          </div>
          <div className="hs-detail-row">
            <span className="hs-detail-lbl">Severity</span>
            <span className="hs-detail-val" style={{ color: SEV_COLOR[run.severity] }}>
              ● {run.severity}
            </span>
          </div>
          {run.pr && (
            <div className="hs-detail-row">
              <span className="hs-detail-lbl">PR</span>
              <a
                href={`https://github.com/${run.repo}/pull/${run.pr}`}
                target="_blank" rel="noopener noreferrer"
                className="hs-detail-link"
                onClick={e => e.stopPropagation()}
              >
                #{run.pr} ↗
              </a>
            </div>
          )}
        </div>
        {/* test bar */}
        <div className="hs-mini-bar-track">
          <div
            className={`hs-mini-bar-fill hs-bar-${run.status}`}
            style={{ width: `${Math.round((run.passed / run.total) * 100)}%` }}
          />
        </div>
      </div>
    </div>
  );
}

/* ── MAIN COMPONENT ── */
export default function HistorySidebar() {
  const navigate = useNavigate();
  const [open,     setOpen]     = useState(false);
  const [openRun,  setOpenRun]  = useState(null);
  const [filter,   setFilter]   = useState('all');
  const [query,    setQuery]    = useState('');
  const [entered,  setEntered]  = useState(false);
  const panelRef = useRef(null);
  const inputRef = useRef(null);

  /* animate items in when panel opens */
  useEffect(() => {
    if (open) { setTimeout(() => setEntered(true), 60); }
    else       { setEntered(false); }
  }, [open]);

  /* close on Escape */
  useEffect(() => {
    const fn = e => { if (e.key === 'Escape' && open) setOpen(false); };
    window.addEventListener('keydown', fn);
    return () => window.removeEventListener('keydown', fn);
  }, [open]);

  /* focus search when opened */
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 350);
  }, [open]);

  /* filtered + searched runs */
  const filtered = HISTORY.filter(r => {
    const matchFilter = filter === 'all' || r.status === filter;
    const q = query.trim().toLowerCase();
    const matchQ = !q || r.repo.toLowerCase().includes(q) || r.bug.toLowerCase().includes(q);
    return matchFilter && matchQ;
  });

  const groups = groupByDate(filtered);
  const successCount = HISTORY.filter(r => r.status === 'success').length;

  return (
    <>
      {/* ── TOGGLE BUTTON ── */}
      <button
        className={`hs-toggle ${open ? 'hs-toggle-open' : ''}`}
        onClick={() => setOpen(o => !o)}
        aria-label="Toggle run history"
        title="Run History"
      >
        <div className="hs-toggle-inner">
          {open ? (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/>
            </svg>
          )}
          {!open && <span className="hs-toggle-label">History</span>}
          {!open && (
            <span className="hs-toggle-count">{HISTORY.length}</span>
          )}
        </div>
      </button>

      {/* ── BACKDROP ── */}
      {open && <div className="hs-backdrop" onClick={() => setOpen(false)} />}

      {/* ── PANEL ── */}
      <aside ref={panelRef} className={`hs-panel ${open ? 'hs-panel-open' : ''}`}>

        {/* gradient top strip */}
        <div className="hs-panel-strip" />

        {/* header */}
        <div className="hs-panel-head">
          <div className="hs-panel-head-left">
            <span className="hs-eyebrow">Run History</span>
            <div className="hs-head-row">
              <h2 className="hs-panel-title">Activity</h2>
              <div className="hs-head-stats">
                <span className="hs-head-stat hs-stat-total">{HISTORY.length} runs</span>
                <span className="hs-head-stat hs-stat-pass">{successCount} passed</span>
              </div>
            </div>
          </div>
        </div>

        {/* search */}
        <div className="hs-search-wrap">
          <svg className="hs-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input
            ref={inputRef}
            className="hs-search"
            placeholder="Search repo or issue…"
            value={query}
            onChange={e => setQuery(e.target.value)}
          />
          {query && (
            <button className="hs-search-clear" onClick={() => setQuery('')} aria-label="Clear search">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          )}
        </div>

        {/* filter tabs */}
        <div className="hs-filters">
          {[
            { key: 'all',     label: 'All',    count: HISTORY.length },
            { key: 'success', label: 'Passed', count: HISTORY.filter(r => r.status === 'success').length },
            { key: 'fail',    label: 'Failed', count: HISTORY.filter(r => r.status === 'fail').length },
          ].map(f => (
            <button
              key={f.key}
              className={`hs-ftab ${filter === f.key ? 'hs-ftab-on' : ''}`}
              onClick={() => setFilter(f.key)}
            >
              {f.label}
              <span className="hs-ftab-n">{f.count}</span>
            </button>
          ))}
        </div>

        {/* divider */}
        <div className="hs-divider" />

        {/* run list */}
        <div className={`hs-list ${entered ? 'hs-list-entered' : ''}`}>
          {groups.length === 0 && (
            <div className="hs-empty">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--color-slate)', marginBottom: 8 }}>
                <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
              </svg>
              No runs match your search.
            </div>
          )}

          {groups.map(([label, runs]) => (
            <div key={label} className="hs-group">
              <span className="hs-group-label">{label}</span>
              {runs.map((run, i) => (
                <RunRow
                  key={run.id}
                  run={run}
                  index={i}
                  isOpen={openRun === run.id}
                  onClick={() => setOpenRun(openRun === run.id ? null : run.id)}
                />
              ))}
            </div>
          ))}
        </div>

        {/* footer */}
        <div className="hs-panel-footer">
          <button className="hs-footer-btn" onClick={() => { navigate('/report'); setOpen(false); }}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/>
              <polyline points="10 9 9 9 8 9"/>
            </svg>
            Full Report
          </button>
          <button className="hs-footer-btn hs-footer-primary" onClick={() => { navigate('/run'); setOpen(false); }}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="5 3 19 12 5 21 5 3"/>
            </svg>
            New Run
          </button>
        </div>
      </aside>
    </>
  );
}
