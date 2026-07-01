import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Landing from './pages/Landing';
import Login from './pages/Login';
import Signup from './pages/Signup';
import TriggerRun from './pages/TriggerRun';
import LiveStatus from './pages/LiveStatus';
import Report from './pages/Report';
import RunResult from './pages/RunResult';
import NavPill from './components/NavPill';
import HistorySidebar from './components/HistorySidebar';

export default function App() {
  const [user, setUser] = useState(null);
  const [activeRun, setActiveRun] = useState(null);

  const handleLogin = (userInfo) => {
    setUser(userInfo);
  };

  const handleLogout = () => {
    setUser(null);
    setActiveRun(null);
  };

  const handleStartRun = (runDetails) => {
    setActiveRun({
      ...runDetails,
      status: 'running'
    });
  };

  const handleResetRun = () => {
    setActiveRun(null);
  };

  return (
    <Router>
      <NavPill user={user} onLogout={handleLogout} />
      {user && <HistorySidebar />}
      <main style={{ minHeight: '100vh', width: '100%' }}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login onLogin={handleLogin} />} />
          <Route path="/signup" element={<Signup onLogin={handleLogin} />} />
          
          <Route 
            path="/run" 
            element={user ? <TriggerRun onStartRun={handleStartRun} /> : <Navigate to="/login" replace />} 
          />
          <Route 
            path="/status" 
            element={user ? <LiveStatus activeRun={activeRun} onResetRun={handleResetRun} /> : <Navigate to="/login" replace />} 
          />
          <Route
            path="/report"
            element={user ? <Report /> : <Navigate to="/login" replace />}
          />
          <Route
            path="/result"
            element={user ? <RunResult activeRun={activeRun} /> : <Navigate to="/login" replace />}
          />
          
          {/* Fallback routing */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </Router>
  );
}
