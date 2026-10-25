/**
 * Repository Manager Component
 * Clean, simplified form that dynamically changes based on repository visibility
 */
import { useState, useEffect } from 'react';
import {
    getRepositories,
    createRepository,
    cloneRepository,
    getCloneStatus,
    deleteRepository
} from '../api/repositories';
import './RepositoryManager.css';

export default function RepositoryManager({ onSelectRepository, selectedRepoId, compactMode = false }) {
    const [repositories, setRepositories] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [showAddForm, setShowAddForm] = useState(false);
    
    // Form state
    const [formData, setFormData] = useState({
        url: '',
        branch: 'main',
        personal_access_token: '',
        description: ''
    });
    const [submitting, setSubmitting] = useState(false);
    const [cloning, setCloning] = useState({});
    const [isPrivate, setIsPrivate] = useState(null); // null = unknown, true = private, false = public
    const [urlParsed, setUrlParsed] = useState(null);

    // Load repositories on mount
    useEffect(() => {
        loadRepositories();
    }, []);

    // Parse GitHub URL to extract owner/repo and detect visibility
    const parseGitHubUrl = (url) => {
        if (!url) {
            setUrlParsed(null);
            setIsPrivate(null);
            return;
        }

        // Match GitHub URL patterns
        const patterns = [
            // https://github.com/owner/repo
            /github\.com\/([^\/]+)\/([^\/\?]+)/,
            // owner/repo
            /^([^\/]+)\/([^\/]+)$/,
            // git@github.com:owner/repo.git
            /github\.com:([^\/]+)\/([^\/\.]+)/
        ];

        for (const pattern of patterns) {
            const match = url.match(pattern);
            if (match) {
                const owner = match[1];
                const repo = match[2].replace(/\.git$/, '').replace(/\/$/, '');
                setUrlParsed({ owner, repo, fullName: `${owner}/${repo}` });
                return;
            }
        }

        setUrlParsed(null);
        setIsPrivate(null);
    };

    // Handle URL input change
    const handleUrlChange = (e) => {
        const url = e.target.value;
        setFormData({ ...formData, url });
        parseGitHubUrl(url);
    };

    // Toggle repository visibility (public/private)
    const handleVisibilityChange = (isPrivateRepo) => {
        setIsPrivate(isPrivateRepo);
    };

    const handleSubmit = async () => {
        if (!formData.url) {
            setError('Repository URL is required');
            return;
        }

        if (isPrivate && !formData.personal_access_token) {
            setError('Personal access token is required for private repositories');
            return;
        }

        setSubmitting(true);
        setError(null);

        try {
            const newRepo = await createRepository({
                ...formData,
                url: formData.url,
                personal_access_token: isPrivate ? formData.personal_access_token : undefined
            });
            
            // Add to list
            setRepositories([newRepo, ...repositories]);
            
            // Reset form
            setFormData({
                url: '',
                branch: 'main',
                personal_access_token: '',
                description: ''
            });
            setUrlParsed(null);
            setIsPrivate(null);
            setShowAddForm(false);
            
            // Auto-clone if URL is provided
            if (newRepo.id) {
                handleClone(newRepo.id);
            }
        } catch (err) {
            setError(err.response?.data?.detail || 'Failed to add repository');
        } finally {
            setSubmitting(false);
        }
    };

    const handleClone = async (repoId) => {
        try {
            setCloning(prev => ({ ...prev, [repoId]: true }));
            const result = await cloneRepository(repoId);
            
            // Update repository in list
            setRepositories(repos => repos.map(r => 
                r.id === repoId 
                    ? { ...r, clone_status: 'cloned', clone_path: result.clone_path }
                    : r
            ));
        } catch (err) {
            setError(err.response?.data?.detail || 'Clone failed');
        } finally {
            setCloning(prev => ({ ...prev, [repoId]: false }));
        }
    };

    const handleDelete = async (repoId) => {
        if (!confirm('Delete this repository? This action cannot be undone.')) {
            return;
        }

        try {
            await deleteRepository(repoId, true); // Also delete cloned files
            setRepositories(repos => repos.filter(r => r.id !== repoId));
        } catch (err) {
            setError(err.response?.data?.detail || 'Failed to delete repository');
        }
    };

    const getStatusBadge = (status) => {
        const badges = {
            not_cloned: { label: 'Not Cloned', className: 'status-gray' },
            cloning: { label: 'Cloning...', className: 'status-blue' },
            cloned: { label: 'Cloned', className: 'status-green' },
            failed: { label: 'Failed', className: 'status-red' },
            updating: { label: 'Updating...', className: 'status-blue' }
        };
        return badges[status] || { label: status, className: 'status-gray' };
    };

    return (
        <div className="repo-manager">
            <div className="repo-manager-header">
                <h3>Your Repositories</h3>
                <button 
                    className="btn-add-repo"
                    onClick={() => setShowAddForm(!showAddForm)}
                >
                    {showAddForm ? '✕ Cancel' : '+ Add Repository'}
                </button>
            </div>

            {error && (
                <div className="repo-error">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
                    </svg>
                    {error}
                </div>
            )}

            {showAddForm && (
                <div className="repo-form">
                    {/* URL Input with Preview */}
                    <div className="form-group">
                        <label htmlFor="url">Repository URL</label>
                        <input
                            id="url"
                            type="text"
                            placeholder="https://github.com/owner/repo or owner/repo"
                            value={formData.url}
                            onChange={handleUrlChange}
                            className={urlParsed ? 'input-success' : ''}
                            autoFocus
                        />
                        {urlParsed && (
                            <div className="url-preview">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                                    <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/>
                                </svg>
                                <span className="url-preview-text">{urlParsed.fullName}</span>
                            </div>
                        )}
                    </div>

                    {/* Visibility Toggle */}
                    {urlParsed && (
                        <div className="visibility-section">
                            <label className="visibility-label">Repository Visibility</label>
                            <div className="visibility-toggle">
                                <button
                                    type="button"
                                    className={`visibility-btn ${isPrivate === false ? 'active' : ''}`}
                                    onClick={() => handleVisibilityChange(false)}
                                >
                                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <circle cx="12" cy="12" r="10"/>
                                        <path d="M12 16v-4M12 8h.01"/>
                                    </svg>
                                    Public
                                </button>
                                <button
                                    type="button"
                                    className={`visibility-btn ${isPrivate === true ? 'active' : ''}`}
                                    onClick={() => handleVisibilityChange(true)}
                                >
                                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                                        <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                                    </svg>
                                    Private
                                </button>
                            </div>
                        </div>
                    )}

                    {/* Dynamic Fields Based on Visibility */}
                    {isPrivate === true && (
                        <div className="form-group pat-group">
                            <label htmlFor="pat">
                                Personal Access Token
                                <span className="required-badge">Required</span>
                            </label>
                            <input
                                id="pat"
                                type="password"
                                placeholder="ghp_xxxxxxxxxxxx"
                                value={formData.personal_access_token}
                                onChange={e => setFormData({ ...formData, personal_access_token: e.target.value })}
                                autoComplete="off"
                            />
                            <span className="form-hint">
                                Required for private repositories. Your token is encrypted and stored securely.
                            </span>
                        </div>
                    )}

                    {/* Branch & Description - Show after visibility selection */}
                    {isPrivate !== null && (
                        <>
                            <div className="form-row">
                                <div className="form-group">
                                    <label htmlFor="branch">Branch</label>
                                    <input
                                        id="branch"
                                        type="text"
                                        placeholder="main"
                                        value={formData.branch}
                                        onChange={e => setFormData({ ...formData, branch: e.target.value })}
                                    />
                                </div>
                            </div>

                            <div className="form-group">
                                <label htmlFor="description">Description (Optional)</label>
                                <textarea
                                    id="description"
                                    rows="2"
                                    placeholder="Brief description of this repository..."
                                    value={formData.description}
                                    onChange={e => setFormData({ ...formData, description: e.target.value })}
                                />
                            </div>
                        </>
                    )}

                    {/* Submit Button */}
                    {isPrivate !== null && (
                        <div className="form-actions">
                            <button 
                                type="button" 
                                className="btn-primary" 
                                onClick={handleSubmit}
                                disabled={submitting || !formData.url || (isPrivate && !formData.personal_access_token)}
                            >
                                {submitting ? (
                                    <>
                                        <span className="btn-spinner"></span>
                                        Adding...
                                    </>
                                ) : (
                                    <>
                                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                                            <line x1="12" y1="5" x2="12" y2="19"/>
                                            <line x1="5" y1="12" x2="19" y2="12"/>
                                        </svg>
                                        Add & Clone Repository
                                    </>
                                )}
                            </button>
                        </div>
                    )}
                </div>
            )}

            {loading ? (
                <div className="repo-loading">Loading repositories...</div>
            ) : repositories.length === 0 ? (
                <div className="repo-empty">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/>
                    </svg>
                    <p>No repositories yet</p>
                    <span>Add your first GitHub repository to get started</span>
                </div>
            ) : (
                <div className="repo-list">
                    {repositories.map(repo => {
                        const statusBadge = getStatusBadge(repo.clone_status);
                        const isSelected = repo.id === selectedRepoId;
                        const isCloning = cloning[repo.id];
                        
                        return (
                            <div 
                                key={repo.id} 
                                className={`repo-card ${isSelected ? 'repo-card-selected' : ''}`}
                                onClick={() => onSelectRepository?.(repo)}
                            >
                                <div className="repo-card-header">
                                    <div className="repo-info">
                                        <h4 className="repo-name">{repo.name}</h4>
                                        {repo.description && (
                                            <p className="repo-desc">{repo.description}</p>
                                        )}
                                    </div>
                                    <span className={`repo-status ${statusBadge.className}`}>
                                        {statusBadge.label}
                                    </span>
                                </div>

                                <div className="repo-meta">
                                    {repo.language && (
                                        <span className="repo-meta-item">
                                            <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                                                <circle cx="12" cy="12" r="10"/>
                                            </svg>
                                            {repo.language}
                                        </span>
                                    )}
                                    {repo.stars_count > 0 && (
                                        <span className="repo-meta-item">
                                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                                            </svg>
                                            {repo.stars_count}
                                        </span>
                                    )}
                                    <span className="repo-meta-item">
                                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                            <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>
                                        </svg>
                                        {repo.default_branch || repo.branch}
                                    </span>
                                </div>

                                <div className="repo-actions" onClick={(e) => e.stopPropagation()}>
                                    {repo.clone_status === 'not_cloned' && (
                                        <button 
                                            className="btn-repo-action btn-clone"
                                            onClick={() => handleClone(repo.id)}
                                            disabled={isCloning}
                                        >
                                            {isCloning ? 'Cloning...' : 'Clone'}
                                        </button>
                                    )}
                                    {repo.clone_status === 'cloned' && (
                                        <span className="clone-info">
                                            {repo.clone_size_mb && `${repo.clone_size_mb.toFixed(1)} MB`}
                                        </span>
                                    )}
                                    <button 
                                        className="btn-repo-action btn-delete"
                                        onClick={() => handleDelete(repo.id)}
                                        title="Delete repository"
                                    >
                                        🗑
                                    </button>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
