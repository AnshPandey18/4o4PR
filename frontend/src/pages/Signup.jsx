import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import Button from '../components/Button';
import './Auth.css';

export default function Signup({ onLogin }) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!name || !email || !password) {
      setError('Please fill in all profile fields.');
      return;
    }
    
    onLogin({ email, name });
    navigate('/run');
  };

  return (
    <div className="auth-wrapper">
      <div className="auth-card">
        <div className="auth-header">
          <h2 className="auth-title">Create account</h2>
          <p className="auth-subtitle">Get started with self-healing codebase automation.</p>
        </div>

        {error && <div className="auth-error">{error}</div>}

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="auth-field-group">
            <label className="auth-label" htmlFor="name">
              Full Name
            </label>
            <input
              type="text"
              id="name"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                setError('');
              }}
              placeholder="Ada Lovelace"
              className="auth-input"
            />
          </div>

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
              placeholder="ada@company.com"
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

          <Button type="submit" variant="primary" style={{ width: '100%', marginTop: '8px' }}>
            Get Started
          </Button>
        </form>

        <div className="auth-footer">
          <span className="auth-link">
            Already have an account?{' '}
            <Link to="/login" className="auth-link-highlight">
              Sign In
            </Link>
          </span>
        </div>
      </div>
    </div>
  );
}
