import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import authService from '../services/authService';
import { getCredentials, storeCredentials, revokeCredentials, testCredentials } from '../api/credentials';
import './TriggerRun.css';

export default function Dashboard() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [credentials, setCredentials] = useState(null);
  const [credentialsLoading, setCredentialsLoading] = useState(false);
  const [showAddKeyForm, setShowAddKeyForm] = useState(false);
  const [showToken, setShowToken] = useState(false);
  const [formData, setFormData] = useState({
    github_token: '',
    scopes: '',
    expires_at: ''
  });
  const [showPatGuide, setShowPatGuide] = useState(false);

  // Calculate days remaining until expiry
  const calculateDaysRemaining = (expiryDate) => {
    if (!expiryDate) return null;
    const today = new Date();
    const expiry = new Date(expiryDate);
    const diffTime = expiry - today;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays;
  };
  const [formError, setFormError] = useState('');
  const [formSuccess, setFormSuccess] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [testing, setTesting] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    loadUser();
    loadCredentials();
  }, []);

  const loadUser = async () => {
    try {
      const userData = await authService.getCurrentUser();
      setUser(userData);
    } catch (err) {
      setError('Failed to load user profile');
      console.error('Failed to load user:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadCredentials = async () => {
    setCredentialsLoading(true);
    try {
      const creds = await getCredentials();
      setCredentials(creds);
    } catch (err) {
      // No credentials found is not an error
      if (err.response?.status !== 404) {
        console.error('Failed to load credentials:', err);
      }
    } finally {
      setCredentialsLoading(false);
    }
  };

  const handleInputChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    setFormError('');
    setFormSuccess('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!formData.github_token.trim()) {
      setFormError('GitHub token is required');
      return;
    }

    if (!formData.expires_at) {
      setFormError('Expiration date is required');
      return;
    }

    setSubmitting(true);
    setFormError('');
    setFormSuccess('');

    try {
      const savedCreds = await storeCredentials(formData);
      setCredentials(savedCreds);
      setFormSuccess('PAT token added successfully');
      
      // Reset form after delay
      setTimeout(() => {
        setShowAddKeyForm(false);
        setFormData({ github_token: '', scopes: '', expires_at: '' });
        setFormSuccess('');
        setShowToken(false);
      }, 2000);
    } catch (err) {
      setFormError(err.response?.data?.detail || err.message || 'Failed to save PAT token');
    } finally {
      setSubmitting(false);
    }
  };

  const handleTestCredentials = async () => {
    setTesting(true);
    setFormError('');
    setFormSuccess('');

    try {
      const result = await testCredentials();
      setFormSuccess(`Token is valid! Scopes: ${result.scopes || 'N/A'}`);
    } catch (err) {
      setFormError(err.response?.data?.detail || 'Token validation failed');
    } finally {
      setTesting(false);
    }
  };

  const handleRevokeCredentials = async () => {
    if (!confirm('Are you sure you want to revoke your PAT token?')) {
      return;
    }

    try {
      await revokeCredentials();
      setCredentials(null);
      setFormSuccess('PAT token revoked successfully');
    } catch (err) {
      setFormError(err.response?.data?.detail || 'Failed to revoke PAT token');
    }
  };

  const handleCancel = () => {
    setShowAddKeyForm(false);
    setFormData({ github_token: '', scopes: '', expires_at: '' });
    setFormError('');
    setFormSuccess('');
    setShowToken(false);
  };

  if (loading) {
    return (
      <div className="tr2-page">
        <div className="tr2-grid-overlay" />
        <div className="tr2-wrap">
          <div className="tr2-card" style={{ marginTop: '80px' }}>
            <div style={{ textAlign: 'center', padding: '40px' }}>
              <span className="tr2-spinner" style={{ width: '32px', height: '32px' }} />
              <p style={{ marginTop: '16px', color: 'var(--color-fog)' }}>Loading...</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="tr2-page">
      <div className="tr2-grid-overlay" />
      <div className="tr2-wrap">

        {/* Hero */}
        <section className="tr2-hero">
          <span className="tr2-eyebrow">
            <span className="tr2-eyebrow-dot" />
            User Dashboard
          </span>
          <h1 className="tr2-headline">
            Your Account<br />
            <em className="tr2-headline-em">Overview</em>
          </h1>
          <p className="tr2-hero-sub">
            Manage your profile, credentials, and system preferences.
          </p>
        </section>

        {/* Main content */}
        <div className="tr2-main-grid">
          <div className="tr2-left">
            
            {/* User Profile Card */}
            {user && (
              <div className="tr2-card">
                <div className="tr2-card-heading">
                  <span className="tr2-card-dot" />
                  <h2 className="tr2-card-title">Profile Information</h2>
                </div>
                <div className="tr2-stats-grid">
                  <div className="tr2-stat">
                    <span className="tr2-stat-k">Full Name</span>
                    <span className="tr2-stat-v">{user.full_name || 'User'}</span>
                  </div>
                  <div className="tr2-stat">
                    <span className="tr2-stat-k">Email</span>
                    <span className="tr2-stat-v tr2-v-mono">{user.email}</span>
                  </div>
                  <div className="tr2-stat">
                    <span className="tr2-stat-k">User ID</span>
                    <span className="tr2-stat-v tr2-v-mono">#{user.id}</span>
                  </div>
                  <div className="tr2-stat">
                    <span className="tr2-stat-k">Status</span>
                    <span className={`tr2-stat-v ${user.is_active ? 'tr2-v-teal' : 'tr2-v-ember'}`}>
                      {user.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                  <div className="tr2-stat">
                    <span className="tr2-stat-k">Member Since</span>
                    <span className="tr2-stat-v">
                      {new Date(user.created_at).toLocaleDateString('en-US', {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric'
                      })}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* PAT Token Management Card */}
            <div className="tr2-card tr2-card-teal">
              <div className="tr2-card-heading">
                <span className="tr2-card-dot" />
                <h2 className="tr2-card-title">GitHub PAT Token</h2>

                {!showAddKeyForm && (
                  <button
                    type="button"
                    className="repos-add-btn"
                    onClick={() => setShowAddKeyForm(true)}
                    style={{ marginLeft: 'auto' }}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="12" y1="5" x2="12" y2="19"/>
                      <line x1="5" y1="12" x2="19" y2="12"/>
                    </svg>
                    {credentials?.is_active ? 'Update Token' : 'Add Token'}
                  </button>
                )}
              </div>

              {/* Add/Update Token Form */}
              {showAddKeyForm && (
                <form onSubmit={handleSubmit} className="tr2-form" style={{ marginTop: '16px' }}>
                  
                  {/* How to get PAT Guide */}
                  <div 
                    className="pat-guide-trigger"
                    onMouseEnter={() => setShowPatGuide(true)}
                    onMouseLeave={() => setShowPatGuide(false)}
                    style={{ 
                      position: 'relative', 
                      marginBottom: '16px'
                    }}
                  >
                    <span style={{
                      fontSize: '13px',
                      color: '#20c2a4',
                      textDecoration: 'underline',
                      fontFamily: 'var(--font-inter)',
                      cursor: 'help',
                      display: 'inline-block'
                    }}>
                      How to get PAT?
                    </span>
                    
                    {showPatGuide && (
                      <div className="pat-guide-popup" style={{
                        position: 'absolute',
                        top: '100%',
                        left: '0',
                        marginTop: '8px',
                        width: '420px',
                        backgroundColor: '#1a1d23',
                        border: '1px solid rgba(32, 194, 164, 0.3)',
                        borderRadius: '8px',
                        padding: '16px',
                        boxShadow: '0 8px 24px rgba(0, 0, 0, 0.4)',
                        zIndex: 1000,
                        fontFamily: 'var(--font-inter)',
                        fontSize: '13px',
                        lineHeight: '1.6',
                        color: '#e0e0e0'
                      }}>
                        <h4 style={{
                          margin: '0 0 12px 0',
                          fontSize: '14px',
                          fontWeight: '600',
                          color: '#20c2a4'
                        }}>
                          How to get a fine-grained token
                        </h4>
                        <ol style={{
                          margin: '0',
                          paddingLeft: '20px',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '8px'
                        }}>
                          <li>Go to <strong>GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens</strong>.</li>
                          <li>Click <strong>Generate new token</strong>.</li>
                          <li>Under <strong>Repository access</strong>, select only the repositories you want to add.</li>
                          <li>Under <strong>Permissions</strong>, set <strong>Contents</strong> to <em>Read-only</em> and <strong>Pull requests</strong> to <em>Read-only</em>.</li>
                          <li>Set an expiration date.</li>
                          <li>Click <strong>Generate token</strong> and copy it. <span style={{ color: '#ffb764' }}>GitHub shows it only once</span>.</li>
                        </ol>
                      </div>
                    )}
                  </div>

                  {/* Required Permissions Info */}
                  <div style={{
                    backgroundColor: 'rgba(32, 194, 164, 0.1)',
                    border: '1px solid rgba(32, 194, 164, 0.3)',
                    borderRadius: '6px',
                    padding: '12px 16px',
                    marginBottom: '20px',
                    fontFamily: 'var(--font-inter)',
                    fontSize: '13px'
                  }}>
                    <div style={{
                      fontWeight: '600',
                      color: '#20c2a4',
                      marginBottom: '8px',
                      fontSize: '13px'
                    }}>
                      PAT should have the following permissions:
                    </div>
                    <ul style={{
                      margin: '0',
                      paddingLeft: '20px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px',
                      color: '#e0e0e0'
                    }}>
                      <li><strong>Contents:</strong> needed to clone the code.</li>
                      <li><strong>Pull requests:</strong> needed to read PR details and head/base commits.</li>
                      <li><strong>Metadata:</strong> required by GitHub.</li>
                    </ul>
                  </div>

                  <div className="tr2-field tr2-token-field">
                    <label htmlFor="github-token" className="tr2-label">
                      GitHub Personal Access Token
                      <span className="tr2-required-badge" style={{ marginLeft: '8px' }}>Required</span>
                    </label>
                    <div className="tr2-token-input-wrap">
                      <input
                        id="github-token"
                        type={showToken ? 'text' : 'password'}
                        className="tr2-input"
                        placeholder="ghp_xxxxxxxxxxxx"
                        value={formData.github_token}
                        onChange={(e) => handleInputChange('github_token', e.target.value)}
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
                      Required for accessing private repositories. Token is encrypted before storage.
                    </span>
                  </div>

                  <div className="tr2-field">
                    <label htmlFor="expires-at" className="tr2-label">
                      Expiration Date
                      <span className="tr2-required-badge" style={{ marginLeft: '8px' }}>Required</span>
                    </label>
                    <input
                      id="expires-at"
                      type="date"
                      className="tr2-input"
                      value={formData.expires_at}
                      onChange={(e) => handleInputChange('expires_at', e.target.value)}
                      disabled={submitting}
                      min={new Date().toISOString().split('T')[0]}
                    />
                    <span className="tr2-hint">
                      When will this token expire? This helps track token validity.
                    </span>
                  </div>

                  <div className="tr2-field">
                    <label htmlFor="scopes" className="tr2-label">Token Scopes (Optional)</label>
                    <input
                      id="scopes"
                      type="text"
                      className="tr2-input"
                      placeholder="repo, user (leave empty for default)"
                      value={formData.scopes}
                      onChange={(e) => handleInputChange('scopes', e.target.value)}
                      disabled={submitting}
                    />
                    <span className="tr2-hint">
                      Comma-separated list of token scopes. Leave empty to use default scopes.
                    </span>
                  </div>

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

                  <div className="tr2-actions">
                    <button
                      type="submit"
                      className="tr2-btn-primary"
                      disabled={submitting}
                    >
                      {submitting ? (
                        <><span className="tr2-spinner" />Saving...</>
                      ) : (
                        <>
                          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
                            <polyline points="17 21 17 13 7 13 7 21"/>
                            <polyline points="7 3 7 8 15 8"/>
                          </svg>
                          Save Token
                        </>
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
              )}

              {/* Display Current Token */}
              {!showAddKeyForm && !credentialsLoading && credentials?.is_active && (
                <div style={{ marginTop: '16px' }}>
                  <div className="repos-info-box">
                    <div className="repos-info-row">
                      <span className="repos-info-label">Token (Last 4 digits):</span>
                      <code className="repos-info-value">
                        {'•'.repeat(36)}{credentials.token_last4 || '****'}
                      </code>
                    </div>
                    <div className="repos-info-row">
                      <span className="repos-info-label">Scopes:</span>
                      <code className="repos-info-value">{credentials.scopes || 'Default'}</code>
                    </div>
                    <div className="repos-info-row">
                      <span className="repos-info-label">Status:</span>
                      <span className="repos-badge repos-badge-public">
                        Active
                      </span>
                    </div>
                    {credentials.expires_at && (
                      <>
                        <div className="repos-info-row">
                          <span className="repos-info-label">Expires On:</span>
                          <span className="repos-info-value">
                            {new Date(credentials.expires_at).toLocaleDateString('en-US', {
                              year: 'numeric',
                              month: 'short',
                              day: 'numeric'
                            })}
                          </span>
                        </div>
                        <div className="repos-info-row">
                          <span className="repos-info-label">Days Remaining:</span>
                          <span className="repos-info-value" style={{
                            color: calculateDaysRemaining(credentials.expires_at) < 7 
                              ? '#e6714f' 
                              : calculateDaysRemaining(credentials.expires_at) < 30 
                              ? '#ffb764' 
                              : '#20c2a4',
                            fontWeight: '600'
                          }}>
                            {(() => {
                              const days = calculateDaysRemaining(credentials.expires_at);
                              if (days < 0) return 'Expired';
                              if (days === 0) return 'Expires today';
                              if (days === 1) return '1 day';
                              return `${days} days`;
                            })()}
                          </span>
                        </div>
                      </>
                    )}
                    {credentials.last_used_at && (
                      <div className="repos-info-row">
                        <span className="repos-info-label">Last Used:</span>
                        <span className="repos-info-value">
                          {new Date(credentials.last_used_at).toLocaleDateString('en-US', {
                            year: 'numeric',
                            month: 'short',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit'
                          })}
                        </span>
                      </div>
                    )}
                    <div className="repos-info-row">
                      <span className="repos-info-label">Added:</span>
                      <span className="repos-info-value">
                        {new Date(credentials.created_at).toLocaleDateString('en-US', {
                          year: 'numeric',
                          month: 'short',
                          day: 'numeric'
                        })}
                      </span>
                    </div>
                  </div>

                  <div className="tr2-actions" style={{ marginTop: '16px' }}>
                    <button
                      type="button"
                      className="tr2-btn-outline"
                      onClick={handleTestCredentials}
                      disabled={testing}
                    >
                      {testing ? (
                        <><span className="tr2-spinner" />Testing...</>
                      ) : (
                        <>
                          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="20 6 9 17 4 12"/>
                          </svg>
                          Test Token
                        </>
                      )}
                    </button>
                    <button
                      type="button"
                      className="tr2-btn-outline"
                      onClick={handleRevokeCredentials}
                      style={{ color: '#e6714f', borderColor: '#e6714f' }}
                    >
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                      </svg>
                      Revoke Token
                    </button>
                  </div>

                  {(formError || formSuccess) && (
                    <div style={{ marginTop: '16px' }}>
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
                    </div>
                  )}
                </div>
              )}

              {/* No Token Message */}
              {!showAddKeyForm && !credentialsLoading && !credentials?.is_active && (
                <div className="repos-empty" style={{ padding: '32px 24px' }}>
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                    <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                  </svg>
                  <h3>No PAT Token Added</h3>
                  <p>Add your GitHub Personal Access Token to access private repositories.</p>
                </div>
              )}

              {/* Loading State */}
              {credentialsLoading && (
                <div style={{ textAlign: 'center', padding: '32px' }}>
                  <span className="tr2-spinner" />
                  <p style={{ marginTop: '12px', color: 'var(--color-fog)', fontSize: '14px' }}>
                    Loading credentials...
                  </p>
                </div>
              )}
            </div>

          </div>

          <div className="tr2-right">
            {/* Quick Actions */}
            <div className="tr2-card tr2-card-blush">
              <div className="tr2-card-heading">
                <span className="tr2-card-dot" />
                <h2 className="tr2-card-title">Quick Actions</h2>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
                <button
                  className="tr2-btn-primary"
                  onClick={() => navigate('/repositories')}
                  style={{ width: '100%', justifyContent: 'center' }}
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/>
                  </svg>
                  Manage Repositories
                </button>
                <button
                  className="tr2-btn-primary"
                  onClick={() => navigate('/run')}
                  style={{ width: '100%', justifyContent: 'center' }}
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polygon points="5 3 19 12 5 21 5 3"/>
                  </svg>
                  Trigger New Run
                </button>
                <button
                  className="tr2-btn-outline"
                  onClick={() => navigate('/status')}
                  style={{ width: '100%', justifyContent: 'center' }}
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                  </svg>
                  View Live Status
                </button>
              </div>
            </div>

            {/* System Info */}
            {error && (
              <div className="tr2-card">
                <div className="tr2-error-banner">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="8" x2="12" y2="12"/>
                    <line x1="12" y1="16" x2="12.01" y2="16"/>
                  </svg>
                  {error}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
