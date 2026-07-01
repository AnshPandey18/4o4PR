import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { MOCK_REPOSITORIES, MOCK_BUGS, MOCK_REPO_STATS } from '../data/mockPipeline';
import './TriggerRun.css';

const PIPELINE_STEPS = [
  { n: '01', title: 'Environment Sync',     desc: 'Cloning repository and installing all dependencies.' },
  { n: '02', title: 'Failure Reproduction', desc: 'Executing specified test to capture stack trace logs.' },
  { n: '03', title: 'Trace Analysis',       desc: 'Mapping stack trace to source code segments.' },
  { n: '04', title: 'Patch Generation',     desc: 'Synthesizing candidate code fixes via LLM.' },
  { n: '05', title: 'Verification Run',     desc: 'Testing proposed patches against the full suite.' },
  { n: '06', title: 'Pull Request Staging', desc: 'Finalising documentation and PR metadata.' },
];

const RUNTIME_SETTINGS = [
  { key: 'MAX_RETRIES',  val: '3' },
  { key: 'MODEL_ENGINE', val: 'GEMINI-2.5-PRO' },
  { key: 'TIMEOUT_SEC',  val: '600' },
  { key: 'CONCURRENCY',  val: 'ENABLED' },
];

export default function TriggerRun({ onStartRun }) {
  const [selectedRepo, setSelectedRepo] = useState(MOCK_REPOSITORIES[0]);
  const [selectedBug,  setSelectedBug]  = useState(MOCK_BUGS[0].id);
  const [shouldFail,   setShouldFail]   = useState(false);
  const [launching,    setLaunching]    = useState(false);
  const [repoKey,      setRepoKey]      = useState(0);
  const navigate = useNavigate();
  const pageRef  = useRef(null);

  const repoStats = MOCK_REPO_STATS[selectedRepo] || {};
  const activeBug = MOCK_BUGS.find(b => b.id === selectedBug) || MOCK_BUGS[0];

  const handleRepoChange = e => { setSelectedRepo(e.target.value); setRepoKey(k => k + 1); };

  const handleSubmit = e => {
    if (e) e.preventDefault();
    setLaunching(true);
    setTimeout(() => {
      onStartRun({ repo: selectedRepo, bug: activeBug.title, shouldFail });
      navigate('/status');
    }, 700);
  };

  useEffect(() => {
    const h = e => { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') handleSubmit(); };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [selectedRepo, selectedBug, shouldFail]);

  const sevColor = { High: '#e6714f', Medium: '#ffb764', Low: '#20c2a4' }[activeBug.severity] || '#888';

  return (
    <div className="tr2-page" ref={pageRef}>
      {/* terminal grid overlay */}
      <div className="tr2-grid-overlay" />

      <div className="tr2-wrap">

        {/* ── HERO ── */}
        <section className="tr2-hero">
          <span className="tr2-eyebrow">
            <span className="tr2-eyebrow-dot" />
            Automated Debugging V2.4
          </span>
          <h1 className="tr2-headline">
            Initiate Autonomous<br />
            <em className="tr2-headline-em">Patch Sequence</em>
          </h1>
          <p className="tr2-hero-sub">
            Connect your repository and specify the failing test. 4o4PR will analyse the stack
            trace, reproduce the environment, and propose a verified resolution.
          </p>
        </section>

        {/* ── MAIN GRID ── */}
        <div className="tr2-main-grid">

          {/* ── LEFT: FORM ── */}
          <div className="tr2-left">
            <div className="tr2-card">
              <div className="tr2-card-heading">
                <span className="tr2-card-dot" />
                <h2 className="tr2-card-title">Configuration</h2>
              </div>

              <form onSubmit={handleSubmit} className="tr2-form">

                {/* two-col row */}
                <div className="tr2-row-2">
                  <div className="tr2-field">
                    <label className="tr2-label">Github Repo URL</label>
                    <div className="tr2-select-wrap">
                      <select
                        className="tr2-select"
                        value={selectedRepo}
                        onChange={handleRepoChange}
                      >
                        {MOCK_REPOSITORIES.map(r => (
                          <option key={r} value={r}>{r}</option>
                        ))}
                      </select>
                      <span className="tr2-chevron">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
                      </span>
                    </div>
                  </div>

                  <div className="tr2-field">
                    <label className="tr2-label">Branch</label>
                    <div className="tr2-select-wrap">
                      <select className="tr2-select">
                        <option>{repoStats.activeBranch || 'main'}</option>
                        <option>develop</option>
                        <option>staging</option>
                      </select>
                      <span className="tr2-chevron">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
                      </span>
                    </div>
                  </div>
                </div>

                {/* failing test */}
                <div className="tr2-field">
                  <label className="tr2-label">Failing Test Path</label>
                  <div className="tr2-select-wrap">
                    <select
                      className="tr2-select"
                      value={selectedBug}
                      onChange={e => setSelectedBug(e.target.value)}
                    >
                      {MOCK_BUGS.map(b => (
                        <option key={b.id} value={b.id}>{b.title}</option>
                      ))}
                    </select>
                    <span className="tr2-chevron">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
                    </span>
                  </div>
                </div>

                {/* bug description */}
                <div className="tr2-field">
                  <label className="tr2-label">Bug Description (Optional)</label>
                  <textarea
                    className="tr2-textarea"
                    rows={4}
                    placeholder="Describe the expected vs actual behaviour…"
                  />
                </div>

                {/* diagnostics strip */}
                <div className="tr2-diag" key={activeBug.id} style={{ '--sev-color': sevColor }}>
                  <div className="tr2-diag-header">
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                    Static Code Diagnostics
                  </div>
                  <div className="tr2-diag-badges">
                    <span className={`tr2-badge tr2-sev-${activeBug.severity.toLowerCase()}`}>Severity: {activeBug.severity}</span>
                    <span className={`tr2-badge tr2-comp-${activeBug.complexity.toLowerCase()}`}>Complexity: {activeBug.complexity}</span>
                    <span className="tr2-badge tr2-badge-mono">Est. {activeBug.eta}</span>
                  </div>
                  <p className="tr2-diag-impact">
                    <span className="tr2-diag-impact-lbl">Remediation Impact</span>
                    {activeBug.impact}
                  </p>
                </div>

                {/* failure toggle */}
                <label className={`tr2-toggle ${shouldFail ? 'tr2-toggle-on' : ''}`} htmlFor="fail-toggle">
                  <div className="tr2-toggle-info">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                    <span className="tr2-toggle-lbl">Simulate patch test failure</span>
                    <span className="tr2-toggle-sub">Verify error states in pipeline</span>
                  </div>
                  <div className="tr2-switch">
                    <input type="checkbox" id="fail-toggle" className="tr2-switch-input"
                      checked={shouldFail} onChange={e => setShouldFail(e.target.checked)} />
                    <div className="tr2-switch-thumb" />
                  </div>
                </label>

                {/* actions */}
                <div className="tr2-actions">
                  <button type="submit" className="tr2-btn-primary" disabled={launching}>
                    {launching ? (
                      <><span className="tr2-spinner" />Initializing…</>
                    ) : (
                      <>
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                        Run Pipeline
                      </>
                    )}
                  </button>
                  <button type="button" className="tr2-btn-outline">Save Draft</button>
                  <span className="tr2-kbd-hint"><kbd>⌘</kbd><kbd>↵</kbd></span>
                </div>

              </form>
            </div>
          </div>

          {/* ── RIGHT: PIPELINE + SETTINGS + REPO STATS ── */}
          <div className="tr2-right">

            {/* pipeline card */}
            <div className="tr2-card tr2-card-teal">
              <div className="tr2-card-heading">
                <span className="tr2-card-dot" />
                <h2 className="tr2-card-title">Pipeline Sequence</h2>
              </div>
              <ul className="tr2-pipeline">
                {PIPELINE_STEPS.map(s => (
                  <li key={s.n} className="tr2-pipeline-step">
                    <span className="tr2-step-num">{s.n}</span>
                    <div>
                      <p className="tr2-step-title">{s.title}</p>
                      <p className="tr2-step-desc">{s.desc}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>

            {/* repo stats */}
            <div className="tr2-card tr2-card-blush" key={repoKey}>
              <div className="tr2-card-heading">
                <span className="tr2-card-dot" />
                <h2 className="tr2-card-title">Repository Profile</h2>
                <span className={`tr2-status-pill ${repoStats.status === 'Healthy' ? 'pill-ok' : 'pill-warn'}`}>
                  <span className="tr2-status-dot" />{repoStats.status}
                </span>
              </div>
              <div className="tr2-stats-grid">
                <div className="tr2-stat"><span className="tr2-stat-k">Health Index</span><span className="tr2-stat-v tr2-v-teal">{repoStats.healthIndex}</span></div>
                <div className="tr2-stat"><span className="tr2-stat-k">Test Coverage</span><span className="tr2-stat-v">{repoStats.coverage}</span></div>
                <div className="tr2-stat"><span className="tr2-stat-k">Active Tests</span><span className="tr2-stat-v">{repoStats.activeTests}</span></div>
                <div className="tr2-stat"><span className="tr2-stat-k">Fix Success</span><span className="tr2-stat-v tr2-v-blue">{repoStats.prSuccessRate}</span></div>
                <div className="tr2-stat"><span className="tr2-stat-k">Avg Solve</span><span className="tr2-stat-v">{repoStats.avgRepairTime}</span></div>
                <div className="tr2-stat"><span className="tr2-stat-k">Branch</span><span className="tr2-stat-v tr2-v-mono">{repoStats.activeBranch}</span></div>
              </div>
            </div>

            {/* runtime settings */}
            <div className="tr2-card">
              <div className="tr2-card-heading">
                <span className="tr2-card-dot" />
                <h2 className="tr2-card-title">Runtime Settings</h2>
              </div>
              <div className="tr2-settings">
                {RUNTIME_SETTINGS.map(s => (
                  <div key={s.key} className="tr2-setting-row">
                    <span className="tr2-setting-k">{s.key}</span>
                    <span className="tr2-setting-v">{s.val}</span>
                  </div>
                ))}
              </div>
              <button className="tr2-settings-link">Modify Infrastructure Config →</button>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}
