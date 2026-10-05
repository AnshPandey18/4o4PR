import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import Button from '../components/Button';
import authService from '../services/authService';
import './Auth.css';

export default function Login({ onLogin }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Please fill in all authentication fields.');
      return;
    }
    
    setLoading(true);
    
    try {
      // Call backend API
      await authService.login(email, password);
      
      // Also call onLogin for existing app state
      onLogin({ email });
      
      // Navigate to dashboard
      navigate('/dashboard');
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid email or password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-wrapper">
      <div className="auth-card">
        <div className="auth-header">
          <h2 className="auth-title">Welcome back</h2>
          <p className="auth-subtitle">Sign in to access your autonomic dashboard cockpit.</p>
        </div>

        {error && <div className="auth-error">{error}</div>}

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="auth-field-group">
            <label className="auth-label" htmlFor="email">
              Email Address
            </label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                setError('');
              }}
              placeholder="name@company.com"
              className="auth-input"
            />
          </div>

          <div className="auth-field-group">
            <label className="auth-label" htmlFor="password">
              Password
            </label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                setError('');
              }}
              placeholder="••••••••"
              className="auth-input"
            />
          </div>

          <Button 
            type="submit" 
            variant="primary" 
            disabled={loading}
            style={{ width: '100%', marginTop: '8px' }}
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </Button>
        </form>

        <div className="auth-footer">
          <span className="auth-link">
            New to 404PR?{' '}
            <Link to="/signup" className="auth-link-highlight">
              Create an account
            </Link>
          </span>
        </div>
      </div>
    </div>
  );
}
