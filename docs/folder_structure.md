# Project Folder Structure — Automated Bug Fixing Agent

This document explains the full repository layout: every folder, subfolder, and file, and what it's responsible for. The project has two main parts — `backend/` (Python, the pipeline/agent logic) and `web/` (React + Node, the dashboard) — kept fully separate so each can be developed, tested, and understood independently.

---

## Top-Level Layout

```
automated-bug-fixing-agent/
├── README.md
├── .gitignore
├── .env.example
├── docker-compose.yml
├── backend/
├── web/
├── docs/
└── scripts/
```

| Item | Purpose |
|---|---|
| `README.md` | Project overview, setup instructions, how to run everything locally |
| `.gitignore` | Excludes generated files (node_modules, __pycache__, .env, build artifacts) from version control |
| `.env.example` | Template showing which environment variables are needed (API keys, etc.) without exposing real secrets |
| `docker-compose.yml` | Spins up backend, frontend, and sandbox services together for local development |
| `backend/` | All Python code — the core pipeline, agents, API server, evaluation |
| `web/` | All React + Node code — the dashboard frontend |
| `docs/` | Architecture notes, evaluation write-ups, images for the final report |
| `scripts/` | Small convenience scripts for setup and running tasks |

---

## `backend/` — Python Pipeline & API

```
backend/
├── requirements.txt
├── pyproject.toml
├── .env.example
├── app/
├── evaluation/
├── sandbox/
├── examples/
└── tests/
```

| Item | Purpose |
|---|---|
| `requirements.txt` | List of Python dependencies (anthropic, fastapi, pytest, pygithub, docker, etc.) |
| `pyproject.toml` | Project metadata and tool configuration (formatting, linting settings) |
| `.env.example` | Backend-specific environment variable template (ANTHROPIC_API_KEY, GITHUB_TOKEN, etc.) |
| `app/` | The actual application source code |
| `evaluation/` | SWE-bench evaluation harness and results |
| `sandbox/` | Docker setup for isolated, safe code execution |
| `examples/` | Hand-crafted toy repos with intentional bugs, used during development |
| `tests/` | Tests for your own pipeline code (not the bugs you're fixing — tests *of* your system) |

### `backend/app/` — Core Application

```
app/
├── __init__.py
├── main.py
├── config.py
├── pipeline/
├── agents/
├── tools/
├── models/
├── api/
└── utils/
```

| File/Folder | Purpose |
|---|---|
| `main.py` | FastAPI application entry point — starts the server, registers routes |
| `config.py` | Centralized settings — loads environment variables, file paths, constants |
| `pipeline/` | The orchestration logic that ties all agent steps together |
| `agents/` | Each individual pipeline step, isolated into its own module |
| `tools/` | Reusable wrappers around external systems (Claude, Docker, GitHub, pytest) |
| `models/` | Data structures shared across the app (Pydantic models) |
| `api/` | HTTP endpoints exposed to the React frontend |
| `utils/` | Small shared helper code (e.g., logging setup) |

#### `app/pipeline/`

```
pipeline/
├── __init__.py
├── orchestrator.py
└── state.py
```

| File | Purpose |
|---|---|
| `orchestrator.py` | The main control loop: runs Bug Detector → Patch Generator → Test Validator → (retry if needed) → Explainer → GitHub PR creation, in sequence |
| `state.py` | Defines the shared "state" object that gets passed between steps and updated as the pipeline progresses (current bug, current patch, retry count, status) |

#### `app/agents/`

```
agents/
├── __init__.py
├── bug_detector.py
├── patch_generator.py
├── test_validator.py
└── explainer.py
```

| File | Purpose |
|---|---|
| `bug_detector.py` | Runs the test suite, parses failures into a structured bug report |
| `patch_generator.py` | Sends bug report + code to Claude, gets back root cause + suggested fix |
| `test_validator.py` | Applies the patch in a sandbox, runs tests, returns pass/fail result |
| `explainer.py` | Sends the final approved patch to Claude, gets back a PR description |

#### `app/tools/`

```
tools/
├── __init__.py
├── claude_client.py
├── pytest_runner.py
├── sandbox.py
├── github_client.py
└── diff_utils.py
```

| File | Purpose |
|---|---|
| `claude_client.py` | Wraps the Anthropic SDK — handles API key setup, sending prompts, parsing responses, so agents don't repeat this logic |
| `pytest_runner.py` | Wraps `subprocess` calls to pytest, handles structured JSON report output |
| `sandbox.py` | Manages Docker containers — building images, running code inside them, cleanup |
| `github_client.py` | Wraps PyGithub — creating branches, committing files, opening pull requests |
| `diff_utils.py` | Helpers for generating, parsing, and applying unified diffs/patches |

#### `app/models/`

```
models/
├── __init__.py
└── schemas.py
```

| File | Purpose |
|---|---|
| `schemas.py` | Pydantic models defining the shape of data used throughout the app — e.g., `BugReport`, `Patch`, `ValidationResult`, `PipelineStatus` |

#### `app/api/`

```
api/
├── __init__.py
├── routes.py
└── dependencies.py
```

| File | Purpose |
|---|---|
| `routes.py` | FastAPI endpoint definitions — e.g., trigger a pipeline run, fetch current status, fetch history, used by the React dashboard |
| `dependencies.py` | Shared FastAPI dependencies (e.g., loading config, shared client instances) injected into routes |

#### `app/utils/`

```
utils/
├── __init__.py
└── logger.py
```

| File | Purpose |
|---|---|
| `logger.py` | Centralized logging configuration so all modules log consistently |

---

### `backend/evaluation/`

```
evaluation/
├── __init__.py
├── swe_bench_runner.py
├── metrics.py
└── results/
```

| File/Folder | Purpose |
|---|---|
| `swe_bench_runner.py` | Script that runs the full pipeline against SWE-bench Lite issues and records outcomes |
| `metrics.py` | Calculates evaluation metrics — % resolved, average retries, average time per issue |
| `results/` | Stores output logs/JSON from evaluation runs (excluded from git via `.gitignore`) |

---

### `backend/sandbox/`

```
sandbox/
├── Dockerfile.python
└── requirements-sandbox.txt
```

| File | Purpose |
|---|---|
| `Dockerfile.python` | Defines the isolated container image used to safely run and test LLM-generated patches |
| `requirements-sandbox.txt` | Python dependencies installed inside the sandbox container (kept separate from the main backend's dependencies) |

---

### `backend/examples/`

```
examples/
├── toy_repo_1/
│   ├── src/
│   └── tests/
└── toy_repo_2/
    ├── src/
    └── tests/
```

| Folder | Purpose |
|---|---|
| `toy_repo_1/`, `toy_repo_2/` | Small, hand-written Python repos with intentionally introduced bugs, used during early development (Months 1–3) before moving to real SWE-bench issues |
| `src/` (within each) | The actual buggy source code |
| `tests/` (within each) | The pytest test suite that exposes the bugs |

---

### `backend/tests/`

```
tests/
├── __init__.py
├── test_bug_detector.py
├── test_patch_generator.py
└── test_pipeline.py
```

| File | Purpose |
|---|---|
| `test_bug_detector.py` | Unit tests verifying the Bug Detector correctly parses test failures |
| `test_patch_generator.py` | Unit tests verifying the Patch Generator correctly calls Claude and parses responses |
| `test_pipeline.py` | Integration tests verifying the full orchestrated pipeline behaves correctly end-to-end |

*Note: this folder tests your own system's code — it is separate from the bugs your system is designed to fix.*

---

## `web/` — React + Node Dashboard

```
web/
├── package.json
├── package-lock.json
├── .env.example
├── vite.config.js
├── public/
└── src/
```

| Item | Purpose |
|---|---|
| `package.json` | Node project manifest — lists dependencies and npm scripts (start, build, etc.) |
| `package-lock.json` | Locks exact dependency versions for reproducible installs |
| `.env.example` | Frontend environment variable template (e.g., backend API URL) |
| `vite.config.js` | Build tool configuration (assumes Vite; adjust if using a different bundler) |
| `public/` | Static assets served as-is |
| `src/` | All React source code |

### `web/public/`

```
public/
└── index.html
```

| File | Purpose |
|---|---|
| `index.html` | The base HTML page that the React app mounts into |

### `web/src/`

```
src/
├── main.jsx
├── App.jsx
├── components/
├── pages/
├── api/
├── hooks/
└── styles/
```

| File/Folder | Purpose |
|---|---|
| `main.jsx` | React entry point — renders `App.jsx` into the DOM |
| `App.jsx` | Root component — sets up routing between pages |
| `components/` | Reusable UI building blocks |
| `pages/` | Full page views, composed from components |
| `api/` | Functions for communicating with the FastAPI backend |
| `hooks/` | Custom React hooks for shared stateful logic |
| `styles/` | CSS/styling files |

#### `web/src/components/`

```
components/
├── DiffViewer.jsx
├── AgentTimeline.jsx
├── BugReportCard.jsx
├── PRPreview.jsx
└── RetryTracker.jsx
```

| File | Purpose |
|---|---|
| `DiffViewer.jsx` | Displays a side-by-side or unified view of the original vs. patched code |
| `AgentTimeline.jsx` | Shows live progress through pipeline steps (which agent is currently active) |
| `BugReportCard.jsx` | Displays details of a detected bug (file, error, traceback) |
| `PRPreview.jsx` | Shows a preview of the generated Pull Request before/after it's opened |
| `RetryTracker.jsx` | Visualizes how many retry attempts were needed for a given fix |

#### `web/src/pages/`

```
pages/
├── Dashboard.jsx
├── History.jsx
└── EvaluationResults.jsx
```

| File | Purpose |
|---|---|
| `Dashboard.jsx` | Main live view — shows an active pipeline run in real time |
| `History.jsx` | Table/list of past runs and their outcomes |
| `EvaluationResults.jsx` | Displays SWE-bench evaluation metrics and results |

#### `web/src/api/`

```
api/
└── client.js
```

| File | Purpose |
|---|---|
| `client.js` | Centralized functions for making requests to the FastAPI backend (fetch pipeline status, trigger a run, fetch history) |

#### `web/src/hooks/`

```
hooks/
└── usePipelineStatus.js
```

| File | Purpose |
|---|---|
| `usePipelineStatus.js` | Custom hook for polling/subscribing to live pipeline status updates from the backend |

#### `web/src/styles/`

```
styles/
└── index.css
```

| File | Purpose |
|---|---|
| `index.css` | Global stylesheet |

---

## `docs/`

```
docs/
├── architecture.md
├── evaluation-methodology.md
└── images/
```

| File/Folder | Purpose |
|---|---|
| `architecture.md` | Written explanation of system design and component interaction, for the final report |
| `evaluation-methodology.md` | Detailed write-up of how SWE-bench evaluation was conducted and metrics calculated |
| `images/` | Diagrams, screenshots, charts used in documentation/report |

---

## `scripts/`

```
scripts/
├── setup_dev_env.sh
└── run_local_eval.sh
```

| File | Purpose |
|---|---|
| `setup_dev_env.sh` | One-command setup for a new team member (installs backend + frontend dependencies, sets up env files) |
| `run_local_eval.sh` | Convenience script to kick off a local SWE-bench evaluation run |

---

## Why It's Organized This Way

- **`backend/app/agents/` mirrors the pipeline steps** — anyone opening the repo immediately sees the architecture (Bug Detector, Patch Generator, Test Validator, Explainer) reflected directly in folder names.
- **`backend/app/tools/` separates external integrations from agent logic** — agents call tools; tools have no knowledge of agents. This keeps each piece independently testable.
- **`backend/examples/` vs `backend/evaluation/`** keeps hand-crafted development repos clearly separate from real SWE-bench benchmark runs — no ambiguity about what's a toy and what's a real result.
- **`web/` is fully self-contained** and only communicates with the backend through `web/src/api/client.js` — no Python and JavaScript code are ever mixed in the same folder.
- **`docs/` exists from day one** so the final report can be built incrementally across the 6 months instead of written entirely at the end.
