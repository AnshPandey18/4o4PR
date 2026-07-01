import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import './Report.css';

/* ─── DATA ──────────────────────────────────────────────────────────────── */
const MOCK_RUNS = [
  {
    id: 'run-001', repo: 'AnshPandey18/4o4PR',
    bug: 'Issue #404: pytest failure in auth module (test_jwt_validation)',
    status: 'success', branch: 'fix/auth-jwt-expiry', pr: 73,
    duration: '14.5s', testsTotal: 3, testsPassed: 3, testsFailed: 0,
    timestamp: '2026-07-01T09:42:11Z', severity: 'High',
    steps: [
      { name: 'Clone Repo',     status: 'pass',   ms: 1240 },
      { name: 'Detect Bug',     status: 'pass',   ms: 3100 },
      { name: 'Generate Patch', status: 'pass',   ms: 5830 },
      { name: 'Run Tests',      status: 'pass',   ms: 1420 },
      { name: 'Open PR',        status: 'pass',   ms: 980  },
    ],
    patch: `@@ -24,4 +24,5 @@\n @router.get("/api/v1/resource")\n+@login_required\n def get_resource():\n     return {"status": "success"}`,
  },
  {
    id: 'run-002', repo: 'pallets/flask',
    bug: 'Issue #201: connection timeout in HTTP pool management',
    status: 'success', branch: 'fix/http-pool-timeout', pr: 1482,
    duration: '10.2s', testsTotal: 8, testsPassed: 8, testsFailed: 0,
    timestamp: '2026-07-01T08:15:03Z', severity: 'Medium',
    steps: [
      { name: 'Clone Repo',     status: 'pass', ms: 980  },
      { name: 'Detect Bug',     status: 'pass', ms: 2400 },
      { name: 'Generate Patch', status: 'pass', ms: 4600 },
      { name: 'Run Tests',      status: 'pass', ms: 1180 },
      { name: 'Open PR',        status: 'pass', ms: 740  },
    ],
    patch: `@@ -112,6 +112,7 @@\n- socket.settimeout(None)\n+ socket.settimeout(30)`,
  },
  {
    id: 'run-003', repo: 'psf/requests',
    bug: 'Issue #89: memory leak in WebSocket connection pool',
    status: 'fail', branch: 'fix/ws-pool-leak', pr: null,
    duration: '22.1s', testsTotal: 5, testsPassed: 3, testsFailed: 2,
    timestamp: '2026-06-30T22:08:44Z', severity: 'High',
    steps: [
      { name: 'Clone Repo',     status: 'pass',   ms: 1540 },
      { name: 'Detect Bug',     status: 'pass',   ms: 3900 },
      { name: 'Generate Patch', status: 'pass',   ms: 6200 },
      { name: 'Run Tests',      status: 'fail',   ms: 7900 },
      { name: 'Open PR',        status: 'queued', ms: 0    },
    ],
    patch: `@@ -88,3 +88,6 @@\n def close_pool():\n+    for sock in _pool:\n+        sock.close()\n+    _pool.clear()`,
  },
  {
    id: 'run-004', repo: 'encode/httpx',
    bug: 'Issue #112: CORS header mismatch on endpoints',
    status: 'success', branch: 'fix/cors-header', pr: 541,
    duration: '8.7s', testsTotal: 12, testsPassed: 12, testsFailed: 0,
    timestamp: '2026-06-30T17:33:27Z', severity: 'Low',
    steps: [
      { name: 'Clone Repo',     status: 'pass', ms: 810  },
      { name: 'Detect Bug',     status: 'pass', ms: 2100 },
      { name: 'Generate Patch', status: 'pass', ms: 3450 },
      { name: 'Run Tests',      status: 'pass', ms: 1560 },
      { name: 'Open PR',        status: 'pass', ms: 620  },
    ],
    patch: `@@ -56,2 +56,3 @@\n CORS_ORIGINS = []\n+CORS_ORIGINS.append("https://*.yourdomain.com")`,
  },
  {
    id: 'run-005', repo: 'fastapi/fastapi',
    bug: 'Issue #303: Database connection leak during async tests',
    status: 'success', branch: 'fix/db-conn-leak', pr: 2210,
    duration: '18.3s', testsTotal: 20, testsPassed: 20, testsFailed: 0,
    timestamp: '2026-06-29T14:20:55Z', severity: 'Medium',
    steps: [
      { name: 'Clone Repo',     status: 'pass', ms: 1100 },
      { name: 'Detect Bug',     status: 'pass', ms: 3300 },
      { name: 'Generate Patch', status: 'pass', ms: 7200 },
      { name: 'Run Tests',      status: 'pass', ms: 4800 },
      { name: 'Open PR',        status: 'pass', ms: 890  },
    ],
    patch: `@@ -44,4 +44,6 @@\n async def teardown():\n+    await db.close()\n+    await engine.dispose()`,
  },
];

const STATS = [
  { label: 'Total Runs',   value: 5,    suffix: '',  color: 'var(--color-electric-signal)', bg: 'rgba(0,136,255,0.08)',   border: 'rgba(0,136,255,0.2)',   icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> },
  { label: 'Success Rate', value: 80,   suffix: '%', color: 'var(--color-vivid-mint)',      bg: 'rgba(39,201,63,0.08)',   border: 'rgba(39,201,63,0.2)',   icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg> },
  { label: 'PRs Opened',   value: 4,    suffix: '',  color: 'var(--color-lavender-mist)',   bg: 'rgba(184,85,231,0.08)',  border: 'rgba(184,85,231,0.2)',  icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M13 6h3a2 2 0 0 1 2 2v7"/><line x1="6" y1="9" x2="6" y2="21"/></svg> },
  { label: 'Avg Duration', value: 14.8, suffix: 's', color: 'var(--color-amber-glow)',      bg: 'rgba(255,183,100,0.08)', border: 'rgba(255,183,100,0.2)', icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> },
];

/* ─── HELPERS ── */
function relTime(iso) {
  const d = Date.now() - new Date(iso).getTime();
  const m = Math.floor(d / 60000);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function useInView(threshold = 0.15) {
  const ref = useRef(null);
  const [vis, setVis] = useState(false);
  useEffect(() => {
    const el = ref.current; if (!el) return;
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) setVis(true); }, { threshold });
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);
  return [ref, vis];
}

/* ─── ANIMATED COUNTER ── */
function Counter({ to, suffix = '', trigger }) {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (!trigger) return;
    let s = 0;
    const inc = to / (1200 / 16);
    const t = setInterval(() => {
      s += inc;
      if (s >= to) { setV(to); clearInterval(t); }
      else setV(parseFloat(s.toFixed(1)));
    }, 16);
    return () => clearInterval(t);
  }, [trigger, to]);
  const disp = Number.isInteger(to) ? Math.round(v) : v.toFixed(1);
  return <span>{trigger ? `${disp}${suffix}` : '—'}</span>;
}

/* ─── RADIAL RING ── */
function Ring({ pct, color, size = 72 }) {
  const r = (size - 10) / 2;
  const circ = 2 * Math.PI * r;
  const [off, setOff] = useState(circ);
  useEffect(() => { const t = setTimeout(() => setOff(circ - (pct / 100) * circ), 400); return () => clearTimeout(t); }, [pct, circ]);
  return (
    <svg width={size} height={size}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="5" />
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth="5"
        strokeLinecap="round" strokeDasharray={circ} strokeDashoffset={off}
        transform={`rotate(-90 ${size/2} ${size/2})`}
        style={{ transition: 'stroke-dashoffset 1.3s cubic-bezier(0.16,1,0.3,1)', filter: `drop-shadow(0 0 6px ${color})` }} />
      <text x={size/2} y={size/2+5} textAnchor="middle" fill="white" fontSize="13" fontWeight="700" fontFamily="Inter,sans-serif">{pct}%</text>
    </svg>
  );
}

/* ─── MINI PIPELINE DOTS ── */
function PipelineDots({ steps }) {
  return (
    <div className="rp-dots">
      {steps.map((s, i) => (
        <div key={i} className="rp-dot-wrap" title={`${s.name} — ${s.ms > 0 ? s.ms+'ms' : 'skipped'}`}>
          <div className={`rp-dot rp-dot-${s.status}`} />
          {i < steps.length - 1 && <div className={`rp-dot-line ${s.status === 'pass' ? 'rp-line-pass' : 'rp-line-dim'}`} />}
        </div>
      ))}
    </div>
  );
}

/* ─── DIFF VIEWER ── */
function Diff({ patch }) {
  return (
    <div className="rp-diff">
      <div className="rp-diff-bar">
        <span className="rp-diff-label">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
          Generated diff
        </span>
      </div>
      <pre className="rp-diff-body">
        {patch.split('\n').map((ln, i) => {
          let cls = 'rp-dl';
          if (ln.startsWith('+') && !ln.startsWith('+++')) cls += ' rp-dl-add';
          else if (ln.startsWith('-') && !ln.startsWith('---')) cls += ' rp-dl-rem';
          else if (ln.startsWith('@@')) cls += ' rp-dl-meta';
          return <div key={i} className={cls}>{ln || ' '}</div>;
        })}
      </pre>
    </div>
  );
}

/* ─── DETAIL PANEL ── */
function DetailPanel({ run, onClose, onRunAgain }) {
  const passPct = Math.round((run.testsPassed / run.testsTotal) * 100);
  return (
    <>
      <div className="rp-backdrop" onClick={onClose} />
      <aside className="rp-panel">
        {/* top gradient strip */}
        <div className={`rp-panel-strip strip-${run.status}`} />

        {/* header */}
        <div className="rp-panel-head">
          <div className="rp-panel-head-left">
            <span className="rp-panel-id">{run.id}</span>
            <h2 className="rp-panel-repo">{run.repo}</h2>
          </div>
          <button className="rp-panel-close" onClick={onClose} aria-label="Close">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        {/* outcome hero */}
        <div className={`rp-outcome rp-outcome-${run.status}`}>
          <div className={`rp-outcome-orb orb-${run.status}`} />
          <div className="rp-outcome-text">
            <p className="rp-outcome-label">{run.status === 'success' ? '✓  Patch applied & PR opened' : '✗  Test validation failed'}</p>
            <p className="rp-outcome-sub">{run.duration} · {relTime(run.timestamp)}</p>
          </div>
          {run.pr && (
            <a href={`https://github.com/${run.repo}/pull/${run.pr}`} target="_blank" rel="noopener noreferrer"
               className="rp-pr-pill" onClick={e => e.stopPropagation()}>
              PR #{run.pr}
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="7" y1="17" x2="17" y2="7"/><polyline points="7 7 17 7 17 17"/></svg>
            </a>
          )}
        </div>

        {/* bug context */}
        <div className="rp-ps">
          <span className="rp-ps-label">Bug Context</span>
          <p className="rp-ps-bug">{run.bug}</p>
          <div className="rp-ps-chips">
            <span className={`rp-sev rp-sev-${run.severity.toLowerCase()}`}>{run.severity} severity</span>
            <span className="rp-chip-mono">⎇ {run.branch}</span>
          </div>
        </div>

        {/* step timeline */}
        <div className="rp-ps">
          <span className="rp-ps-label">Step Timeline</span>
          <div className="rp-timeline">
            {run.steps.map((step, i) => (
              <div key={i} className="rp-tl-row">
                <div className="rp-tl-left">
                  <div className={`rp-tl-dot tl-${step.status}`}>
                    {step.status === 'pass'   && <svg width="8" height="7" viewBox="0 0 10 8" fill="none"><path d="M1 4L3.5 6.5L9 1" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>}
                    {step.status === 'fail'   && <svg width="8" height="8" viewBox="0 0 10 10" fill="none"><line x1="2" y1="2" x2="8" y2="8" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/><line x1="8" y1="2" x2="2" y2="8" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>}
                    {step.status === 'queued' && <span className="rp-tl-dash">—</span>}
                  </div>
                  {i < run.steps.length - 1 && <div className={`rp-tl-line tl-line-${step.status === 'pass' ? 'pass' : 'dim'}`} />}
                </div>
                <div className="rp-tl-content">
                  <span className="rp-tl-name">{step.name}</span>
                  {step.ms > 0 && <span className="rp-tl-ms">{step.ms}ms</span>}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* test results */}
        <div className="rp-ps">
          <span className="rp-ps-label">Test Results</span>
          <div className="rp-test-track">
            <div className="rp-test-fill rp-fill-pass" style={{ width: `${passPct}%` }} />
            {run.testsFailed > 0 && <div className="rp-test-fill rp-fill-fail" style={{ width: `${Math.round((run.testsFailed/run.testsTotal)*100)}%` }} />}
          </div>
          <div className="rp-test-legend">
            <span className="rp-leg-pass">✓ {run.testsPassed} passed</span>
            {run.testsFailed > 0 && <span className="rp-leg-fail">✗ {run.testsFailed} failed</span>}
            <span className="rp-leg-total">{run.testsTotal} total</span>
          </div>
        </div>

        {/* diff */}
        <div className="rp-ps"><span className="rp-ps-label">Generated Patch</span><Diff patch={run.patch} /></div>

        {/* actions */}
        <div className="rp-panel-actions">
          <button className="rp-btn-ghost" onClick={onClose}>Close</button>
          <button className="rp-btn-primary" onClick={onRunAgain}>Run Again</button>
        </div>
      </aside>
    </>
  );
}

/* ─── MAIN ── */
export default function Report() {
  const navigate = useNavigate();
  const pageRef  = useRef(null);
  const [selectedRun,  setSelectedRun]  = useState(null);
  const [filter,       setFilter]       = useState('all');
  const [visible,      setVisible]      = useState([]);
  const [statsRef, statsVis] = useInView(0.2);

  /* parallax orbs */
  useEffect(() => {
    const el = pageRef.current; if (!el) return;
    const fn = (e) => {
      const cx = window.innerWidth/2, cy = window.innerHeight/2;
      el.style.setProperty('--ox', `${((e.clientX-cx)/cx)*18}px`);
      el.style.setProperty('--oy', `${((e.clientY-cy)/cy)*12}px`);
    };
    window.addEventListener('mousemove', fn);
    return () => window.removeEventListener('mousemove', fn);
  }, []);

  /* stagger cards */
  useEffect(() => {
    const t = setTimeout(() => {
      MOCK_RUNS.forEach((_, i) => setTimeout(() => setVisible(p => [...p, i]), i * 70));
    }, 150);
    return () => clearTimeout(t);
  }, []);

  /* escape key */
  useEffect(() => {
    const fn = e => { if (e.key === 'Escape') setSelectedRun(null); };
    window.addEventListener('keydown', fn);
    return () => window.removeEventListener('keydown', fn);
  }, []);

  const filtered = MOCK_RUNS.filter(r => filter === 'all' || r.status === filter);
  const successRate = Math.round((MOCK_RUNS.filter(r => r.status === 'success').length / MOCK_RUNS.length) * 100);

  return (
    <div className="rp-page" ref={pageRef}>
      {/* ambient orbs */}
      <div className="rp-orb rp-orb-1" /><div className="rp-orb rp-orb-2" /><div className="rp-orb rp-orb-3" />

      <div className="rp-inner page-wrapper">

        {/* ── PAGE HEADER ── */}
        <div className="rp-header">
          <div className="rp-header-left">
            <span className="rp-eyebrow">Analytics</span>
            <h1 className="rp-title">Run Reports</h1>
            <p className="rp-subtitle">Historical view of every autonomic patch attempt — timestamps, outcomes, diffs &amp; test results.</p>
          </div>
          <button className="rp-btn-primary rp-new-btn" onClick={() => navigate('/run')}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            New Run
          </button>
        </div>

        {/* ── STATS ── */}
        <div ref={statsRef} className={`rp-stats ${statsVis ? 'rp-vis' : ''}`}>
          {STATS.map((s, i) => (
            <div key={s.label} className="rp-stat-card" style={{ '--i': i }}>
              <div className="rp-stat-card-glow" style={{ background: `radial-gradient(circle at 30% 30%, ${s.bg.replace('0.08','0.5')} 0%, transparent 70%)` }} />
              <div className="rp-stat-icon" style={{ background: s.bg, border: `1px solid ${s.border}`, color: s.color }}>{s.icon}</div>
              <div className="rp-stat-text">
                <span className="rp-stat-val" style={{ color: s.color }}>
                  <Counter to={s.value} suffix={s.suffix} trigger={statsVis} />
                </span>
                <span className="rp-stat-lbl">{s.label}</span>
              </div>
            </div>
          ))}
          {/* radial pass-rate */}
          <div className="rp-stat-card rp-stat-ring" style={{ '--i': 4 }}>
            <div className="rp-stat-card-glow" style={{ background: 'radial-gradient(circle at 50% 50%, rgba(39,201,63,0.2) 0%, transparent 70%)' }} />
            {statsVis && <Ring pct={successRate} color="var(--color-vivid-mint)" size={72} />}
            <span className="rp-stat-lbl" style={{ marginTop: 4 }}>Pass Rate</span>
          </div>
        </div>

        {/* ── FILTER BAR ── */}
        <div className="rp-filter-bar">
          {[
            { key: 'all',     label: 'All Runs', color: 'var(--color-ash)' },
            { key: 'success', label: 'Passed',   color: 'var(--color-vivid-mint)' },
            { key: 'fail',    label: 'Failed',   color: 'var(--color-ember)' },
          ].map(f => (
            <button key={f.key} className={`rp-ftab ${filter === f.key ? 'rp-ftab-on' : ''}`} onClick={() => setFilter(f.key)}>
              <span className="rp-ftab-dot" style={{ background: f.color, boxShadow: filter === f.key ? `0 0 6px ${f.color}` : 'none' }} />
              {f.label}
              <span className="rp-ftab-count">{f.key === 'all' ? MOCK_RUNS.length : MOCK_RUNS.filter(r => r.status === f.key).length}</span>
            </button>
          ))}
        </div>

        {/* ── RUN LIST ── */}
        <div className="rp-list">
          {filtered.length === 0 && <div className="rp-empty">No runs match this filter.</div>}
          {filtered.map((run) => {
            const idx = MOCK_RUNS.indexOf(run);
            const isVis = visible.includes(idx);
            return (
              <div key={run.id}
                className={`rp-card ${isVis ? 'rp-card-in' : ''} rp-card-${run.status}`}
                onClick={() => setSelectedRun(run)} role="button" tabIndex={0}
                onKeyDown={e => e.key === 'Enter' && setSelectedRun(run)}
              >
                <div className={`rp-card-accent accent-${run.status}`} />
                <div className="rp-card-hover-glow" />
                <div className="rp-card-body">
                  {/* left */}
                  <div className="rp-card-left">
                    <div className="rp-card-top-row">
                      <span className="rp-card-repo">{run.repo}</span>
                      <span className={`rp-sev rp-sev-${run.severity.toLowerCase()}`}>{run.severity}</span>
                    </div>
                    <p className="rp-card-bug">{run.bug}</p>
                    <div className="rp-card-meta">
                      <span className="rp-card-id">{run.id}</span>
                      <span className="rp-card-time">{relTime(run.timestamp)}</span>
                    </div>
                  </div>
                  {/* center */}
                  <div className="rp-card-center">
                    <PipelineDots steps={run.steps} />
                    <span className="rp-card-dur">
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                      {run.duration}
                    </span>
                  </div>
                  {/* right */}
                  <div className="rp-card-right">
                    <div className="rp-card-tests">
                      <span className="rp-t-pass">{run.testsPassed} passed</span>
                      {run.testsFailed > 0 && <span className="rp-t-fail">{run.testsFailed} failed</span>}
                      <span className="rp-t-total">/ {run.testsTotal}</span>
                    </div>
                    <div className={`rp-badge rp-badge-${run.status}`}>
                      <span className={`rp-badge-dot ${run.status === 'fail' ? 'rp-blink' : ''}`} />
                      {run.status === 'success' ? 'Passed' : 'Failed'}
                    </div>
                    <span className="rp-card-arrow">→</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

      </div>

      {/* ── DETAIL PANEL ── */}
      {selectedRun && (
        <DetailPanel
          run={selectedRun}
          onClose={() => setSelectedRun(null)}
          onRunAgain={() => navigate('/run')}
        />
      )}
    </div>
  );
}
