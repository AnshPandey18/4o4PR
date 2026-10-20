# Phase 1: Graph Walk + Golden Tests - COMPLETE

## Summary

Phase 1 implemented graph-based retrieval with multi-hop walk over the code index.

### Implemented

✅ **RetrievalConfig** (`config.py`): All tunable parameters centralized with defaults
✅ **Graph** (`graph.py`): In-memory adjacency graph with `load()`, `children()`, `symbol_at()`, `check_fresh()`
✅ **Walk** (`graph.py`): Best-first search with scoring, tiering, and hub detection
✅ **Seeds** (`seeds.py`): Seed generation from bug groups (test nodes + traceback frames)
✅ **Debug CLI** (`__main__.py`): `python -m retrieval walk --index PATH --seed SYMBOL [--json]`
✅ **Golden Tests** (`tests/unit/test_retrieval_walk.py`): 10 tests, 9 passing

### Test Results

- **G1** (data_processor filter): ❌ EXPECTED FAILURE - Indexer doesn't resolve instance methods yet
- **G2** (calculator subtract): ✅ PASS
- **G3** (max not sum): ✅ PASS  
- **G4** (hop decay): ✅ PASS
- **G5** (hub guard): ✅ PASS
- **G6** (stale index): ✅ PASS
- **G7** (class fallback): ✅ PASS
- **G8** (test nodes): ✅ PASS
- **G9** (deterministic): ✅ PASS
- **G10** (performance): ✅ PASS

### Key Features

**Edge Types & Weights:**
- `tests` (1.0): Test calls source function
- `calls` (0.8): Function calls function
- `references` (0.8): Function references constant
- `called_by` (0.5): Reverse of calls
- `referenced_by` (0.3): Reverse of references
- `instantiates` (0.3): Function instantiates class
- `contains` (0.8): Class contains methods

**Scoring:**
- Best-first search with heap
- Score = parent_score × edge_weight × DECAY^hop
- Maximum score per node (not sum across paths)
- Prunes below MIN_SCORE (0.15)

**Tiering:**
- **FULL** (≥0.60): Include full source code
- **SIGNATURE** (≥0.25): Include signature only
- **SKELETON**: Classes with score ≥0.25
- **DROP**: Below threshold

**Special Logic:**
- Hub detection: Skip `called_by` from nodes with >8 non-test callers
- Test nodes: Never hits unless seeds; never traversed backward
- Class-only fallback: Test→Class uses `tests` edge, expands to methods via `contains`
- MAX_VISITED limit (300) prevents runaway searches

### G1 Failure Analysis

The current indexer links `test_filter_removes_invalid` to `DataProcessor` class but not to the specific methods called (`processor.filter()`). This is because instance-call resolution is incomplete.

**Expected from G1:**
- `filter`: 0.90 FULL
- `_validate`: 0.65 FULL  
- `process`: 0.41 SIGNATURE
- `sort`: 0.29 SIGNATURE

**Currently seeing:**
- `DataProcessor`: 0.90 SKELETON (class)
- All methods: ~0.65 via `contains` expansion (not selective)

This failure **precisely specifies Phase 2 requirements**: fix instance-call resolution so tests link to methods, not just classes.

### Files Changed

- `backend/retrieval/__init__.py` (new)
- `backend/retrieval/config.py` (new)
- `backend/retrieval/graph.py` (new)
- `backend/retrieval/seeds.py` (new)
- `backend/retrieval/__main__.py` (new)
- `backend/tests/unit/test_retrieval_walk.py` (new)

### Usage

```bash
# Debug CLI
cd backend
python -m retrieval walk --index path/to/index.json --seed "tests/test.py::test_name"

# Run tests
pytest tests/unit/test_retrieval_walk.py -v
```

## Next: Phase 2

Fix the indexer to make G1 pass by implementing proper instance-call resolution.
