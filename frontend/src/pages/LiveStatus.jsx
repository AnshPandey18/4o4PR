import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { PIPELINE_STEPS } from '../data/mockPipeline';
import { streamRun, getRunsDirList } from '../services/api';
import './LiveStatus.css';

/* ── elapsed timer ── */
function useElapsedTimer(running) {
  const [ms, setMs] = useState(0);
  const ref = useRef(null);
  useEffect(() => {
    if (running) {
      ref.current = setInterval(() => setMs(p => p + 100), 100);
    } else {
      clearInterval(ref.current);
    }
    return () => clearInterval(ref.current);
  }, [running]);
  const total = Math.floor(ms / 1000);
  const h = String(Math.floor(total / 3600)).padStart(2, '0');
  const m = String(Math.floor((total % 3600) / 60)).padStart(2, '0');
  const s = String(total % 60).padStart(2, '0');
  const cs = String(Math.floor((ms % 1000) / 10)).padStart(2, '0');
  return `${h}:${m}:${s}.${cs}`;
}

/* ── log line classifier ── */
function LogLine({ line, idx }) {
  if (!line) return <div key={idx} style={{ minHeight: 14 }} />;
  let cls = 'ls2-log-default';

  const isCmd = line.startsWith('Running command:') || line.startsWith('Initializing git clone') ||
    line.startsWith('Staging files:') || line.startsWith('Committing') || line.startsWith('Pushing') ||
    line.startsWith('Opening Pull Request') || line.startsWith('Spawning docker');

  if (isCmd) return (
    <div key={idx} className="ls2-log-cmd">
      <span className="ls2-log-prompt">$</span>{line}
    </div>
  );

  if (line.includes('FAILURES') || line.includes('AssertionError') || line.startsWith('E  ') ||
    line.startsWith('>  ') || line.includes('FAILED') || line.includes('ERROR:')) cls = 'ls2-log-err';
  else if (line.includes('PASSED') || line.includes('passed') || line.includes('SUCCESS') ||
    line.includes('successful') || line.includes('COMPLETED') || line.includes('done.'))
    cls = 'ls2-log-ok';
  else if (line.startsWith('[STATUS]') || line.startsWith('[INFO]') || line.startsWith('[SYSTEM]'))
    cls = 'ls2-log-info';
  else if (line.startsWith('+')) cls = 'ls2-log-add';
  else if (line.startsWith('-') && !line.startsWith('---')) cls = 'ls2-log-rem';
  else if (line.startsWith('@@') || line.startsWith('---')) cls = 'ls2-log-meta';
  else if (line.startsWith('===')) cls = 'ls2-log-sep';

  return <div key={idx} className={cls}>{line}</div>;
}

export default function LiveStatus({ activeRun, onResetRun, onRunComplete }) {
  const navigate   = useNavigate();
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [pipelineStatus,   setPipelineStatus]   = useState('running');
  const [consoleLogs,      setConsoleLogs]       = useState([]);
  const [progress,         setProgress]          = useState(5);
  const [prUrl,            setPrUrl]             = useState(null);
  const [paused,           setPaused]            = useState(false);
  const [backendOnline,    setBackendOnline]      = useState(true);

  const logBodyRef = useRef(null);
  const esRef      = useRef(null);

  const [runFiles, setRunFiles] = useState([]);
  const [runDirName, setRunDirName] = useState(null);
  const reportDirs = [];
  const selectedReport = null;
  const reportDropOpen = false;
  const dropRef = useRef(null);
  const selRunEntry = null;

  const runRepo = activeRun?.repo || 'AnshPandey18/4o4PR';
  const runBug  = activeRun?.bug  || 'Issue #404: pytest failure in auth module';
  const runId   = activeRun?.runId;

  const timer = useElapsedTimer(pipelineStatus === 'running' && !paused);

  /* auto-scroll logs */
  useEffect(() => {
    if (logBodyRef.current) logBodyRef.current.scrollTop = logBodyRef.current.scrollHeight;
  }, [consoleLogs]);

  /* connect to SSE or fall back to mock simulation */
  useEffect(() => {
    if (!runId) {
      // No backend run — show idle state with info message
      setConsoleLogs(['[INFO] No active backend run. Please start a run from the Trigger page.']);
      setPipelineStatus('idle');
      return;
    }

    // Connect to real SSE stream
    const es = streamRun(runId);
    esRef.current = es;

    es.onmessage = (evt) => {
      if (paused) return;
      try {
        const data = JSON.parse(evt.data);

        // Append log line
        if (data.line !== null && data.line !== undefined) {
          setConsoleLogs(prev => [...prev, data.line]);
        }

        // Update step tracker
        if (typeof data.step_index === 'number') {
          setCurrentStepIndex(data.step_index);
          // Calculate progress
          const base = (data.step_index / PIPELINE_STEPS.length) * 100;
          setProgress(Math.min(Math.round(base + 100 / PIPELINE_STEPS.length * 0.5), 98));
        }

        // PR URL
        if (data.pr_url) {
          setPrUrl(data.pr_url);
        }

        // Final state
        if (data.finished) {
          setPipelineStatus(data.status);
          setProgress(data.status === 'completed' ? 100 : 65);
          es.close();
          if (data.run_dir) {
            getRunsDirList().then(result => {
              const currentRun = (result.runs || []).find(run => run.run_dir === data.run_dir);
              setRunDirName(data.run_dir);
              setRunFiles(currentRun?.files || []);
            }).catch(() => {
              setRunDirName(data.run_dir);
              setRunFiles([]);
            });
          }
          // Notify App so Report page can use the real run data
          onRunComplete?.({
            runId,
            runDir: data.run_dir,
            status: data.status,
            bugsDetected: data.bugs_detected,
            testsTotal: data.tests_total,
            testsPassed: data.tests_passed,
            testsFailed: data.tests_failed,
            durationMs: data.duration_ms,
            repo: runRepo,
            bug: runBug,
          });
        }
      } catch {/* ignore parse errors */}
    };

    es.onerror = () => {
      setBackendOnline(false);
      setPipelineStatus('failed');
      setConsoleLogs(prev => [...prev, '[ERROR] Lost connection to backend. Is the server running?']);
      es.close();
    };

    return () => es.close();
  }, [runId]);

  const handleBack = () => { onResetRun?.(); navigate('/run'); };

  const stepOf = `Step ${Math.min(currentStepIndex + 1, PIPELINE_STEPS.length)} of ${PIPELINE_STEPS.length}`;

  return (
    <div className="ls2-page">
      <div className="ls2-grid-bg" />

      {/* sticky progress bar */}
      <div className="ls2-progress-rail">
        <div
          className={`ls2-progress-fill ${pipelineStatus === 'completed' ? 'ls2-fill-done' : pipelineStatus === 'failed' ? 'ls2-fill-fail' : ''}`}
          style={{ width: `${progress}%` }}
        />
      </div>

      <div className="ls2-wrap">
        {/* eyebrow */}
        <section className="ls2-eyebrow-section">
          <div className="ls2-eyebrow-left">
            <div className="ls2-eyebrow-chips">
              <span className={`ls2-live-chip ${pipelineStatus === 'running' ? 'chip-running' : pipelineStatus === 'completed' ? 'chip-done' : pipelineStatus === 'failed' ? 'chip-fail' : ''}`}>
                {pipelineStatus === 'running' && <span className="ls2-chip-dot" />}
                {pipelineStatus === 'running' ? 'Live Run' : pipelineStatus === 'completed' ? 'Completed' : pipelineStatus === 'failed' ? 'Failed' : 'Idle'}
              </span>
              <span className="ls2-job-id">/ Job #{runId || 'N/A'}</span>
            </div>
            <h1 className="ls2-headline">
              Automated Vulnerability<br />
              <em className="ls2-headline-em">Patching</em>
            </h1>
            <div className="ls2-meta-row">
              <span className="ls2-meta-label">Target:</span>
              <code className="ls2-meta-code">{runRepo}</code>
              <span className="ls2-meta-sep">/</span>
              <span className="ls2-meta-bug">{runBug}</span>
            </div>
          </div>

          {/* timer card */}
          <div className="ls2-timer-card">
            <div className="ls2-timer-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
              </svg>
            </div>
            <div>
              <span className="ls2-timer-label">Elapsed Runtime</span>
              <span className="ls2-timer-value">{timer}</span>
            </div>
            <div className="ls2-timer-controls">
              <button
                className={`ls2-ctrl-btn ${paused ? 'ls2-ctrl-active' : ''}`}
                onClick={() => setPaused(p => !p)}
                title={paused ? 'Resume' : 'Pause'}
                disabled={pipelineStatus !== 'running'}
              >
                {paused
                  ? <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                  : <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
                }
              </button>
              <button
                className="ls2-ctrl-btn ls2-ctrl-stop"
                onClick={handleBack}
                title="Stop & exit"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/></svg>
              </button>
            </div>
          </div>
        </section>

        {/* main grid */}
        <div className="ls2-main-grid">

          {/* left: pipeline tracker */}
          <div className="ls2-left">
            <div className="ls2-card">
              <div className="ls2-card-head">
                <h2 className="ls2-card-title">Execution Pipeline</h2>
                <span className="ls2-step-of">{stepOf}</span>
              </div>
              <div className="ls2-steps">
                <div className="ls2-spine" />
                {PIPELINE_STEPS.map((step, idx) => {
                  const done    = idx < currentStepIndex && pipelineStatus !== 'failed';
                  const active  = idx === currentStepIndex && pipelineStatus === 'running';
                  const failed  = idx === currentStepIndex && pipelineStatus === 'failed';
                  const pending = idx > currentStepIndex || pipelineStatus === 'idle';

                  return (
                    <div key={step.id} className={`ls2-step ${done ? 'step-done' : active ? 'step-active' : failed ? 'step-fail' : 'step-pending'}`}>
                      <div className="ls2-node-wrap">
                        <div className="ls2-node">
                          {done && (
                            <svg width="12" height="10" viewBox="0 0 12 10" fill="none">
                              <path d="M1 5L4.5 8.5L11 1.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                            </svg>
                          )}
                          {active && <span className="ls2-node-pulse" />}
                          {failed && (
                            <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
                              <line x1="1" y1="1" x2="10" y2="10" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                              <line x1="10" y1="1" x2="1" y2="10" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                            </svg>
                          )}
                          {pending && (
                            <span className="ls2-node-num">
                              {String(idx + 1).padStart(2, '0')}
                            </span>
                          )}
                        </div>
                        {active && <div className="ls2-node-ring" />}
                      </div>
                      <div className="ls2-step-content">
                        <div className="ls2-step-top">
                          <span className="ls2-step-name">{step.name}</span>
                          {active  && <span className="ls2-running-badge"><span className="ls2-running-dot" />RUNNING</span>}
                          {done    && <span className="ls2-done-badge">DONE</span>}
                          {failed  && <span className="ls2-fail-badge">FAILED</span>}
                        </div>
                        <p className="ls2-step-desc">{step.description}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
            {runFiles.length > 0 && (
              <div className="ls2-rdd-files">
                <div className="ls2-rdd-files-head">
                  <span>Pipeline Run Files</span>
                  <span className="ls2-rdd-files-count">{runDirName}</span>
                </div>
                <div className="ls2-rdd-files-list">
                  {runFiles.map(filePath => (
                    <div key={filePath} className="ls2-rdd-file-row">
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0-2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>
                      <span>{filePath}</span>
                    </div>
                  ))}
                  <div
                    className="ls2-rdd-file-row ls2-rdd-file-md"
                    style={{ cursor: 'pointer' }}
                    onClick={() => navigate('/report')}
                    role="button"
                    tabIndex={0}
                    onKeyDown={e => e.key === 'Enter' && navigate('/report')}
                    title="Open full markdown report"
                  >
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0-2 2V8z"/><polyline points="14 2 20 8"/></svg>
                    <span style={{ flex: 1 }}>bug_report.md</span>
                    <span className="ls2-rdd-md-badge">View Full Report ↓</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* right: log + root cause + outcome */}
          <div className="ls2-right">
            {/* stdout card */}
            <div className="ls2-card ls2-card-teal">
              <div className="ls2-card-head">
                <div className="ls2-terminal-title">
                  <div className="ls2-term-dots">
                    <span className="ls2-dot ls2-dot-r"/><span className="ls2-dot ls2-dot-y"/><span className="ls2-dot ls2-dot-g"/>
                  </div>
                  <span className="ls2-term-name">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{marginRight:5}}><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
                    STDOUT / ERROR LOG
                  </span>
                </div>
                {pipelineStatus === 'running' && (
                  <span className="ls2-autoscroll">AUTO-SCROLLING</span>
                )}
              </div>
              <div className="ls2-log-body" ref={logBodyRef}>
                {consoleLogs.length === 0
                  ? <span className="ls2-log-idle">Console idle — awaiting execution…</span>
                  : consoleLogs.map((line, i) => <LogLine key={i} line={line} idx={i} />)
                }
              </div>
            </div>

            {/* OUTCOME — success */}
            {pipelineStatus === 'completed' && (
              <div className="ls2-outcome ls2-outcome-success">
                <div className="ls2-outcome-orb orb-success" />
                <div className="ls2-outcome-body">
                  <div className="ls2-outcome-head">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                    Repair Successfully Executed
                  </div>
                  <p className="ls2-outcome-desc">Fix generated, validated against pytest docker sandbox, and submitted as a pull request.</p>

                  {/* ── Past Reports Dropdown ── */}
                  {reportDirs.length > 0 && (
                    <div className="ls2-report-dropdown-wrap" ref={dropRef}>
                      <div className="ls2-rdd-label">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                        Past Runs ({reportDirs.length})
                      </div>
                      <button
                        className="ls2-rdd-trigger"
                        onClick={() => setReportDropOpen(p => !p)}
                        id="ls2-report-dropdown-btn"
                      >
                        <span className="ls2-rdd-trigger-text">
                          {selectedReport || 'Select a run report…'}
                        </span>
                        <svg
                          width="12" height="12" viewBox="0 0 24 24" fill="none"
                          stroke="currentColor" strokeWidth="2.5"
                          strokeLinecap="round" strokeLinejoin="round"
                          style={{ transform: reportDropOpen ? 'rotate(180deg)' : 'none', transition: 'transform .2s' }}
                        >
                          <polyline points="6 9 12 15 18 9"/>
                        </svg>
                      </button>

                      {reportDropOpen && (
                        <div className="ls2-rdd-menu">
                          {reportDirs.map(r => (
                            <button
                              key={r.run_dir}
                              className={`ls2-rdd-item ${selectedReport === r.run_dir ? 'ls2-rdd-item-active' : ''}`}
                              onClick={() => { setSelectedReport(r.run_dir); setReportDropOpen(false); }}
                            >
                              <span className="ls2-rdd-item-dir">{r.run_dir}</span>
                              <span className="ls2-rdd-item-meta">
                                {r.files.length} file{r.files.length !== 1 ? 's' : ''}
                                {r.has_markdown && <span className="ls2-rdd-md-badge">MD</span>}
                              </span>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* ── Selected Report File List ── */}
                  {selRunEntry && (
                    <div className="ls2-rdd-files ls2-rdd-files-right">
                      <div className="ls2-rdd-files-head">
                        <span>📂 {selRunEntry.run_dir}</span>
                        <span className="ls2-rdd-files-count">{selRunEntry.files.length} artifact{selRunEntry.files.length !== 1 ? 's' : ''}</span>
                      </div>
                      <div className="ls2-rdd-files-list">
                        {/* JSON artifacts only — .md is excluded from files[] by the backend */}
                        {selRunEntry.files.map(f => (
                          <div key={f} className="ls2-rdd-file-row">
                            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>
                            <span>{f}</span>
                          </div>
                        ))}
                        {/* .md shown as a special row — navigates to /report */}
                        {selRunEntry.has_markdown && (
                          <div
                            className="ls2-rdd-file-row ls2-rdd-file-md"
                            style={{ cursor: 'pointer' }}
                            onClick={() => navigate('/report')}
                            role="button"
                            tabIndex={0}
                            onKeyDown={e => e.key === 'Enter' && navigate('/report')}
                            title="Open full markdown report"
                          >
                            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                            <span style={{ flex: 1 }}>detector/bug_report.md</span>
                            <span className="ls2-rdd-md-badge">View Full Report ↓</span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  <div className="ls2-rdd-files">
                    <div className="ls2-rdd-files-head">
                      <span>Pipeline Run Files</span>
                      <span className="ls2-rdd-files-count">{runDirName}</span>
                    </div>
                    <div className="ls2-rdd-files-list">
                      {runFiles.map(filePath => (
                        <div key={filePath} className="ls2-rdd-file-row">
                          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>
                          <span>{filePath}</span>
                        </div>
                      ))}
                      <div
                        className="ls2-rdd-file-row ls2-rdd-file-md"
                        style={{ cursor: 'pointer' }}
                        onClick={() => navigate('/report')}
                        role="button"
                        tabIndex={0}
                        onKeyDown={e => e.key === 'Enter' && navigate('/report')}
                        title="Open full markdown report"
                      >
                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0-2 2V8z"/><polyline points="14 2 20 8"/></svg>
                        <span style={{ flex: 1 }}>bug_report.md</span>
                        <span className="ls2-rdd-md-badge">View Full Report ↓</span>
                      </div>
                    </div>
                  </div>

                  <div className="ls2-outcome-actions">
                    <button className="ls2-btn-primary" onClick={() => navigate('/report')}>
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                      View Full Report
                    </button>
                    <a href={prUrl || `https://github.com/${runRepo}/pull/73`} target="_blank" rel="noopener noreferrer" className="ls2-pr-link">
                      View Pull Request on GitHub
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="7" y1="17" x2="17" y2="7"/><polyline points="7 7 17 7 17 17"/></svg>
                    </a>
                    <button className="ls2-btn-outline" onClick={handleBack}>Reconfigure Run</button>
                  </div>
                </div>
              </div>
            )}

            {/* OUTCOME — failed */}
            {pipelineStatus === 'failed' && (
              <div className="ls2-outcome ls2-outcome-fail">
                <div className="ls2-outcome-orb orb-fail" />
                <div className="ls2-outcome-body">
                  <div className="ls2-outcome-head">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                    {backendOnline ? 'Repair Execution Failed' : 'Backend Offline'}
                  </div>
                  <p className="ls2-outcome-desc">
                    {backendOnline
                      ? 'Test suite failed verification after patch was applied.'
                      : 'Cannot reach the 4o4PR backend. Run: uvicorn app.main:app --reload from the backend directory.'}
                  </p>
                  <div className="ls2-outcome-actions">
                    <button className="ls2-btn-outline" onClick={handleBack}>Modify Configuration</button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
