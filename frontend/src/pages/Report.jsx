import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { getLatestDemoReport, getRunReport, listRuns, getRunsDirList, getMarkdownReport, getJsonArtifact } from '../services/api';
import {
  STATIC_BUG_REPORT,
  STATIC_BASELINE_RESULTS,
  STATIC_RUN_ID,
  STATIC_MD_CONTENT,
  STATIC_RUNS_DIR_LIST,
} from '../data/staticReport';
import './Report.css';

/* ─── HELPERS ── */
function relTime(iso) {
  if (!iso) return '—';
  const d = Date.now() - new Date(iso).getTime();
  const m = Math.floor(d / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function useInView(threshold = 0.15) {
  const ref = useRef(null);
  const [vis, setVis] = useState(false);
  useEffect(() => {
    const el = ref.current; if (!el) return;
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) setVis(true); }, { threshold });
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);
  return [ref, vis];
}

/* ─── ANIMATED COUNTER ── */
function Counter({ to, suffix = '', trigger }) {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (!trigger) return;
    let s = 0;
    const inc = to / (1200 / 16);
    const t = setInterval(() => {
      s += inc;
      if (s >= to) { setV(to); clearInterval(t); }
      else setV(parseFloat(s.toFixed(1)));
    }, 16);
    return () => clearInterval(t);
  }, [trigger, to]);
  const disp = Number.isInteger(to) ? Math.round(v) : v.toFixed(1);
  return <span>{trigger ? `${disp}${suffix}` : '—'}</span>;
}

/* ─── RADIAL RING ── */
function Ring({ pct, color, size = 72 }) {
  const r = (size - 10) / 2;
  const circ = 2 * Math.PI * r;
  const [off, setOff] = useState(circ);
  useEffect(() => { const t = setTimeout(() => setOff(circ - (pct / 100) * circ), 400); return () => clearTimeout(t); }, [pct, circ]);
  return (
    <svg width={size} height={size}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="5" />
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth="5"
        strokeLinecap="round" strokeDasharray={circ} strokeDashoffset={off}
        transform={`rotate(-90 ${size/2} ${size/2})`}
        style={{ transition: 'stroke-dashoffset 1.3s cubic-bezier(0.16,1,0.3,1)', filter: `drop-shadow(0 0 6px ${color})` }} />
      <text x={size/2} y={size/2+5} textAnchor="middle" fill="white" fontSize="13" fontWeight="700" fontFamily="Inter,sans-serif">{pct}%</text>
    </svg>
  );
}

/* ─── PIPELINE DOTS (5 fixed steps for display) ── */
const STEP_NAMES = ['Clone', 'Detect', 'Patch', 'Test', 'PR'];
function PipelineDots({ passed }) {
  // passed = true → all green, false → last two are fail/queued
  const steps = STEP_NAMES.map((name, i) => ({
    name,
    status: passed ? 'pass' : i < 3 ? 'pass' : i === 3 ? 'fail' : 'queued',
  }));
  return (
    <div className="rp-dots">
      {steps.map((s, i) => (
        <div key={i} className="rp-dot-wrap" title={s.name}>
          <div className={`rp-dot rp-dot-${s.status}`} />
          {i < steps.length - 1 && <div className={`rp-dot-line ${s.status === 'pass' ? 'rp-line-pass' : 'rp-line-dim'}`} />}
        </div>
      ))}
    </div>
  );
}

/* ─── DIFF VIEWER ── */
function Diff({ patch }) {
  if (!patch) return <p style={{ color: 'rgba(255,255,255,0.3)', fontSize: 12 }}>No patch data available.</p>;
  return (
    <div className="rp-diff">
      <div className="rp-diff-bar">
        <span className="rp-diff-label">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
          Generated diff
        </span>
      </div>
      <pre className="rp-diff-body">
        {patch.split('\n').map((ln, i) => {
          let cls = 'rp-dl';
          if (ln.startsWith('+') && !ln.startsWith('+++')) cls += ' rp-dl-add';
          else if (ln.startsWith('-') && !ln.startsWith('---')) cls += ' rp-dl-rem';
          else if (ln.startsWith('@@')) cls += ' rp-dl-meta';
          return <div key={i} className={cls}>{ln || ' '}</div>;
        })}
      </pre>
    </div>
  );
}

/* ─── SOURCE SNAPSHOT VIEWER ── */
function SourceSnapshot({ bug }) {
  const sym = bug?.called_symbols?.[0];
  const snapshot = sym?.source_snapshot || bug?.code || '';
  const file = sym?.file || bug?.inferred_source_module || 'unknown';
  if (!snapshot) return null;

  const lines = snapshot.split('\n');
  return (
    <div className="rp-diff">
      <div className="rp-diff-bar">
        <span className="rp-diff-label">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          {file}
        </span>
        <span style={{ marginLeft: 'auto', fontSize: 10, color: 'rgba(255,255,255,0.3)' }}>
          lines {sym?.line_start}–{sym?.line_end}
        </span>
      </div>
      <pre className="rp-diff-body">
        {lines.map((ln, i) => {
          const isBug = ln.includes('# BUG');
          return (
            <div key={i} className={`rp-dl${isBug ? ' rp-dl-rem' : ''}`}>
              <span style={{ color: 'rgba(255,255,255,0.2)', marginRight: 12, userSelect: 'none', fontSize: 10 }}>
                {String((sym?.line_start || 0) + i).padStart(3)}
              </span>
              {ln}
            </div>
          );
        })}
      </pre>
    </div>
  );
}

/* ─── BUG DETAIL PANEL ── */
function BugPanel({ bug, onClose }) {
  if (!bug) return null;
  const fa = bug.first_failing_assertion || {};
  const sym = bug.called_symbols?.[0];
  const srcFile = sym?.file || bug.inferred_source_module || '—';

  return (
    <>
      <div className="rp-backdrop" onClick={onClose} />
      <aside className="rp-panel">
        <div className={`rp-panel-strip strip-fail`} />

        <div className="rp-panel-head">
          <div className="rp-panel-head-left">
            <span className="rp-panel-id">{bug.bug_id?.slice(0, 14) || 'BUG'}</span>
            <h2 className="rp-panel-repo" style={{ fontSize: 16 }}>{bug.test_name?.split('::').pop() || bug.test_name}</h2>
          </div>
          <button className="rp-panel-close" onClick={onClose} aria-label="Close">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        {/* failure summary */}
        <div className="rp-outcome rp-outcome-fail">
          <div className="rp-outcome-orb orb-fail" />
          <div className="rp-outcome-text">
            <p className="rp-outcome-label">✗ {bug.error_type || 'Assertion Failed'}</p>
            <p className="rp-outcome-sub" style={{ fontFamily: 'monospace', fontSize: 11 }}>
              {bug.error_message?.split('\n')[0]?.slice(0, 80)}
            </p>
          </div>
        </div>

        {/* first failing assertion */}
        {fa.statement && (
          <div className="rp-ps">
            <span className="rp-ps-label">First Failing Assertion</span>
            <code style={{ fontSize: 12, color: 'rgba(255,255,255,0.7)', fontFamily: 'monospace', background: 'rgba(255,255,255,0.04)', padding: '10px 14px', borderRadius: 6, display: 'block', wordBreak: 'break-word' }}>
              {fa.statement}
            </code>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginTop: 4 }}>
              <span style={{ fontSize: 12 }}>
                <span style={{ color: 'rgba(255,255,255,0.3)' }}>expected: </span>
                <span style={{ color: '#20c2a4', fontFamily: 'monospace' }}>{fa.expected}</span>
              </span>
              <span style={{ fontSize: 12 }}>
                <span style={{ color: 'rgba(255,255,255,0.3)' }}>actual: </span>
                <span style={{ color: '#e6714f', fontFamily: 'monospace' }}>{fa.actual}</span>
              </span>
            </div>
          </div>
        )}

        {/* source location */}
        <div className="rp-ps">
          <span className="rp-ps-label">Source Location</span>
          <div className="rp-ps-chips">
            <span className="rp-chip-mono">📄 {srcFile}</span>
            {sym && <span className="rp-chip-mono">⚙ {sym.name}()</span>}
            {bug.location?.line_number && <span className="rp-chip-mono">line {bug.location.line_number}</span>}
          </div>
        </div>

        {/* source snapshot */}
        <div className="rp-ps">
          <span className="rp-ps-label">Buggy Source Code</span>
          <SourceSnapshot bug={bug} />
        </div>

        {/* rerun command */}
        {bug.rerun_command && (
          <div className="rp-ps">
            <span className="rp-ps-label">Rerun Command</span>
            <code style={{ fontSize: 11, color: '#20c2a4', fontFamily: 'monospace', background: 'rgba(32,194,164,0.06)', border: '1px solid rgba(32,194,164,0.2)', padding: '8px 12px', borderRadius: 6, display: 'block', wordBreak: 'break-all' }}>
              $ {bug.rerun_command}
            </code>
          </div>
        )}

        {/* actions */}
        <div className="rp-panel-actions">
          <button className="rp-btn-ghost" onClick={onClose}>Close</button>
        </div>
      </aside>
    </>
  );
}

/* ─── LOADING STATE ── */
function LoadingState() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '40vh', gap: 16 }}>
      <div style={{ width: 36, height: 36, border: '3px solid rgba(32,194,164,0.2)', borderTopColor: '#20c2a4', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
      <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: 13, fontFamily: 'IBM Plex Mono, monospace' }}>Loading report data…</p>
    </div>
  );
}

/* ─── ERROR STATE ── */
function ErrorState({ message, onRetry }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '40vh', gap: 16, padding: '0 24px', textAlign: 'center' }}>
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="rgba(230,113,79,0.6)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
      <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: 14, maxWidth: 400 }}>{message}</p>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center' }}>
        <button onClick={onRetry} style={{ padding: '9px 20px', background: 'rgba(32,194,164,0.1)', border: '1px solid rgba(32,194,164,0.3)', borderRadius: 99, color: '#20c2a4', fontSize: 12, cursor: 'pointer', fontFamily: 'IBM Plex Mono, monospace' }}>
          Retry
        </button>
        <p style={{ color: 'rgba(255,255,255,0.25)', fontSize: 12, margin: 'auto 0' }}>
          Make sure the backend is running: <code style={{ color: '#20c2a4' }}>uvicorn app.main:app --reload</code>
        </p>
      </div>
    </div>
  );
}

/* ─── JSON FILE POPUP MODAL ── */
function JsonModal({ runDir, filePath, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setLoading(true); setErr(null); setData(null);
    getJsonArtifact(runDir, filePath)
      .then(res => setData(res.data))
      .catch(e => setErr(e.message || 'Failed to load JSON'))
      .finally(() => setLoading(false));
  }, [runDir, filePath]);

  const pretty = data ? JSON.stringify(data, null, 2) : '';

  const handleCopy = () => {
    navigator.clipboard.writeText(pretty).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  // Escape key
  useEffect(() => {
    const fn = e => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', fn);
    return () => window.removeEventListener('keydown', fn);
  }, [onClose]);

  const fileName = filePath.split('/').pop();

  return (
    <>
      <div className="rp-json-backdrop" onClick={onClose} />
      <div className="rp-json-modal">
        {/* header */}
        <div className="rp-json-modal-head">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div className="rp-json-file-icon">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#20c2a4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            </div>
            <div>
              <p className="rp-json-modal-title">{fileName}</p>
              <p className="rp-json-modal-sub">{runDir} / {filePath}</p>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {data && (
              <button className="rp-json-copy-btn" onClick={handleCopy}>
                {copied ? (
                  <><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#27c93f" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg> Copied!</>
                ) : (
                  <><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copy</>
                )}
              </button>
            )}
            <button className="rp-panel-close" onClick={onClose} aria-label="Close">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
        </div>
        {/* body */}
        <div className="rp-json-modal-body">
          {loading && (
            <div className="rp-md-loading">
              <div className="rp-md-spin" />
              <span>Loading {fileName}…</span>
            </div>
          )}
          {err && <p style={{ color: '#e6714f', fontSize: 13, padding: 16 }}>Error: {err}</p>}
          {data && (
            <pre className="rp-json-pre">
              {colorizeJson(pretty)}
            </pre>
          )}
        </div>
      </div>
    </>
  );
}

/* simple JSON syntax colorizer */
function colorizeJson(str) {
  const parts = [];
  const regex = /("[^"]*"\s*:)|("[^"]*")|(-?\d+\.?\d*(?:[eE][+-]?\d+)?)|(true|false|null)/g;
  let lastIdx = 0, match;
  while ((match = regex.exec(str)) !== null) {
    if (match.index > lastIdx) parts.push(<span key={lastIdx} style={{ color: 'rgba(255,255,255,0.4)' }}>{str.slice(lastIdx, match.index)}</span>);
    if (match[1]) parts.push(<span key={match.index + 'k'} style={{ color: '#79b8ff' }}>{match[1]}</span>);
    else if (match[2]) parts.push(<span key={match.index + 's'} style={{ color: '#9ecbff' }}>{match[2]}</span>);
    else if (match[3]) parts.push(<span key={match.index + 'n'} style={{ color: '#f8b195' }}>{match[3]}</span>);
    else if (match[4]) parts.push(<span key={match.index + 'b'} style={{ color: '#79deff' }}>{match[4]}</span>);
    lastIdx = match.index + match[0].length;
  }
  if (lastIdx < str.length) parts.push(<span key={lastIdx + 'r'} style={{ color: 'rgba(255,255,255,0.4)' }}>{str.slice(lastIdx)}</span>);
  return parts;
}

/* ─── FULL-SCREEN MD MODAL ── */
function MdModal({ content, loading, onClose }) {
  // Escape key
  useEffect(() => {
    const fn = e => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', fn);
    return () => window.removeEventListener('keydown', fn);
  }, [onClose]);

  return (
    <div className="rp-md-modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="rp-md-modal">
        {/* header */}
        <div className="rp-md-modal-head">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div className="rp-json-file-icon" style={{ background: 'rgba(184,85,231,0.15)', borderColor: 'rgba(184,85,231,0.3)' }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#b855e7" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
            </div>
            <div>
              <p style={{ margin: 0, fontSize: 14, fontWeight: 700, color: '#fff', fontFamily: 'Inter, sans-serif' }}>bug_report.md</p>
              <p style={{ margin: 0, fontSize: 11, color: 'rgba(255,255,255,0.35)', fontFamily: 'IBM Plex Mono, monospace' }}>Full Pipeline Report</p>
            </div>
          </div>
          <button className="rp-panel-close" onClick={onClose} aria-label="Close">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        {/* body */}
        <div className="rp-md-modal-body">
          {loading ? (
            <div className="rp-md-loading" style={{ justifyContent: 'center', padding: '48px 0' }}>
              <div className="rp-md-spin" />
              <span>Loading bug_report.md…</span>
            </div>
          ) : (
            <MarkdownViewer content={content} />
          )}
        </div>
      </div>
    </div>
  );
}

/* ─── MARKDOWN VIEWER ── */
function MarkdownViewer({ content }) {
  if (!content) return null;

  const lines = content.split('\n');
  return (
    <div className="rp-md-viewer">
      {lines.map((line, i) => {
        // h1
        if (/^# /.test(line)) return <h1 key={i} className="rp-md-h1">{line.slice(2)}</h1>;
        // h2
        if (/^## /.test(line)) return <h2 key={i} className="rp-md-h2">{line.slice(3)}</h2>;
        // h3
        if (/^### /.test(line)) return <h3 key={i} className="rp-md-h3">{line.slice(4)}</h3>;
        // hr
        if (/^---/.test(line)) return <hr key={i} className="rp-md-hr" />;
        // code fence (toggle — just show as block)
        if (/^```/.test(line)) return <div key={i} className="rp-md-code-fence">{line}</div>;
        // bullet
        if (/^- /.test(line)) {
          const rest = line.slice(2).replace(/\*\*(.*?)\*\*/g, (_, t) => `<strong>${t}</strong>`);
          return <div key={i} className="rp-md-bullet" dangerouslySetInnerHTML={{ __html: `• ${rest}` }} />;
        }
        // bold inline in plain line
        if (/\*\*/.test(line)) {
          const html = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
          return <p key={i} className="rp-md-p" dangerouslySetInnerHTML={{ __html: html }} />;
        }
        // blank
        if (line.trim() === '') return <div key={i} className="rp-md-blank" />;
        // default
        return <p key={i} className="rp-md-p">{line}</p>;
      })}
    </div>
  );
}

/* ─── FILE TREE COMPONENT (flat list, no folder grouping) ── */
function FileTree({ files, hasMarkdown, onOpenJson, onOpenMd, mdLoading }) {
  const [hovered, setHovered] = useState(null);

  const allFiles = (files || []);

  const jsonIcon = <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#20c2a4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>;
  const mdIcon   = <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#b855e7" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>;

  if (allFiles.length === 0 && !hasMarkdown) {
    return <p style={{ padding: '16px 20px', color: 'rgba(255,255,255,0.25)', fontSize: 12, fontFamily: 'IBM Plex Mono, monospace' }}>No files found for this run.</p>;
  }

  return (
    <div className="rp-ftree">
      {allFiles.map(filePath => {
        const name = filePath.split('/').pop();
        return (
          <button
            key={filePath}
            className={`rp-ftree-file${hovered === filePath ? ' rp-ftree-file-hov' : ''}`}
            onClick={() => onOpenJson(filePath)}
            onMouseEnter={() => setHovered(filePath)}
            onMouseLeave={() => setHovered(null)}
            title={`Open ${filePath}`}
          >
            <span className="rp-ftree-file-icon">{jsonIcon}</span>
            <span className="rp-ftree-file-name">{name}</span>
            <span className="rp-ftree-file-path">{filePath}</span>
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="rgba(32,194,164,0.4)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginLeft: 'auto', flexShrink: 0 }}>
              <polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>
            </svg>
          </button>
        );
      })}

      {/* markdown report row */}
      {hasMarkdown && (
        <button
          className={`rp-ftree-file rp-ftree-file-md${hovered === '__md' ? ' rp-ftree-file-hov' : ''}`}
          onClick={onOpenMd}
          onMouseEnter={() => setHovered('__md')}
          onMouseLeave={() => setHovered(null)}
          disabled={mdLoading}
          title="View full markdown report"
        >
          <span className="rp-ftree-file-icon">{mdIcon}</span>
          <span className="rp-ftree-file-name" style={{ color: '#d08cf7' }}>bug_report.md</span>
          <span className="rp-ftree-file-path">detector/bug_report.md</span>
          {mdLoading
            ? <div className="rp-md-spin" style={{ width: 10, height: 10, borderWidth: '2px', marginLeft: 'auto', flexShrink: 0 }} />
            : <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="rgba(184,85,231,0.5)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginLeft: 'auto', flexShrink: 0 }}>
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
              </svg>
          }
        </button>
      )}
    </div>
  );
}

/* ─── SEVERITY HELPER ── */
function inferSeverity(bug) {
  const msg = (bug.error_message || '').toLowerCase();
  const src = (bug.inferred_source_module || '').toLowerCase();
  if (msg.includes('zero') || src.includes('auth') || src.includes('security')) return 'High';
  if (msg.includes('assert') || src.includes('string')) return 'Medium';
  return 'Low';
}

/* ─── BUILD RUN OBJECTS from bug_report.json ── */
function buildRunsFromReport(report, groups, runDir, baseline) {
  if (!report) return [];
  const summary = report.summary || {};
  const bugs = report.bugs || [];
  const ts = report.timestamp || new Date().toISOString();
  const baselineTests = baseline?.results || {};

  // Aggregate by source file
  const byFile = {};
  bugs.forEach(b => {
    const src = b.inferred_source_module || 'unknown';
    if (!byFile[src]) byFile[src] = [];
    byFile[src].push(b);
  });

  const fileKeys = Object.keys(byFile);

  return fileKeys.map((srcFile, idx) => {
    const fileBugs = byFile[srcFile];
    const sev = inferSeverity(fileBugs[0]);
    const patch = buildPatch(fileBugs[0]);

    // Filter baseline results relevant to this source file
    const relevantTests = Object.entries(baselineTests).filter(([testPath]) => {
      const inferredSrc = testPath.replace('tests/test_', 'src/').replace('.py::', '.py::').split('::')[0];
      return inferredSrc === srcFile || testPath.includes(srcFile.replace('src/', '').replace('.py', ''));
    });

    return {
      id: `${report.run_id}-${idx}`,
      run_id: report.run_id,
      run_dir: runDir,
      repo: `demo/sample_bugs → ${srcFile}`,
      bug: `${fileBugs.length} bug${fileBugs.length > 1 ? 's' : ''} detected in ${srcFile}`,
      status: 'fail',
      branch: 'demo/fixture',
      pr: null,
      duration: `${summary.duration_seconds?.toFixed(2) || '?'}s`,
      testsTotal: summary.tests_run || 0,
      testsPassed: summary.passed || 0,
      testsFailed: summary.failed || 0,
      timestamp: ts,
      severity: sev,
      steps: [
        { name: 'Clone Repo',     status: 'pass',   ms: 120  },
        { name: 'Detect Bug',     status: 'pass',   ms: Math.round((summary.duration_seconds || 0.1) * 1000) },
        { name: 'Generate Patch', status: 'pass',   ms: 0    },
        { name: 'Run Tests',      status: 'fail',   ms: 0    },
        { name: 'Open PR',        status: 'queued', ms: 0    },
      ],
      patch,
      bugs: fileBugs,
      baselineTests: relevantTests,
      allBaselineTests: baselineTests,
    };
  });
}

function buildPatch(bug) {
  if (!bug) return null;
  const sym = bug.called_symbols?.[0];
  const fa = bug.first_failing_assertion || {};
  const loc = bug.location || {};
  const ln = loc.line_number || sym?.line_start || 0;
  const src = sym?.file || bug.inferred_source_module || 'unknown';
  return (
    `@@ -${ln},3 +${ln},3 @@\n` +
    ` # ${src}\n` +
    `-# BUG: ${bug.error_message?.split('\n')[0]?.slice(0, 60) || ''}\n` +
    `+# FIX: expected ${fa.expected}, got ${fa.actual}\n` +
    (sym?.source_snapshot?.split('\n').slice(0, 3).join('\n') || '')
  );
}

/* ─── DETAIL PANEL (run-level) ── */
function DetailPanel({ run, onClose, onRunAgain, onSelectBug }) {
  const passPct = run.testsTotal > 0 ? Math.round((run.testsPassed / run.testsTotal) * 100) : 0;
  return (
    <>
      <div className="rp-backdrop" onClick={onClose} />
      <aside className="rp-panel">
        <div className={`rp-panel-strip strip-${run.status}`} />

        <div className="rp-panel-head">
          <div className="rp-panel-head-left">
            <span className="rp-panel-id">{run.id}</span>
            <h2 className="rp-panel-repo">{run.repo}</h2>
          </div>
          <button className="rp-panel-close" onClick={onClose} aria-label="Close">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        {/* outcome hero */}
        <div className={`rp-outcome rp-outcome-${run.status === 'success' ? 'success' : 'fail'}`}>
          <div className={`rp-outcome-orb orb-${run.status === 'success' ? 'success' : 'fail'}`} />
          <div className="rp-outcome-text">
            <p className="rp-outcome-label">{run.status === 'success' ? '✓  Patch applied & PR opened' : `✗  ${run.bugs?.length || 0} bugs detected`}</p>
            <p className="rp-outcome-sub">{run.duration} · {relTime(run.timestamp)}</p>
          </div>
          {run.pr && (
            <a href={`https://github.com/${run.repo}/pull/${run.pr}`} target="_blank" rel="noopener noreferrer"
               className="rp-pr-pill" onClick={e => e.stopPropagation()}>
              PR #{run.pr}
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="7" y1="17" x2="17" y2="7"/><polyline points="7 7 17 7 17 17"/></svg>
            </a>
          )}
        </div>

        {/* bug context */}
        <div className="rp-ps">
          <span className="rp-ps-label">Detection Summary</span>
          <p className="rp-ps-bug">{run.bug}</p>
          <div className="rp-ps-chips">
            <span className={`rp-sev rp-sev-${run.severity.toLowerCase()}`}>{run.severity} severity</span>
            <span className="rp-chip-mono">⎇ {run.branch}</span>
          </div>
        </div>

        {/* individual bugs list */}
        {run.bugs?.length > 0 && (
          <div className="rp-ps">
            <span className="rp-ps-label">Detected Bugs ({run.bugs.length})</span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {run.bugs.map((b, i) => (
                <button
                  key={b.bug_id || i}
                  onClick={() => onSelectBug(b)}
                  style={{
                    display: 'flex', alignItems: 'flex-start', gap: 10,
                    padding: '10px 12px', background: 'rgba(255,255,255,0.03)',
                    border: '1px solid rgba(255,255,255,0.07)', borderRadius: 8,
                    cursor: 'pointer', textAlign: 'left', transition: 'background .15s, border-color .15s',
                    width: '100%',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; e.currentTarget.style.borderColor = 'rgba(255,255,255,0.14)'; }}
                  onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.03)'; e.currentTarget.style.borderColor = 'rgba(255,255,255,0.07)'; }}
                >
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#e6714f', boxShadow: '0 0 6px rgba(230,113,79,0.6)', flexShrink: 0, marginTop: 4 }} />
                  <div style={{ minWidth: 0 }}>
                    <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.75)', margin: 0, fontFamily: 'IBM Plex Mono, monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {b.test_name?.split('::').pop() || b.test_name}
                    </p>
                    <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', margin: '3px 0 0', fontFamily: 'IBM Plex Mono, monospace' }}>
                      {b.error_message?.split('\n')[0]?.slice(0, 60)}
                    </p>
                  </div>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, marginLeft: 'auto', marginTop: 4 }}><polyline points="9 18 15 12 9 6"/></svg>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* baseline test results table */}
        {run.allBaselineTests && Object.keys(run.allBaselineTests).length > 0 && (
          <div className="rp-ps">
            <span className="rp-ps-label">Baseline Test Results ({Object.keys(run.allBaselineTests).length} tests)</span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {Object.entries(run.allBaselineTests).map(([testPath, status]) => {
                const name = testPath.split('::').pop();
                const file = testPath.split('::')[0];
                const passed = status === 'passed';
                return (
                  <div key={testPath} style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '7px 10px',
                    background: passed ? 'rgba(39,201,63,0.04)' : 'rgba(230,113,79,0.04)',
                    border: `1px solid ${passed ? 'rgba(39,201,63,0.12)' : 'rgba(230,113,79,0.12)'}`,
                    borderRadius: 6,
                  }}>
                    <span style={{
                      width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
                      background: passed ? '#27c93f' : '#e6714f',
                      boxShadow: `0 0 5px ${passed ? 'rgba(39,201,63,0.6)' : 'rgba(230,113,79,0.6)'}`,
                    }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.65)', fontFamily: 'IBM Plex Mono, monospace', display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {name}
                      </span>
                      <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)', fontFamily: 'IBM Plex Mono, monospace' }}>
                        {file}
                      </span>
                    </div>
                    <span style={{
                      fontSize: 10, fontWeight: 700, fontFamily: 'IBM Plex Mono, monospace',
                      color: passed ? '#27c93f' : '#e6714f',
                      background: passed ? 'rgba(39,201,63,0.1)' : 'rgba(230,113,79,0.1)',
                      border: `1px solid ${passed ? 'rgba(39,201,63,0.25)' : 'rgba(230,113,79,0.25)'}`,
                      padding: '2px 8px', borderRadius: 4, textTransform: 'uppercase',
                    }}>
                      {status}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* step timeline */}
        <div className="rp-ps">
          <span className="rp-ps-label">Step Timeline</span>
          <div className="rp-timeline">
            {run.steps.map((step, i) => (
              <div key={i} className="rp-tl-row">
                <div className="rp-tl-left">
                  <div className={`rp-tl-dot tl-${step.status}`}>
                    {step.status === 'pass'   && <svg width="8" height="7" viewBox="0 0 10 8" fill="none"><path d="M1 4L3.5 6.5L9 1" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>}
                    {step.status === 'fail'   && <svg width="8" height="8" viewBox="0 0 10 10" fill="none"><line x1="2" y1="2" x2="8" y2="8" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/><line x1="8" y1="2" x2="2" y2="8" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>}
                    {step.status === 'queued' && <span className="rp-tl-dash">—</span>}
                  </div>
                  {i < run.steps.length - 1 && <div className={`rp-tl-line tl-line-${step.status === 'pass' ? 'pass' : 'dim'}`} />}
                </div>
                <div className="rp-tl-content">
                  <span className="rp-tl-name">{step.name}</span>
                  {step.ms > 0 && <span className="rp-tl-ms">{step.ms}ms</span>}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* test results */}
        <div className="rp-ps">
          <span className="rp-ps-label">Test Results</span>
          <div className="rp-test-track">
            {run.testsPassed > 0 && <div className="rp-test-fill rp-fill-pass" style={{ width: `${passPct}%` }} />}
            {run.testsFailed > 0 && <div className="rp-test-fill rp-fill-fail" style={{ width: `${Math.round((run.testsFailed/run.testsTotal)*100)}%` }} />}
          </div>
          <div className="rp-test-legend">
            <span className="rp-leg-pass">✓ {run.testsPassed} passed</span>
            {run.testsFailed > 0 && <span className="rp-leg-fail">✗ {run.testsFailed} failed</span>}
            <span className="rp-leg-total">{run.testsTotal} total</span>
          </div>
        </div>

        {/* diff */}
        <div className="rp-ps"><span className="rp-ps-label">Generated Patch Preview</span><Diff patch={run.patch} /></div>

        {/* actions */}
        <div className="rp-panel-actions">
          <button className="rp-btn-ghost" onClick={onClose}>Close</button>
          <button className="rp-btn-primary" onClick={onRunAgain}>Run Again</button>
        </div>
      </aside>
    </>
  );
}

/* ─── MAIN ── */
export default function Report({ completedRun }) {
  const navigate = useNavigate();
  const pageRef  = useRef(null);
  const [selectedRun,  setSelectedRun]  = useState(null);
  const [selectedBug,  setSelectedBug]  = useState(null);
  const [filter,       setFilter]       = useState('all');
  const [visible,      setVisible]      = useState([]);
  const [statsRef, statsVis] = useInView(0.2);

  // real data state
  const [runs,        setRuns]        = useState([]);
  const [loading,     setLoading]     = useState(true);
  const [error,       setError]       = useState(null);
  const [runId,       setRunId]       = useState(completedRun?.runId || null);
  const [isLiveData,  setIsLiveData]  = useState(false);

  // File browser state
  const [runsDirList,   setRunsDirList]   = useState([]);
  const [selectedDir,   setSelectedDir]   = useState(null);   // selected run folder
  const [selectedJson,  setSelectedJson]  = useState('');     // selected JSON file path
  // JSON popup
  const [jsonModal,     setJsonModal]     = useState(null);   // { runDir, filePath }
  // MD full-screen modal
  const [mdContent,     setMdContent]     = useState(null);
  const [mdLoading,     setMdLoading]     = useState(false);
  const [mdModalOpen,   setMdModalOpen]   = useState(false);

  // Load ALL run dirs list — fallback to static list
  useEffect(() => {
    getRunsDirList()
      .then(d => {
        const all = d.runs || [];
        if (all.length > 0) {
          setRunsDirList(all);
          setSelectedDir(all[0].run_dir);
          // Pre-select first JSON file if any
          const firstJson = (all[0].files || []).find(f => f.endsWith('.json'));
          setSelectedJson(firstJson || '');
        } else {
          setRunsDirList(STATIC_RUNS_DIR_LIST);
          setSelectedDir(STATIC_RUNS_DIR_LIST[0].run_dir);
          const firstJson = (STATIC_RUNS_DIR_LIST[0].files || []).find(f => f.endsWith('.json'));
          setSelectedJson(firstJson || '');
        }
      })
      .catch(() => {
        setRunsDirList(STATIC_RUNS_DIR_LIST);
        setSelectedDir(STATIC_RUNS_DIR_LIST[0].run_dir);
        const firstJson = (STATIC_RUNS_DIR_LIST[0].files || []).find(f => f.endsWith('.json'));
        setSelectedJson(firstJson || '');
      });
  }, []);

  // Current dir entry
  const currentDirEntry = runsDirList.find(r => r.run_dir === selectedDir);
  const jsonFiles = (currentDirEntry?.files || []).filter(f => f.endsWith('.json'));
  const hasMarkdown = currentDirEntry?.has_markdown ?? false;

  // Open JSON popup
  const openJson = () => {
    if (!selectedDir || !selectedJson) return;
    setJsonModal({ runDir: selectedDir, filePath: selectedJson });
  };

  // Open MD full-screen modal
  const openMd = async () => {
    if (!selectedDir) return;
    setMdLoading(true);
    setMdContent(null);
    setMdModalOpen(true);
    try {
      const res = await getMarkdownReport(selectedDir);
      setMdContent(res.markdown);
    } catch {
      setMdContent(STATIC_MD_CONTENT);
    } finally {
      setMdLoading(false);
    }
  };

  /* parallax orbs */
  useEffect(() => {
    const el = pageRef.current; if (!el) return;
    const fn = (e) => {
      const cx = window.innerWidth/2, cy = window.innerHeight/2;
      el.style.setProperty('--ox', `${((e.clientX-cx)/cx)*18}px`);
      el.style.setProperty('--oy', `${((e.clientY-cy)/cy)*12}px`);
    };
    window.addEventListener('mousemove', fn);
    return () => window.removeEventListener('mousemove', fn);
  }, []);

  /* escape key */
  useEffect(() => {
    const fn = e => {
      if (e.key === 'Escape') {
        if (selectedBug) { setSelectedBug(null); return; }
        setSelectedRun(null);
      }
    };
    window.addEventListener('keydown', fn);
    return () => window.removeEventListener('keydown', fn);
  }, [selectedBug]);

  /* load report data — falls back to static embedded data if backend is offline */
  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getLatestDemoReport();
      const builtRuns = buildRunsFromReport(
        data.bug_report,
        data.bug_groups,
        data.run_dir,
        data.baseline_results
      );
      if (builtRuns.length === 0) throw new Error('No runs returned from backend');
      setRuns(builtRuns);
      setRunId(data.bug_report?.run_id);
      setIsLiveData(true);
    } catch {
      // Backend offline — use static embedded data so the page always renders
      const builtRuns = buildRunsFromReport(
        STATIC_BUG_REPORT,
        null,
        STATIC_RUN_ID,
        STATIC_BASELINE_RESULTS
      );
      setRuns(builtRuns);
      setRunId(STATIC_RUN_ID);
      setIsLiveData(false);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  /* stagger cards once loaded */
  useEffect(() => {
    if (runs.length === 0) return;
    setVisible([]);
    const t = setTimeout(() => {
      runs.forEach((_, i) => setTimeout(() => setVisible(p => [...p, i]), i * 70));
    }, 150);
    return () => clearTimeout(t);
  }, [runs]);

  /* derived stats */
  const totalBugs    = runs.reduce((s, r) => s + (r.bugs?.length || 0), 0);
  const totalTests   = runs[0]?.testsTotal || 0;
  const totalPassed  = runs[0]?.testsPassed || 0;
  const passRate     = totalTests > 0 ? Math.round((totalPassed / totalTests) * 100) : 0;

  const STATS = [
    { label: 'Bugs Detected',  value: totalBugs,   suffix: '',  color: '#e6714f', bg: 'rgba(230,113,79,0.08)',   border: 'rgba(230,113,79,0.2)',   icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg> },
    { label: 'Tests Run',      value: totalTests,  suffix: '',  color: 'var(--color-electric-signal)', bg: 'rgba(0,136,255,0.08)', border: 'rgba(0,136,255,0.2)', icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> },
    { label: 'Tests Passed',   value: totalPassed, suffix: '',  color: 'var(--color-vivid-mint)',      bg: 'rgba(39,201,63,0.08)',   border: 'rgba(39,201,63,0.2)',   icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg> },
    { label: 'Source Files',   value: runs.length, suffix: '',  color: 'var(--color-lavender-mist)',   bg: 'rgba(184,85,231,0.08)',  border: 'rgba(184,85,231,0.2)',  icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg> },
  ];

  const filtered = runs.filter(r => filter === 'all' || r.status === filter);

  return (
    <div className="rp-page" ref={pageRef}>
      <div className="rp-orb rp-orb-1" /><div className="rp-orb rp-orb-2" /><div className="rp-orb rp-orb-3" />

      <div className="rp-inner page-wrapper">

        {/* ── PAGE HEADER ── */}
        <div className="rp-header">
          <div className="rp-header-left">
            <span className="rp-eyebrow">Analytics</span>
            <h1 className="rp-title">Bug Detection Report</h1>
            <p className="rp-subtitle">
              {isLiveData
                ? <>Results from run <code style={{ fontFamily: 'monospace', color: '#20c2a4' }}>{runId}</code> — live data from <code style={{ fontFamily: 'monospace', color: '#20c2a4' }}>backend/runs/</code></>
                : <>Showing cached results from run <code style={{ fontFamily: 'monospace', color: '#20c2a4' }}>{runId}</code> — start the backend for live data</>}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <button className="rp-btn-ghost" onClick={loadData} title="Refresh from backend">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-4.17"/></svg>
              Refresh
            </button>
            <button className="rp-btn-primary rp-new-btn" onClick={() => navigate('/run')}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
              New Run
            </button>
          </div>
        </div>

        {/* ── FILE BROWSER SECTION ── */}
        {runsDirList.length > 0 && (
          <div className="rp-md-section">
            <div className="rp-md-section-head">
              <div className="rp-md-section-title">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                Pipeline Run Files
                <span className="rp-md-badge">runs/</span>
              </div>
            </div>

            <FileTree
              files={[]}
              hasMarkdown={hasMarkdown}
              selectedDir={selectedDir}
              onOpenJson={(filePath) => setJsonModal({ runDir: selectedDir, filePath })}
              onOpenMd={openMd}
              mdLoading={mdLoading}
            />
          </div>
        )}

        {loading && <LoadingState />}
        {!loading && error && <ErrorState message={error} onRetry={loadData} />}

        {!loading && !error && (
          <>
            {/* ── STATS ── */}
            <div ref={statsRef} className={`rp-stats ${statsVis ? 'rp-vis' : ''}`}>
              {STATS.map((s, i) => (
                <div key={s.label} className="rp-stat-card" style={{ '--i': i }}>
                  <div className="rp-stat-card-glow" style={{ background: `radial-gradient(circle at 30% 30%, ${s.bg.replace('0.08','0.5')} 0%, transparent 70%)` }} />
                  <div className="rp-stat-icon" style={{ background: s.bg, border: `1px solid ${s.border}`, color: s.color }}>{s.icon}</div>
                  <div className="rp-stat-text">
                    <span className="rp-stat-val" style={{ color: s.color }}>
                      <Counter to={s.value} suffix={s.suffix} trigger={statsVis} />
                    </span>
                    <span className="rp-stat-lbl">{s.label}</span>
                  </div>
                </div>
              ))}
              {/* radial pass-rate */}
              <div className="rp-stat-card rp-stat-ring" style={{ '--i': 4 }}>
                <div className="rp-stat-card-glow" style={{ background: 'radial-gradient(circle at 50% 50%, rgba(39,201,63,0.2) 0%, transparent 70%)' }} />
                {statsVis && <Ring pct={passRate} color="var(--color-vivid-mint)" size={72} />}
                <span className="rp-stat-lbl" style={{ marginTop: 4 }}>Pass Rate</span>
              </div>
            </div>

            {/* ── run id banner ── */}
            {runId && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '12px 20px', marginBottom: 24,
                background: 'rgba(32,194,164,0.06)', border: '1px solid rgba(32,194,164,0.2)',
                borderRadius: 8, flexWrap: 'wrap',
              }}>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#20c2a4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                <span style={{ fontSize: 12, color: '#20c2a4', fontFamily: 'IBM Plex Mono, monospace' }}>
                  Run ID: <strong>{runId}</strong>
                </span>
                <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.3)', fontFamily: 'IBM Plex Mono, monospace' }}>
                  Input: backend/tests/fixtures/sample_bugs → Output: backend/runs/{runId}/
                </span>
              </div>
            )}

            {/* ── FILTER BAR ── */}
            <div className="rp-filter-bar">
              {[
                { key: 'all',     label: 'All Files', color: 'var(--color-ash)' },
                { key: 'success', label: 'Passed',    color: 'var(--color-vivid-mint)' },
                { key: 'fail',    label: 'Failed',    color: 'var(--color-ember)' },
              ].map(f => (
                <button key={f.key} className={`rp-ftab ${filter === f.key ? 'rp-ftab-on' : ''}`} onClick={() => setFilter(f.key)}>
                  <span className="rp-ftab-dot" style={{ background: f.color, boxShadow: filter === f.key ? `0 0 6px ${f.color}` : 'none' }} />
                  {f.label}
                  <span className="rp-ftab-count">{f.key === 'all' ? runs.length : runs.filter(r => r.status === f.key).length}</span>
                </button>
              ))}
            </div>

            {/* ── RUN LIST ── */}
            <div className="rp-list">
              {filtered.length === 0 && <div className="rp-empty">No results match this filter.</div>}
              {filtered.map((run) => {
                const idx = runs.indexOf(run);
                const isVis = visible.includes(idx);
                return (
                  <div key={run.id}
                    className={`rp-card ${isVis ? 'rp-card-in' : ''} rp-card-${run.status}`}
                    onClick={() => setSelectedRun(run)} role="button" tabIndex={0}
                    onKeyDown={e => e.key === 'Enter' && setSelectedRun(run)}
                  >
                    <div className={`rp-card-accent accent-${run.status}`} />
                    <div className="rp-card-hover-glow" />
                    <div className="rp-card-body">
                      {/* left */}
                      <div className="rp-card-left">
                        <div className="rp-card-top-row">
                          <span className="rp-card-repo">{run.repo}</span>
                          <span className={`rp-sev rp-sev-${run.severity.toLowerCase()}`}>{run.severity}</span>
                        </div>
                        <p className="rp-card-bug">{run.bug}</p>
                        <div className="rp-card-meta">
                          <span className="rp-card-id">{run.run_id}</span>
                          <span className="rp-card-time">{relTime(run.timestamp)}</span>
                        </div>
                      </div>
                      {/* center */}
                      <div className="rp-card-center">
                        <PipelineDots passed={run.status === 'success'} />
                        <span className="rp-card-dur">
                          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                          {run.duration}
                        </span>
                      </div>
                      {/* right */}
                      <div className="rp-card-right">
                        <div className="rp-card-tests">
                          <span className="rp-t-pass">{run.testsPassed} passed</span>
                          {run.testsFailed > 0 && <span className="rp-t-fail">{run.testsFailed} failed</span>}
                          <span className="rp-t-total">/ {run.testsTotal}</span>
                        </div>
                        <div className={`rp-badge rp-badge-${run.status}`}>
                          <span className={`rp-badge-dot ${run.status === 'fail' ? 'rp-blink' : ''}`} />
                          {run.bugs?.length ? `${run.bugs.length} bugs` : run.status === 'success' ? 'Passed' : 'Failed'}
                        </div>
                        <span className="rp-card-arrow">→</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>

      {/* ── DETAIL PANEL ── */}
      {selectedRun && !selectedBug && (
        <DetailPanel
          run={selectedRun}
          onClose={() => setSelectedRun(null)}
          onRunAgain={() => navigate('/run')}
          onSelectBug={(bug) => setSelectedBug(bug)}
        />
      )}

      {/* ── BUG DETAIL PANEL ── */}
      {selectedBug && (
        <BugPanel
          bug={selectedBug}
          onClose={() => setSelectedBug(null)}
        />
      )}

      {/* ── JSON FILE POPUP ── */}
      {jsonModal && (
        <JsonModal
          runDir={jsonModal.runDir}
          filePath={jsonModal.filePath}
          onClose={() => setJsonModal(null)}
        />
      )}

      {/* ── MD FULL-SCREEN MODAL ── */}
      {mdModalOpen && (
        <MdModal
          content={mdContent}
          loading={mdLoading}
          onClose={() => setMdModalOpen(false)}
        />
      )}
    </div>
  );
}
