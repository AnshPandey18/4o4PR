import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { triggerPipelineRun } from '../api/pipelineRuns';
import { getRepositories } from '../api/repositories';
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
  healthIndex: '—',
  coverage: '—',
  activeTests: '—',
  prSuccessRate: '—',
  avgRepairTime: '—',
  activeBranch: '—',
  status: 'Ready',
};

/* ─── component ─────────────────────────────────────────────────────────── */
export default function TriggerRun({ onStartRun }) {
  const [configTab,    setConfigTab]    = useState('branch'); // 'branch' | 'pr' | 'commit'
  const [selectedRepo, setSelectedRepo] = useState(null);
  const [repositories, setRepositories] = useState([]);
  const [branchInput,  setBranchInput]  = useState('');
  const [prUrl,        setPrUrl]        = useState('');
  const [commitHash,   setCommitHash]   = useState('');
  const [launching,    setLaunching]    = useState(false);
  const [error,        setError]        = useState(null);
  const navigate = useNavigate();
  const pageRef  = useRef(null);

  // Success message
  const [repoSuccess, setRepoSuccess] = useState(null);

  const repoStats = selectedRepo ? {
    healthIndex: '—',
    coverage: '—',
    activeTests: '—',
    prSuccessRate: '—',
    avgRepairTime: '—',
    activeBranch: selectedRepo.default_branch || 'main',
    status: 'Ready',
  } : DEMO_REPO_STATS;

  // Fetch repositories on mount
  useEffect(() => {
    const fetchRepos = async () => {
      try {
        const data = await getRepositories();
        setRepositories(data.repositories || []);
      } catch (err) {
        console.error('Failed to fetch repositories:', err);
      }
    };
    fetchRepos();
  }, []);

  // Form validation
  const canSubmit = 
    (configTab === 'branch' && selectedRepo && (branchInput || selectedRepo.default_branch)) ||
    (configTab === 'pr' && prUrl.trim()) ||
    (configTab === 'commit' && selectedRepo && commitHash.trim());

  /* ─── Form submission ─────────────────────────────────────────────────── */
  const handleRunPipeline = async (e) => {
    e.preventDefault();

    if (launching) return;

    setLaunching(true);
    setError(null);
    setRepoSuccess(null);

    try {
      let payload = {};
      
      // Branch Mode
      if (configTab === 'branch') {
        if (!selectedRepo) {
          setError('Please select a repository');
          setLaunching(false);
          return;
        }
        
        payload = {
          repository_id: selectedRepo.id,
          input_mode: 'branch',
          input_ref: branchInput || selectedRepo.default_branch || 'main',
          verbose: true,
        };
      }
      
      // Pull Request Mode
      else if (configTab === 'pr') {
        if (!prUrl.trim()) {
          setError('Please enter a pull request URL');
          setLaunching(false);
          return;
        }
        
        payload = {
          input_mode: 'pr',
          input_ref: prUrl.trim(),
          verbose: true,
        };
      }
      
      // Commit Hash Mode
      else if (configTab === 'commit') {
        if (!selectedRepo) {
          setError('Please select a repository');
          setLaunching(false);
          return;
        }
        if (!commitHash.trim()) {
          setError('Please enter a commit hash');
          setLaunching(false);
          return;
        }
        
        payload = {
          repository_id: selectedRepo.id,
          input_mode: 'commit',
          input_ref: commitHash.trim(),
          verbose: true,
        };
      }

      console.log('🚀 Triggering pipeline run...', payload);
      const runData = await triggerPipelineRun(payload);

      const runId = runData.run_id;
      const repositoryName = selectedRepo?.full_name || 'Repository';

      console.log('✓ Pipeline started:', { runId });

      setRepoSuccess(`Pipeline started (Run ID: ${runId}). Tracking execution status…`);

      // Hand the run to the status page
      onStartRun({
        repo: repositoryName,
        bug: `${configTab.toUpperCase()} Mode: ${payload.input_ref}`,
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

  useEffect(() => {
    const h = e => { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') handleRunPipeline(e); };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [configTab, selectedRepo, branchInput, prUrl, commitHash]);

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

                {/* ── Configuration tabs (Branch / PR / Commit Hash) ── */}
                <div className="tr2-config-tabs">
                  <button
                    type="button"
                    className={`tr2-config-tab ${configTab === 'branch' ? 'tr2-config-tab-active' : ''}`}
                    onClick={() => setConfigTab('branch')}
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="6" y1="3" x2="6" y2="15"></line><circle cx="18" cy="6" r="3"></circle><circle cx="6" cy="18" r="3"></circle><path d="M18 9a9 9 0 0 1-9 9"></path>
                    </svg>
                    Branch
                  </button>
                  <button
                    type="button"
                    className={`tr2-config-tab ${configTab === 'pr' ? 'tr2-config-tab-active' : ''}`}
                    onClick={() => setConfigTab('pr')}
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="18" cy="18" r="3"></circle><circle cx="6" cy="6" r="3"></circle><path d="M13 6h3a2 2 0 0 1 2 2v7"></path><line x1="6" y1="9" x2="6" y2="21"></line>
                    </svg>
                    Pull Request
                  </button>
                  <button
                    type="button"
                    className={`tr2-config-tab ${configTab === 'commit' ? 'tr2-config-tab-active' : ''}`}
                    onClick={() => setConfigTab('commit')}
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="12" cy="12" r="4"></circle><line x1="1.05" y1="12" x2="7" y2="12"></line><line x1="17.01" y1="12" x2="22.96" y2="12"></line>
                    </svg>
                    Commit Hash
                  </button>
                </div>

                {/* ── Configuration forms ── */}
                <div className="tr2-repo-form">
                  {/* Branch Tab */}
                  {configTab === 'branch' && (
                    <>
                      {/* Repository Dropdown */}
                      <div className="tr2-field">
                        <label htmlFor="repo-select" className="tr2-label">Repository</label>
                        <div className="tr2-select-wrap">
                          <select
                            id="repo-select"
                            className="tr2-select"
                            value={selectedRepo?.id || ''}
                            onChange={(e) => {
                              if (e.target.value === 'add-new') {
                                navigate('/repositories');
                              } else {
                                const repo = repositories.find(r => r.id === parseInt(e.target.value));
                                setSelectedRepo(repo);
                              }
                            }}
                            disabled={launching}
                          >
                            <option value="">Select a repository...</option>
                            {repositories.map(repo => (
                              <option key={repo.id} value={repo.id}>
                                {repo.full_name}
                              </option>
                            ))}
                            <option value="add-new">➕ Add new repository</option>
                          </select>
                          <span className="tr2-chevron">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <polyline points="6 9 12 15 18 9"/>
                            </svg>
                          </span>
                        </div>
                      </div>

                      {/* Branch */}
                      <div className="tr2-field">
                        <label htmlFor="branch-input" className="tr2-label">Branch</label>
                        <input
                          id="branch-input"
                          type="text"
                          className="tr2-input"
                          placeholder={selectedRepo?.default_branch || "main"}
                          value={branchInput}
                          onChange={(e) => setBranchInput(e.target.value)}
                          disabled={launching || !selectedRepo}
                        />
                      </div>
                    </>
                  )}

                  {/* Pull Request Tab */}
                  {configTab === 'pr' && (
                    <>
                      {/* PR URL */}
                      <div className="tr2-field">
                        <label htmlFor="pr-url" className="tr2-label">Pull Request URL</label>
                        <input
                          id="pr-url"
                          type="text"
                          className="tr2-input"
                          placeholder="https://github.com/owner/repo/pull/123"
                          value={prUrl}
                          onChange={(e) => setPrUrl(e.target.value)}
                          disabled={launching}
                        />
                        <span className="tr2-hint">
                          The repository will be automatically added if it doesn't exist.
                        </span>
                      </div>
                    </>
                  )}

                  {/* Commit Hash Tab */}
                  {configTab === 'commit' && (
                    <>
                      {/* Repository Dropdown */}
                      <div className="tr2-field">
                        <label htmlFor="commit-repo-select" className="tr2-label">Repository</label>
                        <div className="tr2-select-wrap">
                          <select
                            id="commit-repo-select"
                            className="tr2-select"
                            value={selectedRepo?.id || ''}
                            onChange={(e) => {
                              if (e.target.value === 'add-new') {
                                navigate('/repositories');
                              } else {
                                const repo = repositories.find(r => r.id === parseInt(e.target.value));
                                setSelectedRepo(repo);
                              }
                            }}
                            disabled={launching}
                          >
                            <option value="">Select a repository...</option>
                            {repositories.map(repo => (
                              <option key={repo.id} value={repo.id}>
                                {repo.full_name}
                              </option>
                            ))}
                            <option value="add-new">➕ Add new repository</option>
                          </select>
                          <span className="tr2-chevron">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <polyline points="6 9 12 15 18 9"/>
                            </svg>
                          </span>
                        </div>
                      </div>

                      {/* Commit Hash */}
                      <div className="tr2-field">
                        <label htmlFor="commit-hash" className="tr2-label">Commit Hash</label>
                        <input
                          id="commit-hash"
                          type="text"
                          className="tr2-input"
                          placeholder="abc123... (full or short SHA)"
                          value={commitHash}
                          onChange={(e) => setCommitHash(e.target.value)}
                          disabled={launching || !selectedRepo}
                        />
                        <span className="tr2-hint">
                          The hash will be validated and expanded to the full 40-character SHA.
                        </span>
                      </div>
                    </>
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
                        Run Pipeline
                      </>
                    )}
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

            <div className="tr2-card">
              <div className="tr2-card-heading">
                <span className="tr2-card-dot" />
                <h2 className="tr2-card-title">Runtime Settings</h2>
              </div>
              <div className="tr2-settings">
                {RUNTIME_SETTINGS.map(s => (
                  <div key={s.key} className="tr2-setting-row">
                    <span className="tr2-setting-key">{s.key}</span>
                    <span className="tr2-setting-val">{s.val}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
