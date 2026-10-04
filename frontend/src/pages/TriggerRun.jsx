import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { MOCK_BUGS, MOCK_REPO_STATS } from '../data/mockPipeline';
import { startRun, startDemoRun } from '../services/api';
import './TriggerRun.css';

/* ─── constants ─────────────────────────────────────────────────────────── */
const PIPELINE_STEPS = [
  { n: '01', title: 'Environment Sync',     desc: 'Cloning repository and installing all dependencies.' },
  { n: '02', title: 'Failure Reproduction', desc: 'Executing specified test to capture stack trace logs.' },
  { n: '03', title: 'Trace Analysis',       desc: 'Mapping stack trace to source code segments.' },
  { n: '04', title: 'Patch Generation',     desc: 'Synthesising candidate code fixes via LLM.' },
  { n: '05', title: 'Verification Run',     desc: 'Testing proposed patches against the full suite.' },
  { n: '06', title: 'Pull Request Staging', desc: 'Finalising documentation and PR metadata.' },
];

const RUNTIME_SETTINGS = [
  { key: 'MAX_RETRIES',  val: '3' },
  { key: 'MODEL_ENGINE', val: 'GEMINI-2.5-PRO' },
  { key: 'TIMEOUT_SEC',  val: '600' },
  { key: 'CONCURRENCY',  val: 'ENABLED' },
];

const DEMO_REPO_STATS = {
  healthIndex: '82%',
  coverage: '61.5%',
  activeTests: '11',
  prSuccessRate: '—',
  avgRepairTime: '~3s',
  activeBranch: 'main',
  status: 'Warning',
};

/* ─── component ─────────────────────────────────────────────────────────── */
export default function TriggerRun({ onStartRun }) {
  const [sourceMode,   setSourceMode]   = useState('demo');   // 'demo' | 'github'
  const [selectedBug,  setSelectedBug]  = useState(MOCK_BUGS[0].id);
  const [launching,    setLaunching]    = useState(false);
  const [error,        setError]        = useState(null);
  const navigate = useNavigate();
  const pageRef  = useRef(null);

  const activeBug  = MOCK_BUGS.find(b => b.id === selectedBug) || MOCK_BUGS[0];
  const repoStats  = sourceMode === 'demo' ? DEMO_REPO_STATS : (MOCK_REPO_STATS['AnshPandey18/4o4PR'] || {});
  const sevColor   = { High: '#e6714f', Medium: '#ffb764', Low: '#20c2a4' }[activeBug.severity] || '#888';

  /* ─── submit ─────────────────────────────────────────────────────────── */
  const handleSubmit = async e => {
    if (e) e.preventDefault();
    setError(null);
    setLaunching(true);
    try {
      let runData;
      if (sourceMode === 'demo') {
        // Run the real CLI pipeline on tests/fixtures/sample_bugs
        runData = await startDemoRun();
      } else {
        runData = await startRun({
          repo: 'AnshPandey18/4o4PR',
          bug: activeBug.title,
          branch: 'main',
        });
      }
      onStartRun({
        repo: sourceMode === 'demo' ? 'demo/sample_bugs' : 'AnshPandey18/4o4PR',
        bug:  sourceMode === 'demo'
          ? 'Demo: sample_bugs fixture (calculator + string_utils)'
          : activeBug.title,
        runId: runData.id,
      });
      navigate('/status');
    } catch (err) {
      setError(err.message || 'Failed to start run. Is the backend running?');
      setLaunching(false);
    }
  };

  useEffect(() => {
    const h = e => { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') handleSubmit(); };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [sourceMode, selectedBug]);

  /* ─── render ─────────────────────────────────────────────────────────── */
  return (
    <div className="tr2-page" ref={pageRef}>
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
            Point 4o4PR at a repository or use the built-in demo fixtures — it will
            analyse failing tests, reproduce the environment, and propose a verified
            resolution.
          </p>
        </section>

        {/* ── MAIN GRID ── */}
        <div className="tr2-main-grid">
          <div className="tr2-left">
            <div className="tr2-card">
              <div className="tr2-card-heading">
                <span className="tr2-card-dot" />
                <h2 className="tr2-card-title">Configuration</h2>
              </div>

              <form onSubmit={handleSubmit} className="tr2-form">

                {/* ── source mode tabs ── */}
                <div className="tr2-source-tabs">
                  <button
                    type="button"
                    className={`tr2-source-tab ${sourceMode === 'demo' ? 'tr2-source-tab-active' : ''}`}
                    onClick={() => setSourceMode('demo')}
                  >
                    {/* flask / beaker icon */}
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M9 3h6M9 3v8l-4 9h14l-4-9V3"/>
                    </svg>
                    Demo (Fixtures)
                  </button>
                  <button
                    type="button"
                    className={`tr2-source-tab ${sourceMode === 'github' ? 'tr2-source-tab-active' : ''}`}
                    onClick={() => setSourceMode('github')}
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/>
                    </svg>
                    GitHub Repo
                  </button>
                </div>

                {/* ── demo mode info strip ── */}
                {sourceMode === 'demo' && (
                  <div className="tr2-demo-strip">
                    <div className="tr2-demo-strip-head">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                      </svg>
                      Demo Mode
                    </div>
                    <div className="tr2-demo-paths">
                      <div className="tr2-demo-path-row">
                        <span className="tr2-demo-path-lbl">Input (faulty code)</span>
                        <code className="tr2-demo-path-val">backend/tests/fixtures/sample_bugs</code>
                      </div>
                      <div className="tr2-demo-path-row">
                        <span className="tr2-demo-path-lbl">Output</span>
                        <code className="tr2-demo-path-val">backend/runs/</code>
                      </div>
                      <div className="tr2-demo-path-row">
                        <span className="tr2-demo-path-lbl">Command</span>
                        <code className="tr2-demo-path-val tr2-demo-cmd">
                          python run_pipeline.py --root tests/fixtures/sample_bugs --import-root src --verbose
                        </code>
                      </div>
                    </div>
                    <p className="tr2-demo-note">
                      The fixture contains <strong>6 intentional bugs</strong> across
                      <code>src/calculator.py</code> and <code>src/string_utils.py</code>.
                      Running the pipeline will detect them, group them, build LLM context,
                      and write the full report to <code>backend/runs/</code>.
                    </p>
                  </div>
                )}

                {/* ── github mode fields ── */}
                {sourceMode === 'github' && (
                  <>
                    <div className="tr2-field">
                      <label className="tr2-label">Failing Test</label>
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
                  </>
                )}

                {/* ── error banner ── */}
                {error && (
                  <div className="tr2-error-banner">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                    {error}
                  </div>
                )}

                {/* ── actions ── */}
                <div className="tr2-actions">
                  <button type="submit" className="tr2-btn-primary" disabled={launching}>
                    {launching ? (
                      <><span className="tr2-spinner" />Initializing…</>
                    ) : (
                      <>
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                        {sourceMode === 'demo' ? 'Run Demo Pipeline' : 'Run Pipeline'}
                      </>
                    )}
                  </button>
                  <button type="button" className="tr2-btn-outline">Save Draft</button>
                  <span className="tr2-kbd-hint"><kbd>⌘</kbd><kbd>↵</kbd></span>
                </div>

              </form>
            </div>
          </div>

          {/* ── RIGHT: pipeline + repo stats + runtime ── */}
          <div className="tr2-right">
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

            <div className="tr2-card tr2-card-blush">
              <div className="tr2-card-heading">
                <span className="tr2-card-dot" />
                <h2 className="tr2-card-title">
                  {sourceMode === 'demo' ? 'Demo Fixture Profile' : 'Repository Profile'}
                </h2>
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
