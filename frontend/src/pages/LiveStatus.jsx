import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { PIPELINE_STEPS } from '../data/mockPipeline';
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
  let prefix = null;

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

/* ── ROOT CAUSE ── extracted from logs ── */
const ROOT_CAUSE_SNIPPETS = [
  '"The failure stems from an unprotected endpoint — the route handler lacks the @login_required decorator, allowing unauthenticated requests to succeed with HTTP 200 instead of returning 401."',
  '"Connection timeouts arise because the socket timeout is set to None, causing the pool to wait indefinitely. Setting an explicit 30-second limit resolves the deadlock."',
  '"Unclosed WebSocket sockets accumulate in the pool because close_pool() never iterates over open connections. Explicit iteration and clearing the pool at teardown eliminates the leak."',
];

export default function LiveStatus({ activeRun, onResetRun }) {
  const navigate  = useNavigate();
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [pipelineStatus,   setPipelineStatus]   = useState('idle');
  const [consoleLogs,      setConsoleLogs]       = useState([]);
  const [progress,         setProgress]          = useState(0);
  const [rootCause,        setRootCause]         = useState('');
  const [paused,           setPaused]            = useState(false);

  const logsQueueRef   = useRef([]);
  const logIntervalRef = useRef(null);
  const logBodyRef     = useRef(null);

  const runRepo   = activeRun?.repo   || 'AnshPandey18/4o4PR';
  const runBug    = activeRun?.bug    || 'Issue #404: pytest failure in auth module';
  const shouldFail = activeRun?.shouldFail || false;
  const jobId     = 'PA-' + Math.floor(Math.random() * 9000 + 1000) + '-X';

  const timer = useElapsedTimer(pipelineStatus === 'running' && !paused);

  const processLine = l => l.replace(/{REPO}/g, runRepo).replace(/{BUG}/g, runBug);

  const failureLogs = [
    'Spawning docker container (python:3.10-alpine)...',
    'Applying patch to src/core/router.py...',
    'Running command: pytest tests/',
    '============================= test session starts =============================',
    'platform linux -- Python 3.10.8, pytest-7.2.1, pluggy-1.0.0',
    'rootdir: /app', 'collected 3 items', '',
    'tests/test_core.py ..F                                                   [100%]', '',
    '================================== FAILURES ===================================',
    'E       AssertionError: assert 500 == 401',
    '=========================== 1 failed, 2 passed in 1.34s ===========================',
    'ERROR: Pytest validation check failed after patch application.',
    'Fix verification status: FAILED.',
  ];

  const startSimulation = () => {
    clearInterval(logIntervalRef.current);
    setCurrentStepIndex(0); setPipelineStatus('running');
    setConsoleLogs([`[INFO] Starting patch workflow for: ${runRepo}...`]);
    setProgress(5); setRootCause(''); setPaused(false);
    logsQueueRef.current = [...PIPELINE_STEPS[0].logs.map(processLine)];
  };

  /* auto-start */
  useEffect(() => { startSimulation(); return () => clearInterval(logIntervalRef.current); }, [activeRun]);

  /* auto-scroll logs */
  useEffect(() => {
    if (logBodyRef.current) logBodyRef.current.scrollTop = logBodyRef.current.scrollHeight;
  }, [consoleLogs]);

  /* set root-cause when detect step finishes */
  useEffect(() => {
    if (currentStepIndex >= 1 && !rootCause) {
      setRootCause(ROOT_CAUSE_SNIPPETS[Math.floor(Math.random() * ROOT_CAUSE_SNIPPETS.length)]);
    }
  }, [currentStepIndex]);

  /* simulation tick */
  useEffect(() => {
    if (pipelineStatus !== 'running') return;
    logIntervalRef.current = setInterval(() => {
      if (paused) return;
      if (logsQueueRef.current.length > 0) {
        const next = logsQueueRef.current.shift();
        setConsoleLogs(p => [...p, next]);
        setProgress(() => {
          const base = (currentStepIndex / PIPELINE_STEPS.length) * 100;
          const size = 100 / PIPELINE_STEPS.length;
          const sub  = (1 - (logsQueueRef.current.length / (PIPELINE_STEPS[currentStepIndex].logs.length || 10))) * size;
          return Math.min(Math.round(base + sub), 98);
        });
      } else {
        clearInterval(logIntervalRef.current);
        const isLast = currentStepIndex === PIPELINE_STEPS.length - 1;
        if (shouldFail && currentStepIndex === 3) {
          setPipelineStatus('failed');
          setConsoleLogs(p => [...p, ...failureLogs.map(processLine)]);
          setProgress(65);
        } else if (isLast) {
          setPipelineStatus('completed'); setProgress(100);
        } else {
          const next = currentStepIndex + 1;
          setCurrentStepIndex(next);
          logsQueueRef.current = [...PIPELINE_STEPS[next].logs.map(processLine)];
          setConsoleLogs(p => [...p, `\n[STATUS] ── ${PIPELINE_STEPS[next].name} ──`]);
        }
      }
    }, 220);
    return () => clearInterval(logIntervalRef.current);
  }, [pipelineStatus, currentStepIndex, shouldFail, paused]);

  const handleBack = () => { onResetRun?.(); navigate('/run'); };

  /* step display info */
  const stepOf = `Step ${Math.min(currentStepIndex + 1, PIPELINE_STEPS.length)} of ${PIPELINE_STEPS.length}`;

  return (
    <div className="ls2-page">
      {/* terminal grid bg */}
      <div className="ls2-grid-bg" />

      {/* ── STICKY PROGRESS BAR ── */}
      <div className="ls2-progress-rail">
        <div
          className={`ls2-progress-fill ${pipelineStatus === 'completed' ? 'ls2-fill-done' : pipelineStatus === 'failed' ? 'ls2-fill-fail' : ''}`}
          style={{ width: `${progress}%` }}
        />
      </div>

      <div className="ls2-wrap">

        {/* ── PAGE EYEBROW ── */}
        <section className="ls2-eyebrow-section">
          <div className="ls2-eyebrow-left">
            <div className="ls2-eyebrow-chips">
              <span className={`ls2-live-chip ${pipelineStatus === 'running' ? 'chip-running' : pipelineStatus === 'completed' ? 'chip-done' : pipelineStatus === 'failed' ? 'chip-fail' : ''}`}>
                {pipelineStatus === 'running' && <span className="ls2-chip-dot" />}
                {pipelineStatus === 'running' ? 'Live Run' : pipelineStatus === 'completed' ? 'Completed' : pipelineStatus === 'failed' ? 'Failed' : 'Idle'}
              </span>
              <span className="ls2-job-id">/ Job #{jobId}</span>
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

        {/* ── MAIN CONTENT GRID ── */}
        <div className="ls2-main-grid">

          {/* ── LEFT: PIPELINE TRACKER ── */}
          <div className="ls2-left">
            <div className="ls2-card">
              <div className="ls2-card-head">
                <h2 className="ls2-card-title">Execution Pipeline</h2>
                <span className="ls2-step-of">{stepOf}</span>
              </div>

              <div className="ls2-steps">
                {/* vertical spine */}
                <div className="ls2-spine" />

                {PIPELINE_STEPS.map((step, idx) => {
                  const done   = idx < currentStepIndex && pipelineStatus !== 'failed';
                  const active = idx === currentStepIndex && pipelineStatus === 'running';
                  const failed = idx === currentStepIndex && pipelineStatus === 'failed';
                  const pending = idx > currentStepIndex || pipelineStatus === 'idle';

                  return (
                    <div key={step.id} className={`ls2-step ${done ? 'step-done' : active ? 'step-active' : failed ? 'step-fail' : 'step-pending'}`}>
                      {/* node */}
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
                        {/* active ring */}
                        {active && <div className="ls2-node-ring" />}
                      </div>

                      {/* content */}
                      <div className="ls2-step-content">
                        <div className="ls2-step-top">
                          <span className="ls2-step-name">{step.name}</span>
                          {active && (
                            <span className="ls2-running-badge">
                              <span className="ls2-running-dot" />RUNNING
                            </span>
                          )}
                          {done && <span className="ls2-done-badge">DONE</span>}
                          {failed && <span className="ls2-fail-badge">FAILED</span>}
                        </div>
                        <p className="ls2-step-desc">{step.description}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* ── RIGHT: LOG + ROOT CAUSE + OUTCOME ── */}
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

            {/* root cause card */}
            {rootCause && (
              <div className="ls2-card ls2-card-blush ls2-root-cause">
                <div className="ls2-rc-head">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                  ROOT CAUSE EXPLANATION
                </div>
                <p className="ls2-rc-text">{rootCause}</p>
              </div>
            )}

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
                  <div className="ls2-outcome-actions">
                    <a href={`https://github.com/${runRepo}/pull/73`} target="_blank" rel="noopener noreferrer" className="ls2-pr-link">
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
                    Repair Execution Failed
                  </div>
                  <p className="ls2-outcome-desc">Test suite failed verification after patch was applied. Pytest exited with non-zero code.</p>
                  <div className="ls2-outcome-actions">
                    <button className="ls2-btn-primary" onClick={startSimulation}>Retry Patch Run</button>
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
