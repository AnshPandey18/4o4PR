import React, { useState, useEffect } from 'react';
import { 
  getPipelineRuns, 
  getPipelineRun, 
  cancelPipelineRun,
  RunStatus
} from '../api/pipelineRuns';
import './RunHistory.css';

const RunHistory = ({ repositoryId = null, autoRefresh = true, refreshInterval = 5000 }) => {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedRun, setExpandedRun] = useState(null);
  const [cancellingRuns, setCancellingRuns] = useState(new Set());

  // Helper to get status display info with emoji
  const getRunStatusDisplay = (status) => {
    const displays = {
      pending: { emoji: '🟡', label: 'Pending', className: 'status-pending' },
      queued: { emoji: '🔵', label: 'Queued', className: 'status-queued' },
      cloning: { emoji: '📦', label: 'Cloning', className: 'status-cloning' },
      running: { emoji: '▶️', label: 'Running', className: 'status-running' },
      completed: { emoji: '✅', label: 'Completed', className: 'status-completed' },
      failed: { emoji: '❌', label: 'Failed', className: 'status-failed' },
      cancelled: { emoji: '⚫', label: 'Cancelled', className: 'status-cancelled' }
    };
    return displays[status] || { emoji: '⚪', label: status, className: 'status-unknown' };
  };

  // Fetch runs
  const fetchRuns = async () => {
    try {
      setError(null);
      const params = {};
      if (repositoryId) {
        params.repository_id = repositoryId;
      }
      const data = await getPipelineRuns(params);
      setRuns(data.runs || []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to fetch pipeline runs');
      console.error('Error fetching runs:', err);
    } finally {
      setLoading(false);
    }
  };

  // Initial fetch
  useEffect(() => {
    fetchRuns();
  }, [repositoryId]);

  // Auto-refresh for active runs
  useEffect(() => {
    if (!autoRefresh) return;

    const hasActiveRuns = runs.some(run => 
      ['pending', 'running', 'cloning'].includes(run.status)
    );

    if (!hasActiveRuns) return;

    const interval = setInterval(() => {
      fetchRuns();
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [runs, autoRefresh, refreshInterval]);

  // Expand/collapse run details
  const toggleRunDetails = async (runId) => {
    if (expandedRun === runId) {
      setExpandedRun(null);
    } else {
      setExpandedRun(runId);
      // Fetch fresh details when expanding
      try {
        const details = await getPipelineRun(runId);
        setRuns(prevRuns => 
          prevRuns.map(run => 
            run.id === runId ? details : run
          )
        );
      } catch (err) {
        console.error('Error fetching run details:', err);
      }
    }
  };

  // Cancel a run
  const handleCancelRun = async (runId) => {
    if (!window.confirm('Are you sure you want to cancel this run?')) {
      return;
    }

    setCancellingRuns(prev => new Set(prev).add(runId));
    try {
      await cancelPipelineRun(runId, 'User cancelled');
      await fetchRuns(); // Refresh the list
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to cancel run');
    } finally {
      setCancellingRuns(prev => {
        const next = new Set(prev);
        next.delete(runId);
        return next;
      });
    }
  };

  // Format timestamp
  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'N/A';
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  // Calculate duration
  const calculateDuration = (startTime, endTime) => {
    if (!startTime) return 'N/A';
    const start = new Date(startTime);
    const end = endTime ? new Date(endTime) : new Date();
    const diffMs = end - start;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHr = Math.floor(diffMin / 60);

    if (diffHr > 0) {
      return `${diffHr}h ${diffMin % 60}m`;
    } else if (diffMin > 0) {
      return `${diffMin}m ${diffSec % 60}s`;
    } else {
      return `${diffSec}s`;
    }
  };

  if (loading) {
    return <div className="run-history loading">Loading pipeline runs...</div>;
  }

  return (
    <div className="run-history">
      <div className="run-history-header">
        <h3>Pipeline Run History</h3>
        <button 
          className="btn-refresh" 
          onClick={fetchRuns}
          disabled={loading}
        >
          🔄 Refresh
        </button>
      </div>

      {error && (
        <div className="error-message">
          {error}
        </div>
      )}

      {runs.length === 0 ? (
        <div className="empty-state">
          No pipeline runs yet. Trigger your first run to see results here.
        </div>
      ) : (
        <div className="runs-list">
          {runs.map((run) => {
            const statusDisplay = getRunStatusDisplay(run.status);
            const isExpanded = expandedRun === run.id;
            const isCancelling = cancellingRuns.has(run.id);
            const canCancel = ['pending', 'running', 'cloning'].includes(run.status);

            return (
              <div key={run.id} className={`run-card status-${run.status}`}>
                <div className="run-header" onClick={() => toggleRunDetails(run.id)}>
                  <div className="run-main-info">
                    <div className="run-title">
                      <span className={`status-indicator ${statusDisplay.className}`}>
                        {statusDisplay.emoji}
                      </span>
                      <span className="run-id">Run #{run.id}</span>
                      <span className={`status-badge ${statusDisplay.className}`}>
                        {statusDisplay.label}
                      </span>
                    </div>
                    <div className="run-meta">
                      <span className="meta-item">
                        📦 {run.repository_name || `Repo #${run.repository_id}`}
                      </span>
                      <span className="meta-item">
                        🕒 {formatTimestamp(run.created_at)}
                      </span>
                      {run.started_at && (
                        <span className="meta-item">
                          ⏱️ {calculateDuration(run.started_at, run.completed_at)}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="run-actions" onClick={(e) => e.stopPropagation()}>
                    {canCancel && (
                      <button
                        className="btn-cancel-run"
                        onClick={() => handleCancelRun(run.id)}
                        disabled={isCancelling}
                      >
                        {isCancelling ? '⏳ Cancelling...' : '❌ Cancel'}
                      </button>
                    )}
                    <span className="expand-icon">
                      {isExpanded ? '▼' : '▶'}
                    </span>
                  </div>
                </div>

                {isExpanded && (
                  <div className="run-details">
                    <div className="details-grid">
                      <div className="detail-section">
                        <h4>Run Information</h4>
                        <div className="detail-row">
                          <span className="detail-label">Run ID:</span>
                          <span className="detail-value">{run.id}</span>
                        </div>
                        <div className="detail-row">
                          <span className="detail-label">Status:</span>
                          <span className="detail-value">{run.status}</span>
                        </div>
                        <div className="detail-row">
                          <span className="detail-label">Triggered By:</span>
                          <span className="detail-value">User #{run.user_id}</span>
                        </div>
                        <div className="detail-row">
                          <span className="detail-label">Created:</span>
                          <span className="detail-value">{formatTimestamp(run.created_at)}</span>
                        </div>
                        {run.started_at && (
                          <div className="detail-row">
                            <span className="detail-label">Started:</span>
                            <span className="detail-value">{formatTimestamp(run.started_at)}</span>
                          </div>
                        )}
                        {run.completed_at && (
                          <div className="detail-row">
                            <span className="detail-label">Completed:</span>
                            <span className="detail-value">{formatTimestamp(run.completed_at)}</span>
                          </div>
                        )}
                      </div>

                      <div className="detail-section">
                        <h4>Repository</h4>
                        <div className="detail-row">
                          <span className="detail-label">Repository ID:</span>
                          <span className="detail-value">{run.repository_id}</span>
                        </div>
                        {run.repository_name && (
                          <div className="detail-row">
                            <span className="detail-label">Name:</span>
                            <span className="detail-value">{run.repository_name}</span>
                          </div>
                        )}
                        {run.commit_sha && (
                          <div className="detail-row">
                            <span className="detail-label">Commit:</span>
                            <span className="detail-value code">{run.commit_sha.substring(0, 8)}</span>
                          </div>
                        )}
                        {run.branch && (
                          <div className="detail-row">
                            <span className="detail-label">Branch:</span>
                            <span className="detail-value">{run.branch}</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {run.error_message && (
                      <div className="error-section">
                        <h4>Error Details</h4>
                        <pre className="error-content">{run.error_message}</pre>
                      </div>
                    )}

                    {run.results && (
                      <div className="results-section">
                        <h4>Results</h4>
                        <pre className="results-content">
                          {typeof run.results === 'string' 
                            ? run.results 
                            : JSON.stringify(run.results, null, 2)
                          }
                        </pre>
                      </div>
                    )}

                    {run.logs && (
                      <div className="logs-section">
                        <h4>Logs</h4>
                        <pre className="logs-content">{run.logs}</pre>
                      </div>
                    )}

                    <div className="metadata-section">
                      <h4>Additional Details</h4>
                      <div className="detail-row">
                        <span className="detail-label">Configuration:</span>
                        <span className="detail-value">
                          {run.config ? JSON.stringify(run.config) : 'Default'}
                        </span>
                      </div>
                      {run.metadata && (
                        <div className="detail-row">
                          <span className="detail-label">Metadata:</span>
                          <span className="detail-value">
                            {JSON.stringify(run.metadata)}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default RunHistory;
