import { useState, useEffect } from 'react';
import { getRepositories, createRepository, updateRepository, deleteRepository, fetchRepositoryInfo } from '../api/repositories';
import { getCredentials } from '../api/credentials';
import './Repositories.css';

// GitHub API base URL
const GITHUB_API_BASE = 'https://api.github.com/repos';

/**
 * Parse GitHub URL to extract owner and repo
 * Accepts various formats:
 * - https://github.com/owner/repo
 * - https://github.com/owner/repo/
 * - https://github.com/owner/repo.git
 * - git@github.com:owner/repo.git
 * - owner/repo
 */
const parseGitHubUrl = (url) => {
  const trimmed = url.trim();
  
  // Pattern 1: git@github.com:owner/repo.git
  if (trimmed.startsWith('git@github.com:')) {
    const match = trimmed.match(/git@github\.com:([^/]+)\/(.+?)(\.git)?$/);
    if (match) {
      return { owner: match[1], repo: match[2] };
    }
  }
  
  // Pattern 2: https://github.com/owner/repo(.git)?
  if (trimmed.includes('github.com/')) {
    const match = trimmed.match(/github\.com\/([^/]+)\/([^/]+?)(\.git)?\/?$/);
    if (match) {
      return { owner: match[1], repo: match[2] };
    }
  }
  
  // Pattern 3: owner/repo
  if (trimmed.includes('/') && !trimmed.includes('://')) {
    const parts = trimmed.split('/');
    if (parts.length === 2) {
      return { owner: parts[0], repo: parts[1].replace('.git', '') };
    }
  }
  
  return null;
};

/**
 * Fetch repository information from GitHub API
 */
const fetchGitHubRepoInfo = async (owner, repo, token = null) => {
  const url = `${GITHUB_API_BASE}/${owner}/${repo}`;
  const headers = {};
  
  if (token) {
    headers.Authorization = `token ${token}`;
  }
  
  const response = await fetch(url, { headers });
  
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('Repository not found on GitHub, Try adding your Repository on the PAT Token in the dashboard');
    } else if (response.status === 401) {
      throw new Error('Invalid or expired token');
    } else {
      throw new Error(`GitHub API error: ${response.status}`);
    }
  }
  
  const data = await response.json();
  
  // GitHub redirects return the new full_name
  return {
    full_name: data.full_name, // May differ from input if renamed
    description: data.description || '',
    github_id: data.id,
    default_branch: data.default_branch || 'main',
    is_private: data.private,
  };
};

export default function Repositories() {
  const [repositories, setRepositories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingRepo, setEditingRepo] = useState(null);
  const [storedPAT, setStoredPAT] = useState(null); // Stored PAT from dashboard
  
  // Form state
  const [formData, setFormData] = useState({
    url: '',
    token: '',
    description: '',
  });
  const [formError, setFormError] = useState('');
  const [formSuccess, setFormSuccess] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [showToken, setShowToken] = useState(false);
  const [fetchingGitHub, setFetchingGitHub] = useState(false);
  const [githubInfo, setGithubInfo] = useState(null);

  // Fetch repositories and stored PAT on mount
  useEffect(() => {
    loadRepositories();
    loadStoredPAT();
  }, []);

  const loadStoredPAT = async () => {
    try {
      const creds = await getCredentials();
      if (creds && creds.is_active) {
        // We don't get the actual token, but we know one exists
        setStoredPAT({ exists: true, last4: creds.token_last4 });
      }
    } catch (err) {
      // No stored PAT - user needs to add one in dashboard for private repos
      console.log('No stored PAT found');
    }
  };

  const loadRepositories = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getRepositories();
      setRepositories(data.repositories || []);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load repositories');
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    setFormError('');
    setFormSuccess('');
    
    // If URL changes, reset GitHub info
    if (field === 'url') {
      setGithubInfo(null);
    }
  };

  const handleFetchFromGitHub = async () => {
    if (!formData.url.trim()) {
      setFormError('Please enter a repository URL');
      return;
    }

    const parsed = parseGitHubUrl(formData.url);
    if (!parsed) {
      setFormError('Invalid GitHub URL format');
      return;
    }

    setFetchingGitHub(true);
    setFormError('');
    setFormSuccess('');
    
    try {
      // Call backend to fetch repo info - backend will use stored PAT if available
      const info = await fetchRepositoryInfo(formData.url);
      
      // Transform backend response to match expected format
      const repoInfo = {
        full_name: info.full_name,
        description: info.description || '',
        github_id: info.github_id,
        default_branch: info.default_branch || 'main',
        is_private: info.is_private || false,
      };
      
      setGithubInfo(repoInfo);
      
      // Auto-fill description if fetched and not already set
      if (repoInfo.description && !formData.description) {
        setFormData(prev => ({ ...prev, description: repoInfo.description }));
      }
      
      setFormSuccess('Repository information fetched from GitHub');
    } catch (err) {
      const errorMsg = err.response?.data?.detail || err.message || 'Failed to fetch repository info';
      setFormError(errorMsg);
      setGithubInfo(null);
    } finally {
      setFetchingGitHub(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.url.trim()) {
      setFormError('Repository URL is required');
      return;
    }

    const parsed = parseGitHubUrl(formData.url);
    if (!parsed) {
      setFormError('Invalid GitHub URL format');
      return;
    }

    setSubmitting(true);
    setFormError('');
    setFormSuccess('');

    try {
      // If we don't have repo info yet, fetch it first
      let repoInfo = githubInfo;
      if (!repoInfo) {
        try {
          const info = await fetchRepositoryInfo(formData.url);
          repoInfo = {
            full_name: info.full_name,
            description: info.description || '',
            github_id: info.github_id,
            default_branch: info.default_branch || 'main',
            is_private: info.is_private || false,
          };
          setGithubInfo(repoInfo);
        } catch (err) {
          // If fetch fails, use minimal info and let backend handle it
          console.log('Could not fetch repo info, proceeding with minimal data');
          repoInfo = {
            full_name: `${parsed.owner}/${parsed.repo}`,
            description: formData.description || '',
            is_private: false,
            default_branch: 'main'
          };
        }
      }

      // Create the repository - backend will use stored PAT
      const payload = {
        url: `https://github.com/${repoInfo.full_name}`,
        description: formData.description || repoInfo.description || '',
        branch: repoInfo.default_branch || 'main',
      };

      // Only include PAT if user explicitly provided one (for updating stored PAT)
      if (formData.token.trim()) {
        payload.personal_access_token = formData.token.trim();
      }

      if (editingRepo) {
        // Update existing
        await updateRepository(editingRepo.id, {
          description: payload.description,
        });
        setFormSuccess('Repository updated successfully');
      } else {
        // Create new
        await createRepository(payload);
        setFormSuccess('Repository added successfully');
      }

      // Reload list
      await loadRepositories();
      
      // Reset form
      setTimeout(() => {
        setShowAddForm(false);
        setEditingRepo(null);
        resetForm();
      }, 1500);
      
    } catch (err) {
      setFormError(err.response?.data?.detail || err.message || 'Failed to save repository');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = (repo) => {
    setEditingRepo(repo);
    setFormData({
      url: `https://github.com/${repo.full_name}`,
      token: '',
      description: repo.description || '',
    });
    setGithubInfo({
      full_name: repo.full_name,
      description: repo.description,
      github_id: repo.github_id,
      default_branch: repo.default_branch,
      is_private: repo.is_private,
    });
    setShowAddForm(true);
  };

  const handleDelete = async (id) => {
    if (!confirm('Are you sure you want to delete this repository?')) {
      return;
    }

    try {
      await deleteRepository(id, false);
      await loadRepositories();
    } catch (err) {
      alert(err.response?.data?.detail || err.message || 'Failed to delete repository');
    }
  };

  const resetForm = () => {
    setFormData({ url: '', token: '', description: '' });
    setFormError('');
    setFormSuccess('');
    setGithubInfo(null);
    setShowToken(false);
  };

  const handleCancel = () => {
    setShowAddForm(false);
    setEditingRepo(null);
    resetForm();
  };

  return (
    <div className="tr2-page">
      <div className="tr2-grid-overlay" />
      <div className="tr2-wrap">
        
        {/* Hero */}
        <section className="tr2-hero">
          <span className="tr2-eyebrow">
            <span className="tr2-eyebrow-dot" />
            Repository Management
          </span>
          <h1 className="tr2-headline">
            Manage Your<br />
            <em className="tr2-headline-em">Repositories</em>
          </h1>
          <p className="tr2-hero-sub">
            Add and manage GitHub repositories for automated bug detection and fixing.
          </p>
        </section>

        {/* Main content */}
        <div className="repos-content">
          <div className="tr2-card">
            <div className="tr2-card-heading">
              <span className="tr2-card-dot" />
              <h2 className="tr2-card-title">Repositories</h2>
              <button
                type="button"
                className="repos-add-btn"
                onClick={() => setShowAddForm(true)}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="12" y1="5" x2="12" y2="19"/>
                  <line x1="5" y1="12" x2="19" y2="12"/>
                </svg>
                Add Repository
              </button>
            </div>

            {/* Add/Edit Form */}
            {showAddForm && (
              <div className="repos-form-container">
                <form onSubmit={handleSubmit} className="repos-form">
                  <h3 className="repos-form-title">
                    {editingRepo ? 'Edit Repository' : 'Add New Repository'}
                  </h3>

                  {/* URL Field */}
                  <div className="tr2-field">
                    <label htmlFor="repo-url" className="tr2-label">GitHub Repository URL</label>
                    <div className="repos-url-row">
                      <input
                        id="repo-url"
                        type="text"
                        className="tr2-input"
                        placeholder="https://github.com/owner/repo or owner/repo"
                        value={formData.url}
                        onChange={(e) => handleInputChange('url', e.target.value)}
                        disabled={submitting || editingRepo}
                      />
                      {!editingRepo && (
                        <button
                          type="button"
                          className="tr2-btn-outline repos-fetch-btn"
                          onClick={handleFetchFromGitHub}
                          disabled={fetchingGitHub || submitting}
                        >
                          {fetchingGitHub ? (
                            <><span className="tr2-spinner" />Fetching...</>
                          ) : (
                            'Fetch Info'
                          )}
                        </button>
                      )}
                    </div>
                  </div>

                  {/* GitHub Info Display */}
                  {githubInfo && (
                    <div className="repos-info-box">
                      <div className="repos-info-row">
                        <span className="repos-info-label">Full Name:</span>
                        <code className="repos-info-value">{githubInfo.full_name}</code>
                      </div>
                      <div className="repos-info-row">
                        <span className="repos-info-label">Default Branch:</span>
                        <code className="repos-info-value">{githubInfo.default_branch}</code>
                      </div>
                      <div className="repos-info-row">
                        <span className="repos-info-label">Visibility:</span>
                        <span className={`repos-badge ${githubInfo.is_private ? 'repos-badge-private' : 'repos-badge-public'}`}>
                          {githubInfo.is_private ? 'Private' : 'Public'}
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Token Field (only for private repos) */}
                  {githubInfo?.is_private && (
                    <div className="tr2-field tr2-token-field">
                      <label htmlFor="repo-token" className="tr2-label">
                        GitHub Personal Access Token
                        {!storedPAT?.exists && <span className="tr2-required-badge" style={{ marginLeft: '8px' }}>Required</span>}
                        {storedPAT?.exists && (
                          <span style={{ 
                            marginLeft: '8px',
                            fontSize: '12px',
                            color: '#20c2a4',
                            fontWeight: 'normal'
                          }}>
                            (Using stored PAT ...{storedPAT.last4})
                          </span>
                        )}
                      </label>
                      {storedPAT?.exists ? (
                        <div className="tr2-hint" style={{ marginTop: '8px' }}>
                          ✓ Using your stored PAT token from Dashboard. You can leave this field empty.
                        </div>
                      ) : (
                        <>
                          <div className="tr2-token-input-wrap">
                            <input
                              id="repo-token"
                              type={showToken ? 'text' : 'password'}
                              className="tr2-input"
                              placeholder="ghp_xxxxxxxxxxxx"
                              value={formData.token}
                              onChange={(e) => handleInputChange('token', e.target.value)}
                              disabled={submitting}
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
                          <span className="tr2-hint">
                            Required for private repositories. Token is encrypted before storage.
                          </span>
                        </>
                      )}
                    </div>
                  )}

                  {/* Description */}
                  <div className="tr2-field">
                    <label htmlFor="repo-desc" className="tr2-label">Description</label>
                    <textarea
                      id="repo-desc"
                      className="tr2-textarea"
                      rows={3}
                      placeholder="Brief description of the repository..."
                      value={formData.description}
                      onChange={(e) => handleInputChange('description', e.target.value)}
                      disabled={submitting}
                    />
                    <span className="tr2-hint">
                      Auto-filled from GitHub if available.
                    </span>
                  </div>

                  {/* Error/Success Messages */}
                  {formError && (
                    <div className="tr2-error-banner">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <circle cx="12" cy="12" r="10"/>
                        <line x1="12" y1="8" x2="12" y2="12"/>
                        <line x1="12" y1="16" x2="12.01" y2="16"/>
                      </svg>
                      {formError}
                    </div>
                  )}

                  {formSuccess && (
                    <div className="tr2-success-banner">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                        <polyline points="22 4 12 14.01 9 11.01"/>
                      </svg>
                      {formSuccess}
                    </div>
                  )}

                  {/* Actions */}
                  <div className="repos-form-actions">
                    <button
                      type="submit"
                      className="tr2-btn-primary"
                      disabled={submitting || !githubInfo}
                    >
                      {submitting ? (
                        <><span className="tr2-spinner" />Saving...</>
                      ) : editingRepo ? (
                        'Update Repository'
                      ) : (
                        'Add Repository'
                      )}
                    </button>
                    <button
                      type="button"
                      className="tr2-btn-outline"
                      onClick={handleCancel}
                      disabled={submitting}
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              </div>
            )}

            {/* Loading State */}
            {loading && (
              <div className="repos-loading">
                <span className="tr2-spinner" style={{ width: '24px', height: '24px' }} />
                <span>Loading repositories...</span>
              </div>
            )}

            {/* Error State */}
            {error && !loading && (
              <div className="tr2-error-banner" style={{ marginTop: '16px' }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10"/>
                  <line x1="12" y1="8" x2="12" y2="12"/>
                  <line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                {error}
              </div>
            )}

            {/* Empty State */}
            {!loading && !error && repositories.length === 0 && !showAddForm && (
              <div className="repos-empty">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/>
                </svg>
                <h3>No Repositories Yet</h3>
                <p>Add your first repository to get started with automated bug detection.</p>
                <button
                  type="button"
                  className="tr2-btn-primary"
                  onClick={() => setShowAddForm(true)}
                  style={{ marginTop: '16px' }}
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="12" y1="5" x2="12" y2="19"/>
                    <line x1="5" y1="12" x2="19" y2="12"/>
                  </svg>
                  Add Your First Repository
                </button>
              </div>
            )}

            {/* Repositories Table */}
            {!loading && repositories.length > 0 && (
              <div className="repos-table-container">
                <table className="repos-table">
                  <thead>
                    <tr>
                      <th>Full Name</th>
                      <th>Description</th>
                      <th>Branch</th>
                      <th>Visibility</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {repositories.map((repo) => (
                      <tr key={repo.id}>
                        <td>
                          <code className="repos-name">{repo.full_name}</code>
                        </td>
                        <td className="repos-desc-cell">
                          {repo.description || <span className="repos-empty-text">—</span>}
                        </td>
                        <td>
                          <code className="repos-branch">{repo.default_branch || 'main'}</code>
                        </td>
                        <td>
                          <span className={`repos-badge ${repo.is_private ? 'repos-badge-private' : 'repos-badge-public'}`}>
                            {repo.is_private ? 'Private' : 'Public'}
                          </span>
                        </td>
                        <td>
                          <span className={`repos-status repos-status-${repo.clone_status || 'not_cloned'}`}>
                            {repo.clone_status === 'cloned' && '● Cloned'}
                            {repo.clone_status === 'cloning' && '⏳ Cloning'}
                            {repo.clone_status === 'failed' && '✕ Failed'}
                            {!repo.clone_status || repo.clone_status === 'not_cloned' ? '○ Not Cloned' : ''}
                          </span>
                        </td>
                        <td>
                          <div className="repos-actions">
                            <button
                              type="button"
                              className="repos-action-btn repos-edit-btn"
                              onClick={() => handleEdit(repo)}
                              title="Edit"
                            >
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                              </svg>
                            </button>
                            <button
                              type="button"
                              className="repos-action-btn repos-delete-btn"
                              onClick={() => handleDelete(repo.id)}
                              title="Delete"
                            >
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <polyline points="3 6 5 6 21 6"/>
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                                <line x1="10" y1="11" x2="10" y2="17"/>
                                <line x1="14" y1="11" x2="14" y2="17"/>
                              </svg>
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
