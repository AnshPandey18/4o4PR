import React, { useEffect, useRef } from 'react';
import './Terminal.css';

export default function Terminal({ logs = [] }) {
  const terminalEndRef = useRef(null);

  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  const formatLogLine = (line, idx) => {
    if (!line) return <div key={idx} className="terminal-log-empty" />;

    let color = 'var(--color-mist)';
    let fontWeight = 'normal';

    const isCommand = line.startsWith('Running command:') || 
                      line.startsWith('Initializing git clone') || 
                      line.startsWith('Staging files:') || 
                      line.startsWith('Committing patch:') || 
                      line.startsWith('Pushing branch:') || 
                      line.startsWith('Opening Pull Request');

    if (isCommand) {
      color = 'var(--color-sky-wash)';
      return (
        <div key={idx} className="terminal-log-command" style={{ color }}>
          <span className="terminal-prompt-symbol">$</span>
          {line}
        </div>
      );
    }

    if (line.includes('=== FAILURES ===') || line.includes('AssertionError:') || line.startsWith('E  ') || line.startsWith('>  ')) {
      color = 'var(--color-ember)';
    } else if (line.includes('=== PASSED ===') || line.includes('PASSED') || line.includes('successful') || line.includes('SUCCESS') || line.includes('COMPLETED') || line.includes('success')) {
      color = 'var(--color-vivid-mint)';
    } else if (line.startsWith('---') || line.startsWith('@@') || line.startsWith('+') || line.startsWith('-')) {
      if (line.startsWith('+')) {
        color = 'var(--color-vivid-mint)';
      } else if (line.startsWith('-')) {
        color = 'var(--color-ember)';
      } else {
        color = 'var(--color-lavender-mist)';
      }
    } else if (line.startsWith('===')) {
      color = 'var(--color-ash)';
    }

    return (
      <div key={idx} className="terminal-log-default" style={{ color, fontWeight }}>
        {line}
      </div>
    );
  };

  return (
    <div className="terminal-wrapper">
      {/* Title Bar */}
      <div className="terminal-title-bar">
        <div className="terminal-dots">
          <span className="terminal-dot terminal-dot-red" />
          <span className="terminal-dot terminal-dot-yellow" />
          <span className="terminal-dot terminal-dot-green" />
        </div>
        <span className="terminal-title-text">404PR-CONSOLE.sh</span>
        <div className="terminal-spacer" />
      </div>

      {/* Terminal Viewport */}
      <div className="terminal-viewport">
        {logs.length === 0 ? (
          <div className="terminal-idle">
            Console is idle. Trigger a run to stream execution logs.
          </div>
        ) : (
          logs.map((line, idx) => formatLogLine(line, idx))
        )}
        <div ref={terminalEndRef} />
      </div>
    </div>
  );
}
