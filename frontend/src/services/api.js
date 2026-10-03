/**
 * 4o4PR API service — connects frontend to FastAPI backend.
 * In dev: Vite proxies /api → http://localhost:8000
 * In prod: set VITE_API_URL to your server.
 */

const BASE = import.meta.env.VITE_API_URL || '';

// ── helpers ───────────────────────────────────────────────────────────────
async function _json(res) {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

// ── runs ──────────────────────────────────────────────────────────────────

/** Start any run (demo_mode:true triggers the real CLI pipeline on fixtures) */
export async function startRun({ repo, bug, branch = 'main', repo_path, demo_mode = false }) {
  return _json(await fetch(`${BASE}/api/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo, bug, branch, repo_path, demo_mode }),
  }));
}

/** Convenience: start the demo pipeline (fixtures/sample_bugs) in one call */
export function startDemoRun() {
  return startRun({
    repo: 'demo/sample_bugs',
    bug: 'Demo: sample_bugs fixture (calculator + string_utils)',
    branch: 'main',
    demo_mode: true,
  });
}

export async function getRun(runId) {
  return _json(await fetch(`${BASE}/api/runs/${runId}`));
}

export async function listRuns() {
  return _json(await fetch(`${BASE}/api/runs`));
}

export async function deleteRun(runId) {
  return _json(await fetch(`${BASE}/api/runs/${runId}`, { method: 'DELETE' }));
}

/** Full bug_report.json + bug_groups.json for a specific run (demo only). */
export async function getRunReport(runId) {
  return _json(await fetch(`${BASE}/api/runs/${runId}/report`));
}

/**
 * Fetch the most-recent pipeline output from backend/runs/ — used by the
 * Report page to show real data even without a live in-memory run.
 */
export async function getLatestDemoReport() {
  return _json(await fetch(`${BASE}/api/demo/latest-report`));
}

/** Returns an EventSource for SSE streaming of run logs. */
export function streamRun(runId) {
  return new EventSource(`${BASE}/api/runs/${runId}/stream`);
}

export async function healthCheck() {
  try {
    return await _json(await fetch(`${BASE}/api/health`));
  } catch {
    return null;
  }
}
