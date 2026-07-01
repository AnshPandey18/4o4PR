import React from 'react';
import StatusBadge from './StatusBadge';
import './StepTracker.css';

export default function StepTracker({ steps = [], currentStepIndex = 0, pipelineStatus = 'idle' }) {
  return (
    <div className="steptracker-wrapper">
      <h3 className="steptracker-title">Pipeline Progress</h3>

      <div className="steptracker-list">
        {steps.map((step, idx) => {
          const isCompleted = idx < currentStepIndex && pipelineStatus !== 'failed';
          const isActive = idx === currentStepIndex && pipelineStatus === 'running';
          const isFailedStep = idx === currentStepIndex && pipelineStatus === 'failed';
          const isPending = idx > currentStepIndex || pipelineStatus === 'idle';

          let stepStatus = 'queued';
          if (isCompleted) stepStatus = 'pass';
          else if (isActive) stepStatus = 'running';
          else if (isFailedStep) stepStatus = 'fail';

          // Node Circle classes
          let nodeClass = 'step-node-queued';
          if (isCompleted) nodeClass = 'step-node-completed';
          else if (isActive) nodeClass = 'step-node-active';
          else if (isFailedStep) nodeClass = 'step-node-failed';

          // Connector line classes
          const connectorClass = isCompleted ? 'step-connector-completed' : 'step-connector-pending';

          // Text classes
          const nameWeightClass = (isActive || isFailedStep) ? 'step-name-highlighted' : 'step-name-regular';
          const nameColorClass = isPending ? 'step-name-pending' : 'step-name-standard';
          const descColorClass = isPending ? 'step-desc-pending' : 'step-desc-standard';

          return (
            <div key={step.id} className="step-item">
              {/* Connector line */}
              {idx < steps.length - 1 && (
                <div className={`step-connector ${connectorClass}`} />
              )}

              {/* Node Bullet */}
              <div className={`step-node ${nodeClass}`}>
                {isCompleted && (
                  <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
                    <path
                      d="M1 4L3.5 6.5L9 1"
                      stroke="var(--color-midnight)"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                )}
                {isActive && (
                  <span className="step-node-active-bullet" />
                )}
              </div>

              {/* Label Content */}
              <div className="step-content">
                <div className="step-text-container">
                  <span className={`step-name ${nameWeightClass} ${nameColorClass}`}>
                    {step.name}
                  </span>
                  <span className={`step-description ${descColorClass}`}>
                    {step.description}
                  </span>
                </div>

                <StatusBadge status={stepStatus} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
