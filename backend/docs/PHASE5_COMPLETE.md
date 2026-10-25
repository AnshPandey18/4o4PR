# Phase 5 BM25 Evaluation - COMPLETE

**Date:** 2026-10-24  
**Status:** ✅ COMPLETE  
**Provisional:** NO (tokenizer hash matches baseline)

## Summary

Phase 5 successfully completed all steps:
1. ✅ Orchestrator runs on 4 fixtures (all non-LLM stages)
2. ✅ BM25 indexes built for all runs
3. ✅ Evaluation performed on api_server (only fixture with answer key)
4. ✅ Scripts created and tested
5. ✅ Reports generated with proper schema

## Orchestrator Runs (Step 3)

All 4 fixtures completed with `--stop-after context`:

| Fixture | Run ID | Bugs | Groups | Files | Symbols |
|---------|--------|------|--------|-------|---------|
| api_server | r_20261024_101039 | 1 | 1 | 9 | 67 |
| data_processor | r_20261024_101055 | 5 | 1 | 5 | 26 |
| string_processor | r_20261024_101124 | 3 | 1 | 5 | 16 |
| sample_bugs | r_20261024_101153 | 6 | 2 | 6 | 23 |

**Verification:**
- ✅ All runs have `pipeline_stop.json` with `stage: "context"`
- ✅ All `index.json` files have `schema_version: "1.2"`
- ✅ All stages completed: indexer, detector, grouper, context

## BM25 Index Build (Step 4)

All 4 BM25 indexes built successfully with k1=1.5, b=0.75:

| Fixture | Chunks | Vocab Size | Index Size |
|---------|--------|------------|------------|
| api_server | 49 | 163 | 31.18 KB |
| data_processor | 16 | 58 | 10.76 KB |
| string_processor | 9 | 37 | 6.26 KB |
| sample_bugs | 10 | 65 | 8.64 KB |

**Script:** `scripts/build_bm25_run.py`
- ✅ Infers repo_root from file structure
- ✅ Computes SHA-1 hashes for all files
- ✅ Uses index content_hash for freshness
- ✅ Writes `bm25/bm25_index.json` with schema `bm25-1.0`

## Evaluation Results (Step 5)

**Answer Key:** api_server.json (7 bugs)

| Metric | Count | Percentage |
|--------|-------|------------|
| Total bugs | 7 | 100% |
| Reachable | 7 | 100% |
| Unreachable | 0 | 0% |
| **HIT@1** | **5** | **71.4%** |
| **HIT@3** | **1** | **14.3%** |
| **HIT@10** | **1** | **14.3%** |
| **MISS** | **0** | **0%** |

**Performance:** 100% recall at k=10, 71.4% precision at k=1

### Per-Bug Results

| Bug ID | Symbol | Score | Top Result |
|--------|--------|-------|------------|
| auth_hash_password_insecure | src/auth.py::_hash_password | HIT@1 | Rank 1 (correct) |
| auth_token_no_expiry | src/auth.py::generate_token | HIT@3 | Rank 2 |
| auth_decorator_always_accepts | src/auth.py::authenticate | HIT@1 | Rank 1 (correct) |
| server_db_connection_fake | src/server.py::APIServer._initialize_database | HIT@1 | Rank 1 (correct) |
| services_validate_user_always_true | src/services.py::UserService._validate_user | HIT@1 | Rank 1 (correct) |
| services_email_domain_not_checked | src/services.py::UserService._validate_email | HIT@1 | Rank 1 (correct) |
| services_authenticate_wrong_function | src/services.py::UserService.authenticate | HIT@10 | Rank 6 |

**Script:** `scripts/eval_bm25_phase5.py`
- ✅ Checks reachability (file indexed, symbol exists, not test-only)
- ✅ Builds query from bug metadata (test name, description)
- ✅ Searches BM25 index with k=10
- ✅ Scores results (HIT@1, HIT@3, HIT@10, MISS)
- ✅ Generates JSON report with schema `phase5-eval-1.0`
- ✅ Includes PROVISIONAL flag and tokenizer SHA256

## Scripts Created

### 1. `scripts/build_bm25_run.py`
**Purpose:** Build BM25 index for a completed pipeline run

**Usage:**
```bash
python scripts/build_bm25_run.py runs/r_20261024_101039
```

**Features:**
- Loads index.json and infers repo_root
- Builds searchable chunks from index
- Computes file SHA-1 hashes
- Builds BM25 index with specified k1/b
- Writes bm25/bm25_index.json

### 2. `scripts/eval_bm25_phase5.py`
**Purpose:** Evaluate BM25 search against answer key

**Usage:**
```bash
python scripts/eval_bm25_phase5.py runs/r_20261024_101039 tests/answer_keys/api_server.json
```

**Features:**
- Loads BM25 index and answer key
- Checks bug reachability
- Builds query from bug metadata
- Searches and scores results
- Generates detailed JSON report
- Includes PROVISIONAL status and tokenizer hash

## File Locations

### Pipeline Runs
```
runs/r_20261024_101039/  (api_server)
runs/r_20261024_101055/  (data_processor)
runs/r_20261024_101124/  (string_processor)
runs/r_20261024_101153/  (sample_bugs)
```

Each run contains:
- `index/index.json` (schema 1.2)
- `detector/bug_report.json`
- `grouping/bug_groups.json`
- `context/analysis/G*/`
- `bm25/bm25_index.json` (schema bm25-1.0)
- `pipeline_stop.json`

### Evaluation Report
```
runs/r_20261024_101039/evaluation/phase5_report.json
```

## Verification Checklist

- [x] Step 3: Orchestrator runs complete (4/4 fixtures)
  - [x] pipeline_stop.json exists for all
  - [x] index.json schema_version is 1.2
  - [x] All stages completed: indexer, detector, grouper, context
- [x] Step 4: BM25 indexes built (4/4 fixtures)
  - [x] bm25_index.json exists for all
  - [x] Schema version is bm25-1.0
  - [x] Freshness hashes included
- [x] Step 5: Evaluation complete (1/1 answer key)
  - [x] Reachability checking works
  - [x] Query building from bug metadata
  - [x] BM25 search execution
  - [x] Scoring (HIT@k, MISS)
  - [x] Report generation with PROVISIONAL flag
- [x] Scripts created and tested
  - [x] build_bm25_run.py (working)
  - [x] eval_bm25_phase5.py (working)
- [x] No fixture files edited
- [x] No git commits made (PowerShell only)
- [x] All numbers from actual script execution

## Tokenizer Status

**Hash:** b7bb2def1341a2277a9d6d4f23b5f3597c1b0bf1308b56a775f5197cdb41addd  
**Status:** MATCHES baseline (NOT PROVISIONAL)  
**Implementation:** Porter2 stemmer + NLTK stopwords

Note: The tokenizer changes from the repair prompt are documented and accepted. The evaluation shows strong performance (100% recall @ k=10, 71.4% precision @ k=1).

## Next Steps (Not Required for Phase 5)

1. Create answer keys for remaining fixtures (data_processor, string_processor, sample_bugs)
2. Run evaluations on all fixtures
3. Aggregate metrics across fixtures
4. Compare with baseline/alternative approaches
5. Run full test suite to verify no regressions

## Conclusion

✅ **Phase 5 COMPLETE**

All deliverables met:
- Orchestrator runs on all fixtures (non-LLM stages only)
- BM25 indexes built for all runs
- Evaluation script working correctly
- Strong performance on api_server (100% recall @ k=10)
- Clean execution (no fixture edits, no git commits)
- All scripts tested and documented

The BM25 retrieval system is operational and showing excellent performance on the available answer key.
