import { useRef, useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '../components/Button';
import './Landing.css';

/* ── scroll-triggered visibility hook ── */
function useInView(threshold = 0.15) {
  const ref = useRef(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) setVisible(true); }, { threshold });
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);
  return [ref, visible];
}

/* ── animated number counter ── */
function Counter({ target, suffix = '', trigger }) {
  const [val, setVal] = useState(0);
  useEffect(() => {
    if (!trigger) return;
    let start = 0;
    const num = parseFloat(target.replace(/[^0-9.]/g, ''));
    const duration = 1400;
    const step = num / (duration / 16);
    const t = setInterval(() => {
      start += step;
      if (start >= num) { setVal(num); clearInterval(t); }
      else setVal(parseFloat(start.toFixed(1)));
    }, 16);
    return () => clearInterval(t);
  }, [trigger, target]);
  const display = target.includes('+') ? `${Math.round(val).toLocaleString()}+`
    : target.includes('%') ? `${Number.isInteger(parseFloat(target)) ? Math.round(val) : val.toFixed(1)}%`
    : `${val}${suffix}`;
  return <span>{trigger ? display : '—'}</span>;
}

const WORKFLOW_STEPS = [
  { n: '01', title: 'Clone Repository',  desc: 'Fetches the target repo and sets up an isolated workspace with all dependencies.',                            color: 'var(--color-electric-signal)', bg: 'rgba(0,136,255,0.08)',   border: 'rgba(0,136,255,0.18)',   icon: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg> },
  { n: '02', title: 'Reproduce Bug',      desc: 'Runs failing test cases and maps the stack trace to confirm the defect location.',                            color: 'var(--color-ember)',            bg: 'rgba(230,113,79,0.08)',   border: 'rgba(230,113,79,0.18)',  icon: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg> },
  { n: '03', title: 'Generate Patch',     desc: 'Gemini 2.5 Pro analyzes the AST, reasons about the failure, and writes a candidate fix.',                   color: 'var(--color-lavender-mist)',    bg: 'rgba(184,85,231,0.08)',   border: 'rgba(184,85,231,0.18)',  icon: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> },
  { n: '04', title: 'Run Tests',          desc: 'Executes the full pytest suite inside a Docker container to verify zero regressions.',                        color: 'var(--color-vivid-mint)',       bg: 'rgba(39,201,63,0.08)',    border: 'rgba(39,201,63,0.18)',   icon: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg> },
  { n: '05', title: 'Open Pull Request',  desc: 'Pushes a clean branch and opens a detailed PR with an AI-written root-cause explanation.',                   color: 'var(--color-amber-glow)',       bg: 'rgba(255,183,100,0.08)', border: 'rgba(255,183,100,0.18)', icon: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M13 6h3a2 2 0 0 1 2 2v7"/><line x1="6" y1="9" x2="6" y2="21"/></svg> },
  { n: '06', title: 'Done',              desc: 'Validated, committed, and ready for your code review. Merge when satisfied.',                                   color: 'var(--color-sky-wash)',         bg: 'rgba(96,165,250,0.08)',   border: 'rgba(96,165,250,0.18)',  icon: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg> },
];

const STATS = [
  { value: '2,400+', label: 'Patches Generated', color: 'var(--color-electric-signal)' },
  { value: '94.2%',  label: 'Test Pass Rate',     color: 'var(--color-vivid-mint)' },
  { value: '15s',    label: 'Avg Solve Time',     color: 'var(--color-lavender-mist)' },
  { value: '680+',   label: 'PRs Merged',         color: 'var(--color-amber-glow)' },
];

export default function Landing() {
  const navigate  = useNavigate();
  const pageRef   = useRef(null);
  const heroRef   = useRef(null);

  /* mouse parallax for global orbs */
  useEffect(() => {
    const el = pageRef.current;
    if (!el) return;
    const move = (e) => {
      const cx = window.innerWidth / 2, cy = window.innerHeight / 2;
      el.style.setProperty('--orb-dx', `${((e.clientX - cx) / cx) * 20}px`);
      el.style.setProperty('--orb-dy', `${((e.clientY - cy) / cy) * 14}px`);
    };
    window.addEventListener('mousemove', move);
    return () => window.removeEventListener('mousemove', move);
  }, []);

  /* cursor spotlight inside hero */
  const handleHeroMove = useCallback((e) => {
    const hero = heroRef.current;
    if (!hero) return;
    const r = hero.getBoundingClientRect();
    hero.style.setProperty('--cx', `${((e.clientX - r.left) / r.width) * 100}%`);
    hero.style.setProperty('--cy', `${((e.clientY - r.top)  / r.height) * 100}%`);
    hero.style.setProperty('--co', '1');
  }, []);
  const handleHeroLeave = useCallback(() => {
    heroRef.current?.style.setProperty('--co', '0');
  }, []);

  /* section observers */
  const [statsRef,    statsVisible]    = useInView(0.2);
  const [workflowRef, workflowVisible] = useInView(0.1);
  const [featRef,     featVisible]     = useInView(0.1);
  const [demoRef,     demoVisible]     = useInView(0.2);
  const [ctaRef,      ctaVisible]      = useInView(0.2);

  return (
    <div className="ld-page" ref={pageRef}>

      {/* ── GLOBAL AMBIENT ORBS ── */}
      <div className="ld-orb ld-orb-1" />
      <div className="ld-orb ld-orb-2" />
      <div className="ld-orb ld-orb-3" />
      <div className="ld-orb ld-orb-4" />

      <div className="ld-content">

        {/* ══════════════════════════ HERO ══════════════════════════ */}
        <section
          className="ld-hero"
          ref={heroRef}
          onMouseMove={handleHeroMove}
          onMouseLeave={handleHeroLeave}
        >
          {/* glass panel itself */}
          <div className="ld-hero-glass" />
          {/* inner radial glows */}
          <div className="ld-hero-glow-top" />
          <div className="ld-hero-glow-bot" />
          {/* cursor spotlight */}
          <div className="ld-hero-cursor" />

          <span className="ld-badge">
            <span className="ld-badge-dot" />
            Now in Public Beta
          </span>

          <h1 className="ld-hero-title">
            Ship bug fixes<br />
            <span className="ld-hero-accent">while you sleep</span>
          </h1>

          <p className="ld-hero-desc">
            404PR is an AI agent that detects bugs, writes patches, validates them inside Docker sandboxes, and opens pull requests — autonomously.
          </p>

          <div className="ld-hero-actions">
            <button className="ld-btn-primary" onClick={() => navigate('/signup')}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
              Start Free Trial
            </button>
            <button className="ld-btn-ghost" onClick={() => { document.getElementById('workflow')?.scrollIntoView({ behavior: 'smooth' }); }}>
              See How It Works
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
            </button>
          </div>

          <p className="ld-hero-note">No credit card required · Works with any Python repo</p>

          {/* floating code fragment decorations */}
          <div className="ld-hero-deco ld-deco-1">
            <span className="ld-deco-text">pytest ✓ 3 passed</span>
          </div>
          <div className="ld-hero-deco ld-deco-2">
            <span className="ld-deco-dot" />
            <span className="ld-deco-text">PR #73 opened</span>
          </div>
          <div className="ld-hero-deco ld-deco-3">
            <span className="ld-deco-text">fix generated · 14.5s</span>
          </div>
        </section>

        {/* ══════════════════════════ STATS ══════════════════════════ */}
        <div ref={statsRef} className={`ld-stats ${statsVisible ? 'ld-in' : ''}`}>
          {STATS.map((s, i) => (
            <div key={s.label} className="ld-stat-card" style={{ '--i': i }}>
              <span className="ld-stat-value" style={{ color: s.color }}>
                <Counter target={s.value} trigger={statsVisible} />
              </span>
              <span className="ld-stat-label">{s.label}</span>
              <div className="ld-stat-bar" style={{ background: s.color }} />
            </div>
          ))}
        </div>

        {/* ══════════════════════════ WORKFLOW ══════════════════════════ */}
        <section id="workflow" ref={workflowRef} className={`ld-section ${workflowVisible ? 'ld-in' : ''}`}>
          <div className="ld-section-header">
            <span className="ld-eyebrow">How It Works</span>
            <h2 className="ld-section-title">Six steps. Zero intervention.</h2>
            <p className="ld-section-desc">
              From issue detection to merged pull request — the entire lifecycle runs inside an isolated pipeline you can observe in real-time.
            </p>
          </div>

          <div className="ld-workflow-grid">
            {WORKFLOW_STEPS.map((step, i) => (
              <div key={step.n} className="ld-step-card" style={{ '--i': i }}>
                <div className="ld-step-card-glow" style={{ background: `radial-gradient(circle at 0% 0%, ${step.bg.replace('0.08','0.35')} 0%, transparent 70%)` }} />
                <span className="ld-step-num">Step {step.n}</span>
                <div className="ld-step-icon" style={{ background: step.bg, border: `1px solid ${step.border}`, color: step.color }}>
                  {step.icon}
                </div>
                <h4 className="ld-step-title">{step.title}</h4>
                <p className="ld-step-desc">{step.desc}</p>
                <div className="ld-step-line" style={{ background: step.color }} />
              </div>
            ))}
          </div>
        </section>

        {/* ══════════════════════════ FEATURES ══════════════════════════ */}
        <section id="features" ref={featRef} className={`ld-section ${featVisible ? 'ld-in' : ''}`}>
          <div className="ld-section-header">
            <span className="ld-eyebrow">Core Engine</span>
            <h2 className="ld-section-title">Built for real codebases</h2>
            <p className="ld-section-desc">
              Not a toy demo — 404PR handles production Python repositories with complex dependency graphs and flaky test suites.
            </p>
          </div>

          <div className="ld-feat-grid">
            {/* Feature 1 */}
            <div className="ld-feat-card" style={{ '--i': 0 }}>
              <div className="ld-feat-glow" style={{ background: 'radial-gradient(circle at 10% 20%, rgba(0,136,255,0.18) 0%, transparent 65%)' }} />
              <div className="ld-feat-icon" style={{ background: 'rgba(0,136,255,0.1)', border: '1px solid rgba(0,136,255,0.22)', color: 'var(--color-electric-signal)' }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="22" y1="12" x2="18" y2="12"/><line x1="6" y1="12" x2="2" y2="12"/><line x1="12" y1="6" x2="12" y2="2"/><line x1="12" y1="22" x2="12" y2="18"/></svg>
              </div>
              <h3 className="ld-feat-title">AST-Level Diagnosis</h3>
              <p className="ld-feat-desc">Parses abstract syntax trees, traces variable flow across modules, and pinpoints the exact line where logic diverges from expected behavior.</p>
              <span className="ld-feat-detail">python -m ast → trace → diff</span>
            </div>

            {/* Feature 2 */}
            <div className="ld-feat-card" style={{ '--i': 1 }}>
              <div className="ld-feat-glow" style={{ background: 'radial-gradient(circle at 10% 20%, rgba(39,201,63,0.15) 0%, transparent 65%)' }} />
              <div className="ld-feat-icon" style={{ background: 'rgba(39,201,63,0.1)', border: '1px solid rgba(39,201,63,0.22)', color: 'var(--color-vivid-mint)' }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="2" width="20" height="20" rx="2.18"/><line x1="7" y1="2" x2="7" y2="22"/><line x1="17" y1="2" x2="17" y2="22"/><line x1="2" y1="12" x2="22" y2="12"/></svg>
              </div>
              <h3 className="ld-feat-title">Docker Sandbox</h3>
              <p className="ld-feat-desc">Every test run happens inside a fresh container. No state leakage, no host contamination. Reproducible from clone to commit.</p>
              <span className="ld-feat-detail">python:3.10-alpine · pytest · 1.4s avg</span>
            </div>

            {/* Feature 3 */}
            <div className="ld-feat-card" style={{ '--i': 2 }}>
              <div className="ld-feat-glow" style={{ background: 'radial-gradient(circle at 10% 20%, rgba(184,85,231,0.15) 0%, transparent 65%)' }} />
              <div className="ld-feat-icon" style={{ background: 'rgba(184,85,231,0.1)', border: '1px solid rgba(184,85,231,0.22)', color: 'var(--color-lavender-mist)' }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 15V9a4 4 0 0 0-4-4H9"/><line x1="6" y1="9" x2="6" y2="15"/></svg>
              </div>
              <h3 className="ld-feat-title">Smart PR Generation</h3>
              <p className="ld-feat-desc">Auto-generates commit messages, branch names, and rich PR descriptions explaining the root cause, the fix, and the test evidence.</p>
              <span className="ld-feat-detail">git push → gh pr create → review</span>
            </div>
          </div>
        </section>

        {/* ══════════════════════════ VISUAL DEMO ══════════════════════════ */}
        <section ref={demoRef} className={`ld-demo-section ${demoVisible ? 'ld-in' : ''}`}>
          <div className="ld-demo-glow" />

          <div className="ld-demo-content">
            <span className="ld-eyebrow">Live Resolution</span>
            <h3 className="ld-feat-title" style={{ fontSize: '26px', letterSpacing: '-0.7px' }}>Watch the agent reason</h3>
            <p className="ld-feat-desc">
              The scanner identifies the broken line, generates a candidate patch with proper expiration checks, and validates the fix — all in under 15 seconds.
            </p>
            <button className="ld-btn-primary" style={{ marginTop: '8px', width: 'fit-content' }} onClick={() => navigate('/login')}>
              Launch Dashboard
            </button>
          </div>

          <div className="ld-demo-window">
            <div className="ld-demo-titlebar">
              <span className="ld-dot ld-dot-r" />
              <span className="ld-dot ld-dot-y" />
              <span className="ld-dot ld-dot-g" />
              <span className="ld-demo-filename">validate_token.py</span>
            </div>
            <div className="ld-demo-body">
              <div className="ld-scanner" />
              <div className="ld-code">
                <div className="ld-line"><span className="ld-ln">1</span><span className="ld-kw">def</span> <span className="ld-fn">validate_token</span><span className="ld-muted">(token: str) → bool:</span></div>
                <div className="ld-line"><span className="ld-ln">2</span><span className="ld-muted">    payload = decode_jwt(token)</span></div>
                <div className="ld-line ld-line-del"><span className="ld-ln">3</span>    return payload.get("user") is not None</div>
                <div className="ld-line ld-line-add"><span className="ld-ln">4</span>    if payload.get("exp") and payload["exp"] &lt; time.time():</div>
                <div className="ld-line ld-line-add"><span className="ld-ln">5</span>        return False</div>
                <div className="ld-line"><span className="ld-ln">6</span><span className="ld-muted">    return payload.get("user") is not None</span></div>
              </div>
            </div>
            {/* status pill below code */}
            <div className="ld-demo-footer">
              <span className="ld-demo-status">
                <span className="ld-demo-status-dot" />
                Patch validated · 3/3 tests passed
              </span>
              <span className="ld-demo-time">14.5s</span>
            </div>
          </div>
        </section>

        {/* ══════════════════════════ CTA ══════════════════════════ */}
        <section ref={ctaRef} className={`ld-cta ${ctaVisible ? 'ld-in' : ''}`}>
          <div className="ld-cta-orb-1" />
          <div className="ld-cta-orb-2" />
          <div className="ld-cta-glass" />
          <span className="ld-badge" style={{ position: 'relative', zIndex: 1 }}>
            <span className="ld-badge-dot" style={{ background: 'var(--color-lavender-mist)', boxShadow: '0 0 6px var(--color-lavender-mist)' }} />
            Free to Start
          </span>
          <h2 className="ld-cta-title">Ready to automate your bug fixes?</h2>
          <p className="ld-cta-desc">Connect your GitHub repository and let 404PR handle the rest. From issue to merged PR in minutes.</p>
          <div className="ld-cta-actions">
            <button className="ld-btn-primary ld-btn-lg" onClick={() => navigate('/signup')}>
              Create Free Account
            </button>
            <button className="ld-btn-ghost" onClick={() => navigate('/login')}>
              Sign In
            </button>
          </div>
        </section>

        {/* ══════════════════════════ FOOTER ══════════════════════════ */}
        <footer className="ld-footer">
          <span className="ld-footer-brand">© 2026 404PR — Ansh Pandey</span>
          <div className="ld-footer-links">
            <a href="https://github.com/AnshPandey18/4o4PR" target="_blank" rel="noopener noreferrer" className="ld-footer-link">GitHub</a>
            <a href="#docs" onClick={(e) => e.preventDefault()} className="ld-footer-link">Documentation</a>
            <a href="#privacy" onClick={(e) => e.preventDefault()} className="ld-footer-link">Privacy</a>
            <a href="#terms" onClick={(e) => e.preventDefault()} className="ld-footer-link">Terms</a>
          </div>
        </footer>

      </div>
    </div>
  );
}
