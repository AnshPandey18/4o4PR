# 4o4PR PROJECT SYNOPSIS - CHUNK 1
## DRONACHARYA GROUP OF INSTITUTIONS, GREATER NOIDA

---

# FRONT MATTER & PROJECT SUBMISSION DETAILS

## COMPUTER SCIENCE & INFORMATION TECHNOLOGY
## A SYNOPSIS REPORT

**Submitted in partial fulfillment of the requirements for the award of the degree**

## BACHELOR OF TECHNOLOGY

### Title of the Project:
# 4o4PR: An LLM-Powered System for Autonomous Bug Detection, Patch Generation, and GitHub PR Creation

### For
**B.Tech Final Year Major Project**

---

## Dronacharya Group of Institutions, Greater Noida
**Academic Session: 2026–27**

#27, APJ Abdul Kalam Road, Knowledge Park-III, Greater Noida, Uttar Pradesh – 201306

---

## PROJECT SUBMISSION DETAILS

### B.Tech Final Year Major Project Synopsis

| **Project Title** | 4o4PR: An LLM-Powered System for Autonomous Bug Detection, Patch Generation, and GitHub PR Creation |
|---|---|
| **Programme** | B.Tech – Computer Science & Information Technology |
| **Student 1** | Smarth Gupta | **Roll No.:** 2302300110100/18372 | **Section:** CSIT-B |
| **Student 2** | Ansh Kumar Pandey | **Roll No.:** 2302300110019/18271 | **Section:** CSIT-A |
| **Student 3** | Anand Nath Thakur | **Roll No.:** 2302300110015/18267 | **Section:** CSIT-A |

| **Under the Supervision of** | [Supervisor Name] |
|---|---|
| **Designation** | [Assistant Professor / Associate Professor / Professor] |
| **Department** | Computer Science & Information Technology |
| **Institution** | Dronacharya Group of Institutions, Greater Noida |

### Institutional Address
#27, APJ Abdul Kalam Road, Knowledge Park-III, Greater Noida, Uttar Pradesh – 201306

---

## TABLE OF CONTENTS

| S. No. | Section | Page |
|---|---|---|
| 1. | Abstract | 4 |
| 2. | Introduction | 5 |
| 3. | Problem Statement, Objectives & Scope | 6 |
| 4. | Literature Survey | 7 |
| 5. | Research Gap & Proposed Solution | 8 |
| 6. | Proposed Methodology / System Design | 9 |
| 7. | Technology Stack & Requirements | 10 |
| 8. | Modules, Algorithms & Data Flow | 11 |
| 9. | Expected Results, Testing & Evaluation | 12 |
| 10. | Conclusion & Future Scope | 13 |
| 11. | References (IEEE Format) | 14 |

---

# 1. ABSTRACT

Software debugging consumes approximately 50% of developer time and costs the global economy over $300 billion annually. Manual bug fixing is error-prone, time-intensive, and requires iterative testing to ensure fixes don't introduce regressions. Existing automated debugging tools either detect bugs without fixing them (Pylint, Flake8) or require extensive manual intervention to validate proposed solutions.

This project presents **4o4PR (404 Pull Request)**, an end-to-end system that autonomously detects bugs in Python repositories, generates code patches using Large Language Models, validates fixes in isolated Docker sandboxes, self-corrects through iterative refinement, and creates GitHub Pull Requests with human-readable explanations—all without human intervention until final PR review. The system implements a fixed-sequence agentic pipeline: (1) Bug Detector runs pytest and parses failure reports to identify bugs with full code context, (2) Patch Generator uses Claude API to analyze root causes and generate fixes, (3) Test Validator applies patches in Docker sandboxes and executes test suites, (4) Retry Loop feeds validation failures back to the Patch Generator for self-correction (maximum 3 attempts), (5) Explainer generates PR descriptions explaining what was fixed and why, and (6) GitHub Integration creates branches, commits patches, and opens pull requests.

The system is evaluated using **SWE-bench Lite**, a standardized benchmark of 300+ real-world GitHub issues from popular Python projects (Django, Flask, NumPy). Target metrics include 10-20% issue resolution rate, average retry count, and processing time per issue. The modular architecture separates LLM logic (prompts, reasoning), infrastructure (Docker, GitHub API, pytest integration), and frontend (React dashboard for live pipeline visualization). The project demonstrates genuine agentic behavior through its observe-act-adapt loop where the system autonomously decides whether to proceed or retry based on test results.

Unlike ambitious but incomplete approaches, this project prioritizes a **scoped, working, evaluated system** over feature breadth. Multi-language support, LangGraph orchestration, and RAG-based code retrieval are explicitly deferred to future work to ensure delivery of a defensible, fully functional system suitable for academic evaluation and industry demonstration.

## Keywords

Automated bug fixing, Large language models, Agentic AI, Self-correction loop, Docker sandbox, GitHub automation, SWE-bench, pytest integration

---

# 2. INTRODUCTION

## 2.1 Background

Software quality assurance is a critical phase in the software development lifecycle, with debugging accounting for a substantial portion of development costs. According to industry studies, debugging and bug fixing consume approximately 50% of developer time and cost the global economy over $300 billion annually. The traditional bug-fixing workflow involves multiple manual steps: (1) identifying which tests fail, (2) analyzing error messages and stack traces, (3) locating buggy code, (4) understanding root causes, (5) implementing a fix, (6) running tests to validate, and (7) iterating if the fix fails—a process that can take hours or days for complex bugs.

Python, despite being one of the most popular programming languages for web development, data science, and automation, presents unique challenges due to its dynamic typing, runtime error detection, and flexible syntax. Existing tools address only fragments of this workflow: static analyzers like Pylint detect potential issues but don't fix them; GitHub Copilot suggests code but doesn't validate it against test suites; CI/CD systems run tests but don't generate patches when they fail.

Recent advances in Large Language Models (LLMs) such as GPT-4 and Claude have demonstrated remarkable capabilities in understanding code semantics, generating syntactically correct patches, and explaining technical concepts in natural language. However, directly applying LLMs to bug fixing presents challenges: hallucination (generating plausible but incorrect fixes), lack of validation (no guarantee the fix actually works), and context limitations (LLMs don't inherently know if tests pass or fail after applying their suggestions).

The emergence of **agentic AI**—systems that autonomously perceive their environment, take actions, observe results, and adapt their behavior—offers a path toward fully automated debugging. An agentic bug-fixing system would not only generate a candidate patch but also validate it by running tests, observe whether tests pass or fail, and retry with corrections if the initial fix was insufficient, mirroring how human developers debug iteratively.

## 2.2 Motivation

The motivation for 4o4PR stems from four key observations:

1. **Manual Validation Bottleneck**: Existing LLM-based code generation tools (GitHub Copilot, ChatGPT Code Interpreter) produce suggestions without validating them against actual test suites. Developers must manually verify every suggestion, defeating the purpose of automation.

2. **Lack of Self-Correction in Current Tools**: When a generated fix fails, existing tools don't observe the failure and retry—they simply output a patch and exit. Human developers naturally iterate on failed fixes by incorporating new error messages into their next attempt; automated tools should do the same.

3. **Gap Between Detection and Fixing**: Static analysis tools detect bugs but provide no patches. Conversely, LLM-based code generators produce patches but don't systematically detect bugs from test failures. No existing system bridges this gap in a single automated workflow.

4. **SWE-bench as a Credible Standard**: The release of SWE-bench (Software Engineering Benchmark) provides the first standardized, reproducible evaluation dataset for automated debugging systems, using real-world GitHub issues from popular Python projects. This enables honest comparison of different approaches rather than self-reported accuracy on toy examples.

From an academic and industry perspective, this project explores fundamental questions: Can an LLM-driven agent autonomously fix real bugs when given only test failures as input? How many retry attempts are needed on average? What failure patterns emerge, and how can they inform better prompting strategies? These questions have direct relevance to the future of software engineering automation.

## 2.3 Need for the Project

Current practices in automated debugging exhibit critical gaps:

**Gap 1: End-to-End Automation** – Developers must manually orchestrate detection → analysis → fixing → validation. No tool performs all steps autonomously from test failure to validated PR.

**Gap 2: Validation in Isolation** – Running LLM-generated code safely requires sandboxing (isolated environments where buggy or malicious code can't harm the host system). Most tools skip validation entirely or assume trusted environments.

**Gap 3: Self-Correction Capability** – When a fix fails validation, existing tools don't feed failure context back to the LLM for a second attempt. Human developers always analyze "why did my fix fail?" before trying again—automated systems should too.

**Gap 4: Standardized Evaluation** – Many academic papers report bug-fixing accuracy on private datasets or contrived examples, making results non-reproducible. The lack of a common benchmark prevents objective comparison of approaches.

**Gap 5: Human-Readable Explanations** – Even when a fix works, developers reviewing PRs need to understand *what* was changed and *why*. Auto-generated patches without explanations are difficult to trust and approve.

This project addresses these gaps by building a complete pipeline: pytest-based bug detection → Claude-powered patch generation → Docker-based validation → self-correction retry loop → explanation generation → GitHub PR creation, all evaluated on the standardized SWE-bench Lite dataset.

## 2.4 Project Overview

The **4o4PR (404 Pull Request)** is a Python-based system that implements a fixed-sequence agentic pipeline for autonomous bug fixing. The system consists of six core components:

**1. Bug Detector**: Executes pytest on target repositories, parses test failure output to extract error messages, stack traces, file paths, and line numbers, and reads source files to capture failing function code plus surrounding context. Output: structured `BugReport` objects with all information needed for patch generation.

**2. Patch Generator**: Sends bug reports and code context to Claude API with carefully crafted prompts requesting (a) root cause analysis and (b) a code fix as a unified diff or corrected function. Parses Claude's response into a structured `Patch` object.

**3. Test Validator**: Applies the generated patch to a temporary copy of the repository inside an isolated Docker container, runs the full test suite (including FAIL_TO_PASS tests that must now pass, and PASS_TO_PASS tests that must remain passing), and returns validation results (pass/fail, which tests failed, error messages).

**4. Retry Loop**: If validation fails, extracts failure details and sends them back to the Patch Generator along with the original bug report, asking Claude to revise its fix. Repeats up to 3 times. If all attempts fail, the bug is marked "unresolved" rather than looping indefinitely.

**5. Explainer**: Once a patch passes validation, sends the root cause analysis and final patch to Claude, requesting a clear, human-readable summary suitable for a Pull Request description (what was broken, why, what was changed, any caveats).

**6. GitHub Integration**: Creates a new branch from the repository's default branch, commits the validated patch, opens a Pull Request with the auto-generated description and test results summary, and links to the original issue. Leaves final merge decision to human reviewers.

**Dashboard**: A React-based web frontend displays live pipeline progress (which step is active, current diff, test results, retry count), historical runs, and evaluation metrics. The dashboard makes the system demoable and provides transparency into agent decision-making.

The system is **deliberately scoped** to maximize delivery success: Python-only (no multi-language support in v1), direct orchestration (no LangGraph wrapper), no RAG/vector databases (code fits in context at current scale), and Docker-based sandboxing (no cloud VM orchestration). All cut features are documented as future work with clear rationales.

**Target Users**: Open-source maintainers triaging issue backlogs, developers working on large legacy codebases with extensive test suites, academic researchers studying agentic AI systems, and companies exploring AI-assisted software development workflows.

## 2.5 Organization of the Synopsis

This synopsis is structured as follows:

- **Section 3** defines the precise problem statement, measurable objectives, and project scope (what's in v1, what's deferred)
- **Section 4** surveys relevant academic literature on LLM-based code generation, agentic AI, SWE-bench evaluations, and automated debugging
- **Section 5** identifies the research gap and compares existing systems with the proposed 4o4PR system
- **Section 6** details the six-stage pipeline architecture, methodology, and development workflow
- **Section 7** specifies the technology stack (Python, Claude API, Docker, FastAPI, React), hardware/software requirements, and feasibility analysis
- **Section 8** describes major system modules (Bug Detector, Patch Generator, Test Validator, Retry Loop, Explainer, GitHub Integration), key algorithms, and data flow
- **Section 9** outlines SWE-bench Lite evaluation methodology, target metrics (% resolved, average retries, processing time), and testing strategies
- **Section 10** concludes with project contributions, lessons learned, and future research directions (RAG, LangGraph, multi-language support)
- **Section 11** provides IEEE-formatted references

---

# 3. PROBLEM STATEMENT, OBJECTIVES & SCOPE

## 3.1 Problem Statement

Software developers fixing bugs follow an iterative workflow: run tests to identify failures, analyze error messages and stack traces, hypothesize root causes, implement a fix, re-run tests to validate, and repeat if tests still fail. This process is time-consuming (averaging 2-6 hours per non-trivial bug) and error-prone (studies show 20-30% of first-attempt fixes introduce new bugs or fail to resolve the original issue).

Existing approaches to automation fail to replicate this complete workflow:

1. **Static Analysis Tools (Pylint, Flake8, mypy)**: Detect potential issues through pattern matching but generate no fixes. Developers must still manually implement solutions and validate them.

2. **LLM-Based Code Generators (GitHub Copilot, ChatGPT)**: Suggest code fixes when prompted but lack systematic bug detection (developers must manually identify what's broken) and provide no validation (no guarantee suggested fixes actually work or don't break other functionality).

3. **Automated Repair Research Systems (e.g., academic prototypes)**: Often evaluated on synthetic benchmarks or private datasets, with no standardized way to compare approaches. Many lack self-correction capabilities—they generate one candidate fix and stop, regardless of whether it passes tests.

4. **CI/CD Test Runners**: Detect test failures automatically but provide no automated fixing—they only alert developers that something is broken.

The fundamental gap is the absence of a system that autonomously performs the complete bug-fixing loop: **detect failures** (via existing test suites) → **generate a patch** (using LLM reasoning about root causes) → **validate the patch** (by running tests in isolation) → **self-correct if validation fails** (retry with failure feedback) → **explain the solution** (for human PR reviewers) → **automate PR creation** (integrate fix back into the codebase)—all without human intervention except final PR approval.

**Problem Statement**: How can we design an autonomous agentic system that takes a Python repository with failing tests as input and produces a validated, tested, explained code patch as a GitHub Pull Request, with self-correction capabilities to handle initial fix failures, and evaluation against real-world bugs from standardized benchmarks like SWE-bench Lite?

The challenge is to balance LLM hallucination risks (plausible but incorrect fixes) with genuine problem-solving ability, ensure safe execution of generated code (sandboxing), and demonstrate measurable success on credible, reproducible test cases rather than cherry-picked examples.

## 3.2 Objectives

The primary objectives of the 4o4PR project are:

**Objective 1**: Design and implement a six-stage agentic pipeline that autonomously processes test failures through detection, patch generation, validation, retry with self-correction, explanation generation, and GitHub PR creation, with clear separation of concerns (LLM logic, infrastructure, frontend).

**Objective 2**: Develop a Bug Detector module that executes pytest on target repositories, parses failure output using regex and structured formats (pytest-json-report), extracts failing test metadata (name, error type, message, traceback), and uses Python's AST module to extract complete failing function code plus configurable context lines before/after the function—achieving ≥95% parsing accuracy on standard pytest output formats.

**Objective 3**: Implement a Patch Generator that constructs prompts combining bug context, error messages, and code snippets for Claude API, requests both root cause analysis and code fixes, parses LLM responses into structured patches (unified diff format), and handles edge cases (malformed responses, code without clear functions, incomplete diffs)—generating syntactically valid patches for ≥90% of well-formed bug reports.

**Objective 4**: Build a Test Validator using Docker containerization to safely execute LLM-generated patches in isolated environments, apply patches via `git apply` or direct file modification, run full pytest suites to check FAIL_TO_PASS tests (previously failing, now must pass) and PASS_TO_PASS tests (must remain passing), and return structured validation results—completing validation cycles in ≤30 seconds per attempt for typical repositories.

**Objective 5**: Create a self-correction Retry Loop that observes validation failures, extracts new error messages from failed test attempts, feeds this information back to the Patch Generator with explicit instructions to revise the previous fix, limits retries to 3 attempts to prevent infinite loops, and tracks retry statistics (attempt number, why each fix failed)—achieving resolution (eventual test pass) for ≥40% of bugs that fail on first attempt.

**Objective 6**: Evaluate the complete system on SWE-bench Lite (a standardized benchmark of 300+ real-world Python GitHub issues from popular projects like Django, Flask, NumPy) using their provided evaluation harness, report % resolved (issues where final patch passes all FAIL_TO_PASS and PASS_TO_PASS tests), average retry count per issue, average processing time, and failure category breakdown—with target resolution rate of 10-20% (modest but credible given state-of-the-art systems achieve 12-15% on SWE-bench Lite).

## 3.3 Scope of the Project

### In Scope (Version 1 - 6 Month Timeline):

- **Language**: Python only (3.8+), consistent with SWE-bench focus
- **Test Framework**: pytest exclusively (most common Python testing framework)
- **Bug Detection**: Test failure-based only (no static analysis of code without tests)
- **LLM Provider**: Claude API (Anthropic) via official SDK
- **Sandboxing**: Docker containers for isolated patch validation
- **Version Control**: GitHub only (creating branches, commits, PRs via REST API + PyGithub)
- **Evaluation**: SWE-bench Lite subset (~20-30 sampled issues due to API cost constraints)
- **Frontend**: React dashboard with live pipeline status, diff viewer, retry tracker
- **Backend API**: FastAPI exposing pipeline status and controls
- **Orchestration**: Custom Python implementation (fixed-sequence pipeline, no framework dependencies)
- **Deployment**: Local development + Docker Compose for multi-container setup

### Out of Scope (Deferred to Future Work):

- **Multi-language support**: JavaScript, Java, C++—each requires language-specific parsing, test frameworks, and evaluation datasets
- **Agent frameworks**: LangGraph, AutoGen, CrewAI—adds complexity without proven benefit at current scale; direct implementation prioritized for learning value
- **RAG/Vector databases**: ChromaDB, Pinecone for code retrieval—unnecessary when target files fit in LLM context windows; deferred until scaling to enterprise codebases
- **Static analysis integration**: Combining pytest failures with Pylint/Flake8 warnings—increases scope and evaluation complexity
- **Cloud deployment**: AWS Lambda, Azure Functions, GCP Cloud Run—local Docker sufficient for proof-of-concept and academic evaluation
- **Automatic merging**: System stops at PR creation; final merge decision remains human-controlled for safety
- **Security scanning**: Dedicated analysis of generated patches for vulnerabilities—requires separate security LLM fine-tuning
- **Multi-repository support**: Handling cross-repo dependencies or monorepos—single-repo focus for v1

### Scope Rationale:

The scoping decisions prioritize **shipping a complete, working, evaluated system** over feature breadth. As stated in project documentation: *"a scoped, working, evaluated project beats an ambitious incomplete one — both for the final submission and for resume/interview purposes."* Every cut feature is documented with clear reasoning (e.g., no RAG because code fits in context; no LangGraph because team needs to understand orchestration logic directly) and marked as explicit future work.

## 3.4 Expected Contribution

This project makes the following contributions:

**Technical Contribution**: A complete, end-to-end automated bug-fixing system demonstrating genuine agentic behavior (autonomous observation of test results, adaptive retry with self-correction) evaluated on real-world benchmarks (SWE-bench Lite), bridging the gap between bug detection tools and code generation tools.

**Practical Contribution**: An open-source implementation (GitHub: Musashiii03/4o4PR) with Docker-based reproducibility, comprehensive documentation of design decisions (including what was cut and why), and a live dashboard for transparency into agent reasoning—usable by researchers for ablation studies or practitioners for integration into CI/CD workflows.

**Research Contribution**: Empirical data on self-correction effectiveness (how often does a second or third retry succeed vs. first attempt failure?), failure pattern analysis (categorizing why patches fail: wrong file, incomplete fix, broken tests, timeout), and prompt engineering insights (which prompt structures yield higher fix rates)—published as evaluation results with full reproducibility details.

**Educational Contribution**: A case study in realistic scoping for team-based capstone projects, demonstrating how to balance ambition with deliverability, document trade-offs explicitly, and prioritize evaluation credibility (standardized benchmarks) over inflated self-reported metrics (toy examples).

**Expected artifacts**: (1) Complete system source code with >80% test coverage, (2) SWE-bench Lite evaluation results on 20-30 issues with per-issue logs, (3) React dashboard deployed locally with demo recordings, (4) Comprehensive design document explaining architecture and scoping rationale, (5) Comparative analysis vs. state-of-the-art (SWE-agent, AutoCodeRover) using identical benchmark subset.

---

**[END OF CHUNK 1]**

---

## SUMMARY OF CHUNK 1

This chunk includes:
- ✅ Front matter (cover page, team details, supervisor placeholder)
- ✅ Table of Contents
- ✅ Section 1: Abstract (280 words, 8 keywords)
- ✅ Section 2: Introduction (Background, Motivation, Need, Overview, Organization)
- ✅ Section 3: Problem Statement, Objectives (5 specific), Scope, Expected Contribution

**Status**: Ready for review. Awaiting your approval before proceeding to **CHUNK 2 (Literature Survey + Research Gap)**.

**Action Required**:
1. Review content accuracy
2. Confirm supervisor name and designation to replace placeholders
3. Approve to proceed to CHUNK 2

**Estimated Pages**: Chunk 1 = ~6 pages when formatted in Word document
