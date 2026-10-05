import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '../components/Button';
import authService from '../services/authService';
import './Auth.css';

export default function Dashboard() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    loadUser();
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

  const handleLogout = () => {
    authService.logout();
    navigate('/login');
  };

  if (loading) {
    return (
      <div className="auth-wrapper">
        <div className="auth-card">
          <p style={{ 
            textAlign: 'center', 
            color: 'var(--color-fog)',
            fontFamily: 'var(--font-inter)'
          }}>
            Loading...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-wrapper">
      <div className="auth-card">
        <div className="auth-header">
          <h2 className="auth-title">Dashboard</h2>
          <p className="auth-subtitle">Your account overview and system status.</p>
        </div>

        {error && <div className="auth-error">{error}</div>}

        {user && (
          <div style={{ marginTop: 'var(--spacing-24)' }}>
            <div style={{
              backgroundColor: 'var(--surface-charcoal)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: 'var(--radius-inputs)',
              padding: 'var(--spacing-24)',
              marginBottom: 'var(--spacing-20)'
            }}>
              <h3 style={{
                fontFamily: 'var(--font-inter)',
                fontSize: 'var(--text-body)',
                color: 'var(--color-white)',
                fontWeight: 'var(--font-weight-semibold)',
                marginBottom: 'var(--spacing-16)'
              }}>
                Welcome back, {user.full_name || 'User'}!
              </h3>

              <div style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--spacing-12)'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{
                    fontFamily: 'var(--font-inter)',
                    fontSize: 'var(--text-caption)',
                    color: 'var(--color-ash)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em'
                  }}>
                    Email
                  </span>
                  <span style={{
                    fontFamily: 'var(--font-inter)',
                    fontSize: 'var(--text-body-sm)',
                    color: 'var(--color-white)'
                  }}>
                    {user.email}
                  </span>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{
                    fontFamily: 'var(--font-inter)',
                    fontSize: 'var(--text-caption)',
                    color: 'var(--color-ash)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em'
                  }}>
                    User ID
                  </span>
                  <span style={{
                    fontFamily: 'var(--font-inter)',
                    fontSize: 'var(--text-body-sm)',
                    color: 'var(--color-white)'
                  }}>
                    #{user.id}
                  </span>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{
                    fontFamily: 'var(--font-inter)',
                    fontSize: 'var(--text-caption)',
                    color: 'var(--color-ash)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em'
                  }}>
                    Status
                  </span>
                  <span style={{
                    fontFamily: 'var(--font-inter)',
                    fontSize: 'var(--text-body-sm)',
                    color: user.is_active ? 'var(--color-forest-pulse)' : 'var(--color-ember)',
                    fontWeight: 'var(--font-weight-medium)'
                  }}>
                    {user.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{
                    fontFamily: 'var(--font-inter)',
                    fontSize: 'var(--text-caption)',
                    color: 'var(--color-ash)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em'
                  }}>
                    Member Since
                  </span>
                  <span style={{
                    fontFamily: 'var(--font-inter)',
                    fontSize: 'var(--text-body-sm)',
                    color: 'var(--color-white)'
                  }}>
                    {new Date(user.created_at).toLocaleDateString('en-US', {
                      year: 'numeric',
                      month: 'short',
                      day: 'numeric'
                    })}
                  </span>
                </div>
              </div>
            </div>

            <Button 
              onClick={handleLogout} 
              variant="secondary" 
              style={{ width: '100%' }}
            >
              Sign Out
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
