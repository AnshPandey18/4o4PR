import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { MOCK_BUGS, MOCK_REPO_STATS } from '../data/mockPipeline';
import { startRun, startDemoRun } from '../services/api';
import RepositoryManager from '../components/RepositoryManager';
import RunHistory from '../components/RunHistory';
import { triggerPipelineRun } from '../api/pipelineRuns';
import { onboardRepository } from '../api/repositories';
import './TriggerRun.css';

/* ─── constants ─────────────────────────────────────────────────────────── */
const REPO_DRAFT_KEY = '4o4pr.repositoryDraft';
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
  const [sourceMode,   setSourceMode]   = useState('demo');   // 'demo' | 'github' | 'managed'
  const [selectedBug,  setSelectedBug]  = useState(MOCK_BUGS[0].id);
  const [selectedRepo, setSelectedRepo] = useState(null);
  const [launching,    setLaunching]    = useState(false);
  const [error,        setError]        = useState(null);
  const navigate = useNavigate();
  const pageRef  = useRef(null);

  // GitHub Repos form state (for managed mode)
  const [visibility, setVisibility] = useState('public'); // 'public' | 'private'
  const [repoFormData, setRepoFormData] = useState({
    url: '',
    branch: 'main',
    personal_access_token: '',
  });
  const [showToken, setShowToken] = useState(false);
  const [repoValidationErrors, setRepoValidationErrors] = useState({});
  const [repoSuccess, setRepoSuccess] = useState(null);
  const [draftSaved, setDraftSaved] = useState(false);

  const activeBug  = MOCK_BUGS.find(b => b.id === selectedBug) || MOCK_BUGS[0];
  const repoStats  = sourceMode === 'demo' ? DEMO_REPO_STATS : (MOCK_REPO_STATS['AnshPandey18/4o4PR'] || {});
  const sevColor   = { High: '#e6714f', Medium: '#ffb764', Low: '#20c2a4' }[activeBug.severity] || '#888';

  // The Run Pipeline button is enabled as soon as the required fields hold
  // valid values, so a repository URL can be submitted directly.
  const managedFormReady = sourceMode !== 'managed' || Boolean(
    repoFormData.url.trim() &&
    repoFormData.branch.trim() &&
    (visibility === 'public' || repoFormData.personal_access_token.trim())
  );
  const canSubmit = managedFormReady;

  /* ─── restore a previously saved draft (never includes a token) ─────── */
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(REPO_DRAFT_KEY);
      if (!raw) return;
      const draft = JSON.parse(raw);
      setRepoFormData(prev => ({
        ...prev,
        url: draft.url || '',
        branch: draft.branch || 'main',
      }));
      if (draft.visibility === 'private' || draft.visibility === 'public') {
        setVisibility(draft.visibility);
      }
    } catch {
      /* a malformed draft must never block the form */
    }
  }, []);

  /* ─── clear token when switching from private to public ────────────────── */
  useEffect(() => {
    if (visibility === 'public') {
      setRepoFormData(prev => ({ ...prev, personal_access_token: '' }));
      setShowToken(false);
      setRepoValidationErrors(prev => ({ ...prev, personal_access_token: undefined }));
    }
  }, [visibility]);

  /* ─── GitHub Repos validation helpers ──────────────────────────────────── */
  const validateUrl = (url) => {
    if (!url.trim()) return 'Repository URL is required';
    const githubPattern = /^(https?:\/\/)?(www\.)?github\.com\/[\w-]+\/[\w.-]+\/?$/;
    const shortPattern = /^[\w-]+\/[\w.-]+$/;
    if (!githubPattern.test(url) && !shortPattern.test(url)) {
      return 'Please enter a valid GitHub repository URL';
    }
    return null;
  };

  const validateBranch = (branch) => {
    if (!branch.trim()) return 'Branch name is required';
    return null;
  };

  const validateToken = (token) => {
    if (visibility === 'private' && !token.trim()) {
      return 'Personal access token is required for private repositories';
    }
    return null;
  };

  const handleRepoInputChange = (field, value) => {
    setRepoFormData(prev => ({ ...prev, [field]: value }));
    setRepoValidationErrors(prev => ({ ...prev, [field]: undefined }));
    setError(null);
    setRepoSuccess(null);
  };

  /* ─── GitHub Repos form submission ─────────────────────────────────────── */
  const handleRunPipeline = async (e) => {
    e.preventDefault();

    // Validate form only for managed mode
    if (sourceMode !== 'managed') {
      // Let the original handleSubmit handle demo/github modes
      return handleSubmit(e);
    }

    // Validate managed mode form
    const errors = {
      url: validateUrl(repoFormData.url),
      branch: validateBranch(repoFormData.branch),
      personal_access_token: validateToken(repoFormData.personal_access_token),
    };

    Object.keys(errors).forEach(key => {
      if (errors[key] === null) delete errors[key];
    });

    if (Object.keys(errors).length > 0) {
      setRepoValidationErrors(errors);
      return;
    }

    if (launching) return;

    setLaunching(true);
    setError(null);
    setRepoSuccess(null);

    try {
      // Step 1: Onboard the repository and start the pipeline run.
      // The backend clones the repository and executes the pipeline in the
      // background; it returns as soon as both database records exist.
      const payload = {
        url: repoFormData.url,
        branch: repoFormData.branch,
        visibility,
      };

      if (visibility === 'private') {
        payload.personal_access_token = repoFormData.personal_access_token;
      }

      console.log('🚀 Onboarding repository...', { url: payload.url, branch: payload.branch, visibility });
      const onboarded = await onboardRepository(payload);

      const repositoryId = onboarded.repository_id;
      const runId = onboarded.run_id;
      const repositoryName = onboarded.repository?.name || repoFormData.url;

      console.log('✓ Repository registered, pipeline queued:', { repositoryId, runId });

      // The pipeline is still running: report it as started, never as finished.
      setRepoSuccess(`Pipeline started (Run ID: ${runId}). Tracking execution status…`);

      // Hand the run to the status page, which polls the real backend state.
      onStartRun({
        repo: repositoryName,
        bug: 'Repository Analysis',
        runId,
        source: 'pipeline',
      });

      navigate('/status');

    } catch (err) {
      console.error('❌ Pipeline failed:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to start pipeline.';
      setError(errorMessage);
    } finally {
      setLaunching(false);
    }
  };

  /* ─── Save Draft ──────────────────────────────────────────────────────── */
  const handleSaveDraft = () => {
    try {
      // The access token is deliberately excluded from the draft payload.
      window.localStorage.setItem(REPO_DRAFT_KEY, JSON.stringify({
        url: repoFormData.url,
        branch: repoFormData.branch,
        visibility,
        savedAt: new Date().toISOString(),
      }));
      setDraftSaved(true);
      setTimeout(() => setDraftSaved(false), 3000);
    } catch {
      setError('Could not save the draft in this browser.');
    }
  };

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
      } else if (sourceMode === 'managed' && selectedRepo) {
        // Use the new managed repository flow
        runData = await triggerPipelineRun({
          repository_id: selectedRepo.id,
          verbose: true,
          force_reclone: false
        });
      } else {
        runData = await startRun({
          repo: 'AnshPandey18/4o4PR',
          bug: activeBug.title,
          branch: 'main',
        });
      }
      onStartRun({
        repo: sourceMode === 'demo' 
          ? 'demo/sample_bugs' 
          : sourceMode === 'managed' 
          ? selectedRepo?.name || 'managed repo'
          : 'AnshPandey18/4o4PR',
        bug:  sourceMode === 'demo'
          ? 'Demo: sample_bugs fixture (calculator + string_utils)'
          : sourceMode === 'managed'
          ? 'Managed Repository Analysis'
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

              <form onSubmit={handleRunPipeline} className="tr2-form">

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
                    Demo Fixture
                  </button>
                  <button
                    type="button"
                    className={`tr2-source-tab ${sourceMode === 'managed' ? 'tr2-source-tab-active' : ''}`}
                    onClick={() => setSourceMode('managed')}
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>
                    </svg>
                    GitHub Repos
                  </button>
                  <button
                    type="button"
                    className={`tr2-source-tab ${sourceMode === 'github' ? 'tr2-source-tab-active' : ''}`}
                    onClick={() => setSourceMode('github')}
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/>
                    </svg>
                    Issues/PRs
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

                {/* ── managed/GitHub Repos mode ── */}
                {sourceMode === 'managed' && (
                  <div className="tr2-managed-section">
                    <div className="tr2-repo-form">
                      
                      {/* Visibility Dropdown */}
                      <div className="tr2-field">
                        <label htmlFor="visibility" className="tr2-label">Visibility</label>
                        <div className="tr2-select-wrap">
                          <select
                            id="visibility"
                            className="tr2-select"
                            value={visibility}
                            onChange={(e) => setVisibility(e.target.value)}
                          >
                            <option value="public">Public</option>
                            <option value="private">Private</option>
                          </select>
                          <span className="tr2-chevron">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <polyline points="6 9 12 15 18 9"/>
                            </svg>
                          </span>
                        </div>
                      </div>

                      {/* Repository URL */}
                      <div className="tr2-field">
                        <label htmlFor="repo-url" className="tr2-label">GitHub Repository URL</label>
                        <input
                          id="repo-url"
                          type="text"
                          className={`tr2-input ${repoValidationErrors.url ? 'tr2-input-error' : ''}`}
                          placeholder="https://github.com/owner/repository"
                          value={repoFormData.url}
                          onChange={(e) => handleRepoInputChange('url', e.target.value)}
                          disabled={launching}
                        />
                        {repoValidationErrors.url && (
                          <span className="tr2-error-text">{repoValidationErrors.url}</span>
                        )}
                      </div>

                      {/* Branch */}
                      <div className="tr2-field">
                        <label htmlFor="repo-branch" className="tr2-label">Branch</label>
                        <input
                          id="repo-branch"
                          type="text"
                          className={`tr2-input ${repoValidationErrors.branch ? 'tr2-input-error' : ''}`}
                          placeholder="main"
                          value={repoFormData.branch}
                          onChange={(e) => handleRepoInputChange('branch', e.target.value)}
                          disabled={launching}
                        />
                        {repoValidationErrors.branch && (
                          <span className="tr2-error-text">{repoValidationErrors.branch}</span>
                        )}
                      </div>

                      {/* Personal Access Token (Private only) */}
                      {visibility === 'private' && (
                        <div className="tr2-field tr2-token-field">
                          <label htmlFor="repo-token" className="tr2-label">
                            GitHub Personal Access Token
                            <span className="tr2-required-badge">Required</span>
                          </label>
                          <div className="tr2-token-input-wrap">
                            <input
                              id="repo-token"
                              type={showToken ? 'text' : 'password'}
                              className={`tr2-input ${repoValidationErrors.personal_access_token ? 'tr2-input-error' : ''}`}
                              placeholder="ghp_xxxxxxxxxxxx"
                              value={repoFormData.personal_access_token}
                              onChange={(e) => handleRepoInputChange('personal_access_token', e.target.value)}
                              disabled={launching}
                              autoComplete="off"
                            />
                            <button
                              type="button"
                              className="tr2-token-toggle"
                              onClick={() => setShowToken(!showToken)}
                              title={showToken ? 'Hide token' : 'Show token'}
                            >
                              {showToken ? (
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
                                  <line x1="1" y1="1" x2="23" y2="23"/>
                                </svg>
                              ) : (
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                                  <circle cx="12" cy="12" r="3"/>
                                </svg>
                              )}
                            </button>
                          </div>
                          {repoValidationErrors.personal_access_token && (
                            <span className="tr2-error-text">{repoValidationErrors.personal_access_token}</span>
                          )}
                          <span className="tr2-hint">
                            A token with repository read permissions is required. Your token is encrypted and stored securely.
                          </span>
                        </div>
                      )}

                      {/* Success Banner */}
                      {repoSuccess && (
                        <div className="tr2-success-banner">
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                            <polyline points="22 4 12 14.01 9 11.01"/>
                          </svg>
                          {repoSuccess}
                        </div>
                      )}

                    </div>
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
                  <button 
                    type="submit" 
                    className="tr2-btn-primary" 
                    disabled={launching || !canSubmit}
                  >
                    {launching ? (
                      <><span className="tr2-spinner" />Initializing…</>
                    ) : (
                      <>
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                        {sourceMode === 'demo' ? 'Run Demo Pipeline' : 'Run Pipeline'}
                      </>
                    )}
                  </button>
                  <button type="button" className="tr2-btn-outline" onClick={handleSaveDraft}>
                    {draftSaved ? 'Draft Saved' : 'Save Draft'}
                  </button>
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

        {/* ── RUN HISTORY SECTION ── */}
        <section className="tr2-history-section">
          <RunHistory 
            repositoryId={selectedRepo?.id} 
            autoRefresh={true}
            refreshInterval={5000}
          />
        </section>
      </div>
    </div>
  );
}
