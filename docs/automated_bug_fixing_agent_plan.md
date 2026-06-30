# Automated Bug Fixing Agent — Final Project Plan
### Final Year Capstone Project (6 Months, 3-Person Team)

---

## 1. Project Overview

The Automated Bug Fixing Agent is a system that takes buggy Python code (or a real GitHub issue), automatically diagnoses the bug, generates a fix, validates that fix by running tests in an isolated Docker sandbox, retries with self-correction if the fix fails, and opens a GitHub Pull Request with an auto-generated explanation — all without human intervention until final PR review.

This is a deliberately **scoped-down** version of a more ambitious original concept. The original spec included a 6-agent LangGraph pipeline, RAG (Retrieval-Augmented Generation) via ChromaDB, and multi-language (Python + JavaScript) support. After honest assessment of team size, timeline, and learning curve, these were cut to maximize the chance of shipping a fully working, well-evaluated, defensible system rather than an ambitious but broken one.

**Guiding principle:** a scoped, working, evaluated project beats an ambitious incomplete one — both for the final submission and for resume/interview purposes.

---

## 2. Goals

- Build a fully automated, end-to-end pipeline: bug in → verified fix + GitHub PR out.
- Demonstrate genuine agentic AI behavior: an LLM-driven loop that observes results, decides next actions, and self-corrects across retries.
- Produce a real, credible evaluation result using SWE-bench Lite (not a toy/self-reported metric).
- Ship a working live demo with a dashboard, not just slides.
- Be honestly explainable: every design decision (including what was cut) should have a clear, defensible reasoning.

---

## 3. Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Backend / Pipeline** | Python | Core orchestration logic, LLM calls, retry loop |
| **LLM** | Claude API | Bug analysis, patch generation, explanation generation |
| **Static Analysis** | pylint, `ast` | Basic bug/style detection in Python |
| **Testing** | pytest | Running test suites, detecting pass/fail, capturing errors |
| **Sandboxing** | Docker | Isolated, safe execution of LLM-generated code |
| **Version Control Integration** | GitHub REST API + PyGithub | Branch creation, committing patches, opening PRs |
| **Backend API Server** | FastAPI (Python) | Serves pipeline status/data to the frontend |
| **Frontend** | React (with Node.js tooling) | Dashboard: live agent progress, diff viewer, results |
| **Evaluation** | SWE-bench Lite | Standardized benchmark for measuring real-world fix accuracy |
| **Target Codebases** | Python repos (Django, Flask, NumPy, etc. via SWE-bench) | Consistent language across dev and evaluation phases |

### Explicitly Cut From v1 (and why)
- **RAG / ChromaDB** — unnecessary at the scale of codebases being tested (code fits directly in context); adds retrieval-tuning risk without proven benefit at this scope. Documented as future work.
- **LangGraph** — the orchestration framework is a wrapper around state + retry loops; the team is implementing this pattern directly in Python to fully understand the control flow, with LangGraph as a possible later refactor.
- **JavaScript/multi-language support** — kept to Python only, to stay consistent with SWE-bench (the credible, recognized evaluation benchmark) and avoid splitting the team's limited time across two language toolchains.

---

## 4. Team Roles

### Person A — LLM Logic & Pipeline Core
Owns the "thinking" part of the system.
- Designs prompts for bug analysis, patch generation, and explanation generation.
- Builds the core orchestration loop (detect → analyze/fix → validate → retry → explain).
- Implements the self-correction retry logic (feeding failure context back into the next LLM call).
- Tunes prompts based on evaluation failure analysis in later months.

### Person B — Infrastructure & Integration
Owns the "doing" part of the system — everything that executes or talks to external systems.
- Builds the Docker sandbox (isolated environment for safely running LLM-generated patches).
- Implements test running and output parsing (pytest integration).
- Implements GitHub API integration (branch creation, committing patches, opening PRs).
- Sets up SWE-bench Lite environments using their provided Docker images.

### Person C — Frontend & Evaluation
Owns visibility and proof of results.
- Builds the React dashboard (live pipeline status, diff viewer, bug/fix history, retry tracker).
- Builds and runs the SWE-bench Lite evaluation harness.
- Analyzes evaluation results and failure patterns.
- Leads the results write-up and metrics reporting.

*Note: roles define ownership, not isolation — all three should understand the full pipeline well enough to discuss it in an interview.*

---

## 5. Pipeline — Detailed Explanation

The pipeline is a fixed sequence of steps applied to each bug. Some steps are plain code (no AI); others involve a call to Claude.

### Step 1 — Bug Detection (no LLM)
The existing test suite for the target repo is run via `pytest`. Failing tests are captured along with their error messages and stack traces. This produces a structured bug report: which file, which test, what error, what stack trace. If no tests fail, the pipeline exits — there's nothing to fix.

### Step 2 — Root Cause Analysis + Patch Generation (LLM call)
The bug report, along with the relevant code (the failing function and its immediate context), is sent to Claude in a single prompt. Claude is asked to (a) explain the root cause of the failure and (b) generate a fix as a code diff or full corrected function. This step intentionally merges what could be two separate "agents" into one well-structured prompt, since splitting them added complexity without a clear benefit at this project's scale.

### Step 3 — Patch Application (no LLM)
Claude's suggested fix is applied to a temporary copy of the codebase — the original, unmodified code is never touched directly.

### Step 4 — Validation in Sandbox (no LLM)
The patched copy is run inside a Docker container, isolated from the host machine. The full test suite (including the previously failing test) is executed.
- If all relevant tests now pass → proceed to Step 5.
- If tests still fail → the new failure details are sent back to Step 2, and Claude is asked to revise its fix with this new information. This retry loop runs a maximum of 3 times. If all 3 attempts fail, the bug is escalated/logged as unresolved rather than looping forever.

### Step 5 — Explanation Generation (LLM call)
Once a patch passes validation, Claude is given the root cause analysis and the final patch, and asked to write a clear, human-readable summary: what was broken, why, what was changed, and any caveats. This becomes the Pull Request description.

### Step 6 — GitHub PR Creation (no LLM)
A new branch is created, the validated patch is committed, and a Pull Request is opened via the GitHub API, including the auto-generated description and a summary of test results. A human developer retains final approval — the system never auto-merges.

### Step 7 — Dashboard Visibility (no LLM)
Throughout all of the above, the React dashboard displays live status: which step is active, the diff being proposed, test pass/fail results, and how many retries were needed. This is what makes the system demoable rather than a black box.

**Why this counts as agentic AI:** the system doesn't just respond once to a prompt — it observes the result of its own actions (test pass/fail), and autonomously decides the next action (proceed, or retry with new context) without human input between steps. This perceive → act → observe → adapt loop, repeated up to 3 times per bug, is the core defining behavior of an agentic system, even though it's implemented as a fixed-sequence pipeline rather than a fully open-ended planning agent.

---

## 6. Evaluation Methodology

Evaluation uses **SWE-bench Lite**, a curated subset (~300 issues) of real, historical GitHub bug-fix pull requests from popular Python open-source projects.

For each evaluation issue, SWE-bench provides:
- The repository state *before* the fix (a specific commit, bug present)
- The natural-language issue description
- **FAIL_TO_PASS tests** — tests that failed before the fix and should pass after it (proves the bug was actually fixed)
- **PASS_TO_PASS tests** — tests that passed before and must still pass after (proves nothing else broke)
- A pre-built Docker image with the correct environment/dependencies for that specific commit

**Evaluation process per issue:**
1. Feed the "before" repo state + issue description into the pipeline.
2. Pipeline produces a patch.
3. Apply the patch to a fresh copy of the "before" state.
4. Run FAIL_TO_PASS tests — must now pass.
5. Run PASS_TO_PASS tests — must still pass.
6. If both conditions hold, the issue is marked **RESOLVED**.

**Metrics reported:**
- **% resolved** (resolved issues ÷ total issues attempted)
- **Average retries per issue**
- **Average time per issue**
- **Failure category breakdown** for unresolved issues (e.g., patch didn't apply, tests still failed after 3 retries, environment/timeout error)

**Target scope:** run on roughly 20–30 sampled issues (not the full 300) given API cost and time constraints — a modest, honestly-reported resolution rate (even 10–20%) is a legitimate, credible result, especially when paired with clear failure analysis.

---

## 7. Basic Schedule

| Month | Focus | Milestone |
|---|---|---|
| **1** | Learn Claude API basics; pick/build 2–3 small Python repos with bugs + tests; manually run the core loop once | Core idea proven manually on hand-picked bugs |
| **2** | Automate patch application; build Docker sandbox; implement retry loop; start dashboard skeleton | Fully automated pipeline works end-to-end on hand-picked bugs |
| **3** | GitHub PR integration; explanation generation; connect dashboard to live data; test on real small repos | Live demo: trigger on a real repo, watch dashboard, get a real PR |
| **4** | Set up SWE-bench Lite + provided Docker images; adapt pipeline to SWE-bench format; run on 5–10 issues to debug the pipeline itself | Pipeline runs on SWE-bench format without crashing |
| **5** | Run evaluation on 20–30 SWE-bench Lite issues; analyze failures; tune prompts; re-run for final numbers | Final evaluation numbers obtained |
| **6** | Polish dashboard; record demo video; write report; prepare presentation | Submission-ready |

---

## 8. Future Implementation (Post-Submission / Stretch Goals)

These are explicitly out of scope for the 6-month core build but are valid, expected "future work" items to mention in the report or pursue afterward if time allows:

- RAG (ChromaDB or similar) for handling larger codebases that don't fit in context.
- LangGraph (or similar agent framework) refactor for more formalized state management at scale.
- Multi-language support (JavaScript/TypeScript via ESLint + Jest).
- GitHub webhook-based automation (auto-trigger on new issues/PRs, rather than manual trigger).
- Expanded SWE-bench evaluation (full Lite set, or the larger SWE-bench Verified/full set).
- Confidence scoring or multiple candidate patches per bug, with automated selection.
- Security-focused code review as a distinct LLM-reviewed step.

---

## 9. Topics to Learn

### Basic
- Python scripting fundamentals
- Making API calls (requests library, REST basics)
- pytest fundamentals (writing/running tests, reading output)
- Git basics (branching, committing, diffs)
- GitHub fundamentals (PRs, issues)
- React fundamentals (components, state, props)
- Node.js/npm basics
- JSON handling

### Intermediate
- Claude API usage (prompt construction, multi-turn context, parsing structured responses)
- Prompt engineering for code-related tasks (chain-of-thought prompting, structured output)
- Docker fundamentals (images, containers, Dockerfiles, docker-compose)
- FastAPI (routes, request/response models, serving a backend API)
- PyGithub / GitHub REST API (branch creation, commits, PR creation)
- pylint / static analysis tooling
- Diff/patch generation and application (unified diff format)
- Subprocess management in Python (running external commands, capturing output)
- State management in React (for live-updating dashboard data)

### Advanced
- Designing and implementing retry/self-correction loops (feedback-driven LLM iteration)
- SWE-bench dataset structure and evaluation harness usage
- Working with pre-built Docker images mapped to specific commit/dependency states
- Failure analysis and categorization methodology
- Prompt tuning based on systematic evaluation feedback
- Agentic system design principles (perceive–act–observe–adapt loops)
- (Stretch) Vector embeddings and RAG architecture
- (Stretch) LangGraph or similar agent orchestration frameworks
