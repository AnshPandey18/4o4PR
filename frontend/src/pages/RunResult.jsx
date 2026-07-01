import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import './RunResult.css';

/* ── mock data keyed per repo ── */
const RESULT_DATA = {
  'AnshPandey18/4o4PR': {
    runNum: 482, branch: 'fix/auth-leak', prNum: 73, prTitle: 'Fix authentication leak on resource route',
    resolutionTime: '14s', confidence: '0.97', testsPassed: 3, filesModified: 1,
    filePath: 'src/core/router.py',
    diff: [
      { type: 'ctx',  ln: '21', code: '@router.get("/api/v1/resource")' },
      { type: 'rem',  ln: '22', code: 'def get_resource():' },
      { type: 'add',  ln: '22', code: '@login_required' },
      { type: 'add',  ln: '23', code: 'def get_resource():' },
      { type: 'ctx',  ln: '24', code: '    return {"status": "success", "data": "protected"}' },
    ],
    tests: [
      { name: 'Unit: Route Access Control',         status: 'pass' },
      { name: 'Integration: Auth Middleware Flow',  status: 'pass' },
      { name: 'Security: Unauthenticated Request',  status: 'pass' },
    ],
    prDesc: 'Automatically generated fix for unauthenticated access vulnerability. Added @login_required decorator to the resource endpoint, preventing HTTP 200 responses for unauthenticated callers.',
    keyChanges: [
      'Applied @login_required decorator to /api/v1/resource',
      'Route now returns 401 for unauthenticated requests',
      'All 3 regression tests pass in Docker sandbox',
    ],
    agentLog: [
      { ts: '09:42:01', type: 'info',    msg: 'Starting patch synthesis engine...' },
      { ts: '09:42:04', type: 'debug',   msg: 'Loading AST map for src/core/router.py' },
      { ts: '09:42:08', type: 'warn',    msg: 'Pattern match found: unprotected route handler' },
      { ts: '09:42:12', type: 'system',  msg: 'Applying transformation: AddDecoratorPattern' },
      { ts: '09:42:18', type: 'ok',      msg: 'Compiled successfully.' },
      { ts: '09:42:22', type: 'ok',      msg: 'All tests passed. Patch stabilized.' },
    ],
  },
  default: {
    runNum: 483, branch: 'fix/auto-patch', prNum: 99, prTitle: 'Auto-generated bug fix',
    resolutionTime: '18s', confidence: '0.92', testsPassed: 8, filesModified: 1,
    filePath: 'src/core/handler.py',
    diff: [
      { type: 'ctx',  ln: '10', code: 'def handle_request(data):' },
      { type: 'rem',  ln: '11', code: '    return process(data)' },
      { type: 'add',  ln: '11', code: '    validated = validate(data)' },
      { type: 'add',  ln: '12', code: '    return process(validated)' },
      { type: 'ctx',  ln: '13', code: '' },
    ],
    tests: [
      { name: 'Unit: Input Validation',    status: 'pass' },
      { name: 'Integration: Pipeline Run', status: 'pass' },
      { name: 'Regression: Edge Cases',    status: 'pass' },
    ],
    prDesc: 'Automatically generated fix addressing the reported issue. The patch was validated against the full test suite in an isolated Docker container.',
    keyChanges: [
      'Added input validation before processing',
      'All regression tests pass',
      'No breaking changes introduced',
    ],
    agentLog: [
      { ts: '09:43:01', type: 'info',   msg: 'Starting patch synthesis engine...' },
      { ts: '09:43:05', type: 'system', msg: 'Applying AST transformation...' },
      { ts: '09:43:14', type: 'ok',     msg: 'Compiled successfully.' },
      { ts: '09:43:18', type: 'ok',     msg: 'All tests passed. Patch stabilized.' },
    ],
  },
};

/* ── animated counter ── */
function Counter({ to, suffix = '', decimals = 0 }) {
  const [v, setV] = useState(0);
  useEffect(() => {
    let s = 0;
    const n = parseFloat(to);
    const inc = n / (900 / 16);
    const t = setInterval(() => {
      s += inc;
      if (s >= n) { setV(n); clearInterval(t); }
      else setV(parseFloat(s.toFixed(decimals + 1)));
    }, 16);
    return () => clearInterval(t);
  }, [to]);
  return <span>{decimals > 0 ? v.toFixed(decimals) : Math.round(v)}{suffix}</span>;
}

/* ── diff line ── */
function DiffLine({ type, ln, code }) {
  const cls = type === 'add' ? 'rr-dl-add' : type === 'rem' ? 'rr-dl-rem' : 'rr-dl-ctx';
  const prefix = type === 'add' ? '+' : type === 'rem' ? '-' : ' ';
  return (
    <div className={`rr-diff-line ${cls}`}>
      <span className="rr-diff-ln">{ln}</span>
      <span className="rr-diff-prefix">{prefix}</span>
      <span className="rr-diff-code">{code}</span>
    </div>
  );
}

/* ── log type styles ── */
const LOG_CLS = { info: 'rr-log-info', debug: 'rr-log-debug', warn: 'rr-log-warn', system: 'rr-log-system', ok: 'rr-log-ok' };

export default function RunResult({ activeRun }) {
  const navigate  = useNavigate();
  const [visible, setVisible] = useState(false);
  const headerRef = useRef(null);

  const repo = activeRun?.repo || 'AnshPandey18/4o4PR';
  const bug  = activeRun?.bug  || 'Issue #404: pytest failure in auth module';
  const data = RESULT_DATA[repo] || RESULT_DATA.default;
  const failed = activeRun?.shouldFail || false;

  useEffect(() => { const t = setTimeout(() => setVisible(true), 80); return () => clearTimeout(t); }, []);

  return (
    <div className="rr-page">
      <div className="rr-grid-bg" />
      <div className="rr-scanline" />

      <div className="rr-wrap">

        {/* ── HEADER ── */}
        <header className={`rr-header ${visible ? 'rr-vis' : ''}`} ref={headerRef}>
          <p className="rr-eyebrow">Analysis Complete</p>

          <div className="rr-title-row">
            {failed ? (
              <h1 className="rr-headline rr-headline-fail">Bug unresolved ✗</h1>
            ) : (
              <h1 className="rr-headline">Bug resolved ✓</h1>
            )}
            <div className="rr-title-line" />
          </div>

          <div className="rr-header-meta">
            <p className="rr-meta-text">
              <strong className="rr-meta-strong">{repo}</strong>
              {' '}• Run #{data.runNum} • branch:{' '}
              <span className="rr-meta-branch">⎇ {data.branch}</span>
            </p>
            <div className="rr-status-chips">
              {failed ? (
                <span className="rr-chip rr-chip-fail">FAILED</span>
              ) : (
                <>
                  <span className="rr-chip rr-chip-teal">STABLE</span>
                  <span className="rr-chip rr-chip-blue">MERGE READY</span>
                </>
              )}
            </div>
          </div>

          {!failed && (
            <a
              href={`https://github.com/${repo}/pull/${data.prNum}`}
              target="_blank" rel="noopener noreferrer"
              className="rr-pr-btn"
            >
              View Pull Request #{data.prNum}
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="7" y1="17" x2="17" y2="7"/><polyline points="7 7 17 7 17 17"/>
              </svg>
            </a>
          )}
        </header>

        {/* ── STAT STRIP ── */}
        <div className={`rr-stats ${visible ? 'rr-vis' : ''}`} style={{ transitionDelay: '80ms' }}>
          {[
            { label: 'Resolution Time', value: data.resolutionTime, raw: parseFloat(data.resolutionTime), suffix: 's', decimals: 0, color: 'var(--rr-teal)' },
            { label: 'Confidence Score', value: data.confidence, raw: parseFloat(data.confidence), suffix: '', decimals: 2, color: failed ? '#e6714f' : 'var(--rr-teal)' },
            { label: 'Tests Passed',    value: String(data.testsPassed), raw: data.testsPassed, suffix: '', decimals: 0, color: '#f0f4f4' },
            { label: 'Files Modified',  value: String(data.filesModified), raw: data.filesModified, suffix: '', decimals: 0, color: '#f0f4f4' },
          ].map((s, i) => (
            <div key={s.label} className="rr-stat" style={{ '--i': i }}>
              <span className="rr-stat-val" style={{ color: s.color }}>
                {visible ? <Counter to={s.raw} suffix={s.suffix} decimals={s.decimals} /> : '—'}
              </span>
              <span className="rr-stat-lbl">{s.label}</span>
            </div>
          ))}
        </div>

        {/* ── MAIN GRID ── */}
        <div className="rr-main-grid">

          {/* ── LEFT: DIFF + TESTS ── */}
          <div className="rr-left">

            {/* diff viewer */}
            <div className="rr-diff-card">
              <div className="rr-diff-bar">
                <div className="rr-diff-bar-left">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                  <span className="rr-diff-filename">{data.filePath}</span>
                </div>
                <div className="rr-diff-badge">
                  <span className="rr-diff-dot" />
                  MODIFIED
                </div>
              </div>
              <div className="rr-diff-body">
                {data.diff.map((l, i) => <DiffLine key={i} {...l} />)}
              </div>
            </div>

            {/* validation pipeline */}
            <div className="rr-card rr-tests-card">
              <div className="rr-card-head">
                <div className="rr-card-head-bar" />
                <span className="rr-card-label">Validation Pipeline</span>
              </div>
              <div className="rr-tests-list">
                {data.tests.map((t, i) => (
                  <div key={i} className={`rr-test-row ${i < data.tests.length - 1 ? 'rr-test-border' : ''}`}>
                    <div className="rr-test-left">
                      <span className={`rr-test-dot ${t.status === 'pass' ? 'dot-pass' : 'dot-fail'}`} />
                      <span className="rr-test-name">{t.name}</span>
                    </div>
                    <span className={`rr-test-badge ${t.status === 'pass' ? 'badge-pass' : 'badge-fail'}`}>
                      {t.status === 'pass' ? 'PASS' : 'FAIL'}
                    </span>
                  </div>
                ))}
              </div>
            </div>

          </div>

          {/* ── RIGHT: PR DESC + LOG + ACTIONS ── */}
          <div className="rr-right">

            {/* PR description */}
            <div className="rr-card rr-pr-card">
              <div className="rr-pr-top-border" />
              <h3 className="rr-pr-title">PR Description</h3>
              <p className="rr-pr-desc">{data.prDesc}</p>
              <p className="rr-pr-changes-lbl">Key Changes:</p>
              <ul className="rr-pr-changes">
                {data.keyChanges.map((c, i) => (
                  <li key={i} className="rr-pr-change-item">
                    <span className="rr-pr-change-dot" />
                    {c}
                  </li>
                ))}
              </ul>
            </div>

            {/* agent log */}
            <div className="rr-card rr-log-card">
              <div className="rr-log-head">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                AGENT_LOG :: ATTEMPT_02
              </div>
              <div className="rr-log-list">
                {data.agentLog.map((l, i) => (
                  <div key={i} className={`rr-log-line ${LOG_CLS[l.type] || 'rr-log-debug'}`}>
                    <span className="rr-log-ts">[{l.ts}]</span>
                    <span className="rr-log-msg">{l.msg}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* action buttons */}
            <div className="rr-actions">
              {!failed ? (
                <>
                  <a
                    href={`https://github.com/${repo}/pull/${data.prNum}`}
                    target="_blank" rel="noopener noreferrer"
                    className="rr-btn-primary"
                  >
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                    Approve &amp; Merge Patch
                  </a>
                  <button className="rr-btn-outline" onClick={() => navigate('/run')}>
                    Request Manual Review
                  </button>
                </>
              ) : (
                <>
                  <button className="rr-btn-primary rr-btn-retry" onClick={() => navigate('/run')}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-4.17"/></svg>
                    Retry With New Config
                  </button>
                  <button className="rr-btn-outline" onClick={() => navigate('/run')}>
                    Modify Configuration
                  </button>
                </>
              )}
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}
