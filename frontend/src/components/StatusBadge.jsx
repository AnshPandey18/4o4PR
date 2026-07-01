import React from 'react';
import './StatusBadge.css';

export default function StatusBadge({ status = 'queued' }) {
  const normalizedStatus = status.toLowerCase();

  let badgeClass = 'status-badge-queued';
  let dotClass = '';
  let label = 'Queued';
  let showPulse = false;

  switch (normalizedStatus) {
    case 'running':
      badgeClass = 'status-badge-running';
      dotClass = 'badge-dot-running';
      label = 'Running';
      showPulse = true;
      break;
    case 'pass':
    case 'success':
    case 'completed':
      badgeClass = 'status-badge-pass';
      dotClass = 'badge-dot-pass';
      label = 'Pass';
      break;
    case 'fail':
    case 'failed':
    case 'error':
      badgeClass = 'status-badge-fail';
      dotClass = 'badge-dot-fail';
      label = 'Fail';
      break;
    case 'queued':
    default:
      badgeClass = 'status-badge-queued';
      label = 'Queued';
      break;
  }

  return (
    <div className={`status-badge ${badgeClass}`}>
      {showPulse && <span className="badge-dot badge-dot-running pulse-element" />}
      {!showPulse && dotClass && <span className={`badge-dot ${dotClass}`} />}
      <span>{label}</span>
    </div>
  );
}
