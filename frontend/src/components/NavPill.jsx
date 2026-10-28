import React from 'react';
import { NavLink, Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import './NavPill.css';

export default function NavPill() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };
  return (
    <header className="nav-pill-header">
      <div className="nav-pill-container">
        {/* Brand Name */}
        <Link to="/" className="nav-pill-brand" style={{ textDecoration: 'none' }}>
          404PR
        </Link>

        {/* Links */}
        <nav className="nav-pill-nav">
          {user ? (
            <>
              <NavLink to="/dashboard" className="nav-link-item">
                Dashboard
              </NavLink>

              <NavLink to="/repositories" className="nav-link-item">
                Repo's
              </NavLink>

              <NavLink to="/run" className="nav-link-item">
                Trigger Run
              </NavLink>

              <NavLink to="/status" className="nav-link-item">
                Live Status
              </NavLink>

              <NavLink to="/result" className="nav-link-item">
                Run Result
              </NavLink>

              <NavLink to="/report" className="nav-link-item">
                Reports
              </NavLink>
            </>
          ) : (
            <>
              <NavLink to="/" className="nav-link-item" end>
                Home
              </NavLink>

              <a
                href="#features"
                onClick={(e) => {
                  const el = document.getElementById('features');
                  if (el) {
                    e.preventDefault();
                    el.scrollIntoView({ behavior: 'smooth' });
                  }
                }}
                className="nav-link-item"
              >
                Features
              </a>

              <a href="#docs" onClick={(e) => e.preventDefault()} className="nav-link-item">
                Docs
              </a>
            </>
          )}
        </nav>

        {/* Action button: conditional Sign In or Logout */}
        {user ? (
          <button
            onClick={handleLogout}
            className="nav-pill-btn"
            style={{ border: 'none', cursor: 'pointer', outline: 'none' }}
          >
            Logout
          </button>
        ) : (
          <Link to="/login" className="nav-pill-btn">
            Sign In
          </Link>
        )}
      </div>
    </header>
  );
}
