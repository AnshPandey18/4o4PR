# Quick Start Guide

Get started with the 4o4PR pipeline in 5 minutes.

## Prerequisites

```bash
# Python 3.10+
python --version

# Install dependencies
pip install pytest pyyaml
```

## Run on Sample Project

The fastest way to see the pipeline in action:

```bash
# Navigate to backend directory
cd backend

# Run complete pipeline on sample project
python run_pipeline.py \
    --root tests/fixtures/sample_bugs \
    --import-root src \
    --verbose
```

This will:
1. Index the sample project
2. Detect 6 bugs (3 in calculator, 3 in string_utils)
3. Group bugs into 2 groups
4. Build analysis context for each group

## Output Structure

```
runs/r_YYYYMMDD_HHMMSS/
├── index/
│   └── index.json                    # Repository index
├── detector/
│   ├── bug_report.json               # Structured bug reports
│   ├── bug_report.md                 # Human-readable report
│   └── baseline_results.json         # All test outcomes
├── grouping/
│   └── bug_groups.json               # Grouped bugs
└── context/
    └── analysis/
        ├── G1/
        │   └── attempt_1/
        │       ├── analysis_context.txt    # LLM prompt
        │       └── context_manifest.json   # Build metadata
        └── G2/
            └── attempt_1/
                ├── analysis_context.txt
                └── context_manifest.json
```

## View Results

```bash
# View markdown report
cat runs/r_*/detector/bug_report.md

# View bug groups
cat runs/r_*/grouping/bug_groups.json | python -m json.tool

# View context for first group
cat runs/r_*/context/analysis/G1/attempt_1/analysis_context.txt
```

## Run Individual Steps

If you want more control, run each step separately:

```bash
RUN_ID="r_$(date +%Y%m%d_%H%M%S)"

# 1. Index
python -m indexer.cli \
    --root tests/fixtures/sample_bugs \
    --import-root src \
    --out runs/$RUN_ID/index/index.json

# 2. Detect
python -m detector.cli \
    --root tests/fixtures/sample_bugs \
    --import-root src \
    --out-dir runs/$RUN_ID/detector

# 3. Group
python -m grouper.cli \
    --bug-report runs/$RUN_ID/detector/bug_report.json \
    --index runs/$RUN_ID/index/index.json \
    --out runs/$RUN_ID/grouping/bug_groups.json

# 4. Build Context
python -m context.cli \
    --bug-groups runs/$RUN_ID/grouping/bug_groups.json \
    --bug-report runs/$RUN_ID/detector/bug_report.json \
    --index runs/$RUN_ID/index/index.json \
    --group-id G1 \
    --out-dir runs/$RUN_ID/context/analysis/G1/attempt_1
```

## Use on Your Own Project

```bash
python run_pipeline.py \
    --root /path/to/your/project \
    --import-root src \
    --import-root lib \
    --verbose
```

**Note:** Make sure your project has:
- pytest tests
- Proper import structure
- Tests that use imports (not sys.path hacks, or configure `import_roots` accordingly)

## Configuration

Edit `config/settings.yaml` to customize behavior:

```yaml
# Key settings
import_roots: ["src"]          # Where imports resolve from
test_dirs: ["tests"]            # Where tests are located
exclude_dirs: ["__pycache__"]   # Directories to skip

detector:
  flaky_reruns: 2               # Rerun tests to detect flakiness
  
grouper:
  max_bugs_per_group: 8         # Split large groups

context:
  analysis:
    input_budget: 10000         # Token budget for prompts
```

## Next Steps

1. **Review the bug report** - Check `bug_report.md` for human-readable summary
2. **Inspect bug groups** - See how bugs were clustered in `bug_groups.json`
3. **Examine context** - Look at `analysis_context.txt` to see what the LLM would receive
4. **Integrate with LLM** - Use the context files as prompts for Claude, GPT-4, etc.

## Common Issues

### "No bugs detected"
✓ Your tests pass! The pipeline only processes failing tests.

### "Consistency check failed"
The pytest plugin may have issues. Check logs with `--verbose`.

### "Context overflow"
Increase `input_budget` in settings.yaml or lower `max_bugs_per_group`.

### Import resolution fails
Ensure `import_roots` matches your project structure. Use `--import-root` multiple times if needed.

## Performance

On the sample project (~200 lines, 10 tests):
- **Indexing**: <1 second
- **Detection**: 1-2 seconds
- **Grouping**: <1 second  
- **Context**: <1 second
- **Total**: ~3 seconds

## What's Next?

The pipeline prepares everything for root cause analysis. The next phases would be:
- Send `analysis_context.txt` to an LLM for RCA
- Generate patches based on RCA
- Validate patches in sandbox
- Create GitHub PRs

These are not implemented yet (see README for limitations).

## Support

For issues or questions, see the main README.md.
