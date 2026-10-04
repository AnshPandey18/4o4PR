# 4o4PR Bug Detection and Analysis Pipeline

Professional implementation of Steps 1-4 of the 4o4PR automated bug detection and root cause analysis pipeline.

## Overview

This pipeline automatically detects bugs in Python projects, groups related bugs, and prepares context for LLM-based root cause analysis. It consists of four main stages:

```
┌─────────────────┐
│  1. Repo Index  │ ──┐
└─────────────────┘   │
                      ├─→ ┌──────────────────┐
┌─────────────────┐   │   │  3. Bug Grouper  │
│ 2. Bug Detector │ ──┘   └──────────────────┘
└─────────────────┘              │
                                 ▼
                      ┌────────────────────────┐
                      │  4. Context Builder    │
                      └────────────────────────┘
```

## Components

### 1. Repository Indexer

Builds a static index of your Python codebase:
- Extracts functions, classes, and methods using AST
- Resolves imports and builds call graphs
- Maps tests to source functions
- Caches results for fast re-indexing

**Usage:**
```bash
python -m indexer.cli \
    --root tests/fixtures/sample_bugs \
    --import-root src \
    --out runs/r_20231201_120000/index/index.json
```

### 2. Bug Detector (v2.0)

Runs pytest and creates detailed bug reports:
- Uses custom pytest plugin for structured results
- Resolves called symbols via import analysis
- Normalizes all paths to POSIX format
- Extracts and counts assertions
- Detects flaky tests with configurable reruns
- Generates bug_id via stable hashing

**Fixes from v1.0:**
- ✓ Correct summary counts (no more zeros)
- ✓ Real source symbol resolution
- ✓ Windows path normalization
- ✓ Complete assertion analysis
- ✓ Flaky test detection
- ✓ Baseline results generation

**Usage:**
```bash
python -m detector.cli \
    --root tests/fixtures/sample_bugs \
    --import-root src \
    --out-dir runs/r_20231201_120000/detector
```

**Outputs:**
- `bug_report.json` - Structured bug reports (schema v2.0)
- `bug_report.md` - Human-readable markdown report
- `baseline_results.json` - All test outcomes for validation

### 3. Bug Grouper

Clusters related bugs for efficient analysis:
- Groups by suspect symbol and file
- Excludes flaky bugs
- Separate groups for collection errors
- Splits oversized groups by token budget
- Enforces invariant: every bug appears exactly once

**Usage:**
```bash
python -m grouper.cli \
    --bug-report runs/r_20231201_120000/detector/bug_report.json \
    --index runs/r_20231201_120000/index/index.json \
    --out runs/r_20231201_120000/grouping/bug_groups.json
```

### 4. Context Builder

Assembles LLM prompts with token budgeting:
- Loads templates (system rules + output schema)
- Retrieves relevant code from index
- Sanitizes test code (removes docstrings/comments)
- Redacts secrets from source code
- Manages token budget with tiered priorities (T0-T6)
- Generates detailed manifest

**Tiers:**
- **T0**: System rules (required)
- **T1**: Failure evidence (required)
- **T2**: Test code, sanitized (required)
- **T3**: Suspect functions with line numbers (required)
- **T4**: Neighbor functions - signatures only (optional)
- **T5**: Repository map (optional)
- **T6**: Output schema (required)

**Usage:**
```bash
python -m context.cli \
    --bug-groups runs/r_20231201_120000/grouping/bug_groups.json \
    --bug-report runs/r_20231201_120000/detector/bug_report.json \
    --index runs/r_20231201_120000/index/index.json \
    --group-id G1 \
    --out-dir runs/r_20231201_120000/context/analysis/G1/attempt_1
```

**Outputs:**
- `analysis_context.txt` - Complete prompt for LLM
- `context_manifest.json` - Detailed build metadata

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Required:
# - pytest >= 8.0.0
# - pyyaml >= 6.0.0

# Optional (for accurate token counting):
# pip install tiktoken
```

## Configuration

Edit `config/settings.yaml` to customize:

```yaml
project_root: "."
import_roots: ["src"]
test_dirs: ["tests"]
exclude_dirs: ["__pycache__", ".git", ".venv", "runs", "cache"]

detector:
  timeout_seconds: 300
  flaky_reruns: 2
  embed_source_snapshot: true
  snapshot_max_lines: 80

grouper:
  max_bugs_per_group: 8

context:
  analysis:
    input_budget: 10000
    output_reserved: 1500
  token_counter: "estimate"  # or "tiktoken"
```

## Quick Start with Sample Project

The `tests/fixtures/sample_bugs` directory contains a sample project with 6 intentional bugs.

### Run Complete Pipeline:

```bash
# Set working directory to sample project
cd tests/fixtures/sample_bugs

# Create run directory
RUN_ID="r_$(date +%Y%m%d_%H%M%S)"
mkdir -p ../../../runs/$RUN_ID/{index,detector,grouping,context/analysis}

# Step 1: Index the repository
python -m indexer.cli \
    --root . \
    --import-root src \
    --out ../../../runs/$RUN_ID/index/index.json \
    --config ../../../config/settings.yaml

# Step 2: Detect bugs
python -m detector.cli \
    --root . \
    --import-root src \
    --out-dir ../../../runs/$RUN_ID/detector \
    --config ../../../config/settings.yaml

# Step 3: Group bugs
python -m grouper.cli \
    --bug-report ../../../runs/$RUN_ID/detector/bug_report.json \
    --index ../../../runs/$RUN_ID/index/index.json \
    --out ../../../runs/$RUN_ID/grouping/bug_groups.json \
    --config ../../../config/settings.yaml

# Step 4: Build context for first group
python -m context.cli \
    --bug-groups ../../../runs/$RUN_ID/grouping/bug_groups.json \
    --bug-report ../../../runs/$RUN_ID/detector/bug_report.json \
    --index ../../../runs/$RUN_ID/index/index.json \
    --group-id G1 \
    --out-dir ../../../runs/$RUN_ID/context/analysis/G1/attempt_1 \
    --config ../../../config/settings.yaml
```

### Expected Results:

- **10 tests run**: 4 pass, 6 fail
- **6 bugs detected**: all in calculator.py and string_utils.py
- **2 bug groups**: G1 (calculator.py), G2 (string_utils.py)
- **Context built**: Ready for LLM analysis

## Project Structure

```
backend/
├── common/              # Shared utilities
│   ├── paths.py        # Path normalization
│   ├── pyresolve.py    # Import resolution
│   ├── hashing.py      # Content hashing
│   ├── io.py           # Atomic I/O
│   └── tokens.py       # Token counting
├── config/
│   ├── settings.yaml   # Configuration
│   └── settings.py     # Settings loader
├── indexer/            # Repository indexer
│   ├── models.py
│   ├── index.py
│   ├── query.py
│   └── cli.py
├── detector/           # Bug detector
│   ├── models.py
│   ├── detector.py
│   ├── pytest_plugin.py
│   ├── pytest_results.py
│   ├── markdown.py
│   └── cli.py
├── grouper/            # Bug grouper
│   ├── models.py
│   ├── group.py
│   └── cli.py
├── context/            # Context builder
│   ├── models.py
│   ├── builder.py
│   ├── sanitizer.py
│   └── cli.py
├── prompts/
│   └── analysis_v1/
│       ├── system_rules.md
│       └── output_schema.json
├── runs/               # Output directory
├── cache/              # Index cache
└── tests/
    └── fixtures/
        └── sample_bugs/
```

## Schema Versions

- **Index**: v1.0
- **Bug Report**: v2.0 (major upgrade from v1.0)
- **Bug Groups**: v1.0
- **Context Manifest**: v1.0
- **Baseline Results**: v1.0

## Key Features

### Deterministic Output
- Sorted JSON keys
- Stable ordering throughout
- Content-based hashing for caching
- Same input → identical output (except timestamps)

### Token Budget Management
- Soft caps per tier with overflow to next tier
- Required tiers checked first
- Graceful degradation (full → signature → drop)
- Detailed manifest tracking

### Security & Safety
- Secret redaction (AWS keys, API keys, PEM files)
- File denylist (.env, *.key, *secret*)
- Docstring/comment sanitization
- No code execution (AST only)

### Cross-Platform
- POSIX path normalization
- Windows and Linux support
- Path-based import resolution

## Troubleshooting

### Issue: "Consistency check failed"
The detector's summary counts don't match the actual bug count. This means pytest's output parsing or the plugin failed. Check logs for details.

### Issue: "StaleIndexError"
A source file changed after indexing. Re-run the indexer.

### Issue: "Context overflow"
The required tiers exceed the token budget. Either:
1. Increase `input_budget` in settings.yaml
2. Split the bug group (lower `max_bugs_per_group`)

### Issue: Import resolution fails
Ensure `import_roots` in settings.yaml matches your project structure.

## Limitations & Future Work

**Not Implemented:**
- RCA Agent (LLM integration)
- Patch Generator
- Patch Validator
- GitHub PR creation
- Full `extend()` API for context expansion
- Embeddings/semantic search
- Call graph-based group merging

**Out of Scope:**
- Non-Python languages
- Distributed repositories
- Real-time analysis
- UI/Dashboard

## Development

The codebase follows professional Python standards:
- Type hints throughout
- Pydantic v2 models
- Logging (never print())
- UTF-8 everywhere
- Atomic file writes
- AST parsing (no regex hacks)

## License

Part of the 4o4PR project.

## Credits

Implements the specification from `docs/kiro_prompt_stage1_to_4.md`.
