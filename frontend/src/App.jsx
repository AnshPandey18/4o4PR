import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Landing from './pages/Landing';
import Login from './pages/Login';
import Signup from './pages/Signup';
import TriggerRun from './pages/TriggerRun';
import LiveStatus from './pages/LiveStatus';
import Report from './pages/Report';
import RunResult from './pages/RunResult';
import Dashboard from './pages/Dashboard';
import Repositories from './pages/Repositories';
import NavPill from './components/NavPill';
import HistorySidebar from './components/HistorySidebar';

export default function App() {
  const [activeRun, setActiveRun] = useState(null);
  // completedRun stores the final summary after a pipeline finishes
  const [completedRun, setCompletedRun] = useState(null);

  const handleStartRun = (runDetails) => {
    setCompletedRun(null);
    setActiveRun({
      ...runDetails,
      status: 'running'
    });
  };

  const handleRunComplete = (summary) => {
    // Called by LiveStatus when the pipeline finishes
    setCompletedRun(summary);
  };

  const handleResetRun = () => {
    setActiveRun(null);
  };

  return (
    <AuthProvider>
      <Router>
        <NavPill />
        <HistorySidebar />
        <main style={{ minHeight: '100vh', width: '100%' }}>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />
            
            {/* Protected routes */}
            <Route 
              path="/dashboard" 
              element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              } 
            />
            
            <Route 
              path="/repositories" 
              element={
                <ProtectedRoute>
                  <Repositories />
                </ProtectedRoute>
              } 
            />
            
            <Route 
              path="/run" 
              element={
                <ProtectedRoute>
                  <TriggerRun onStartRun={handleStartRun} />
                </ProtectedRoute>
              } 
            />
            
            <Route 
              path="/status" 
              element={
                <ProtectedRoute>
                  <LiveStatus activeRun={activeRun} onResetRun={handleResetRun} onRunComplete={handleRunComplete} />
                </ProtectedRoute>
              } 
            />
            
            <Route
              path="/report"
              element={
                <ProtectedRoute>
                  <Report completedRun={completedRun} />
                </ProtectedRoute>
              }
            />
            
            <Route
              path="/result"
              element={
                <ProtectedRoute>
                  <RunResult activeRun={activeRun} />
                </ProtectedRoute>
              }
            />
            
            {/* Fallback routing */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </Router>
    </AuthProvider>
  );
}
