# Design Notes: Future Enhancements

## Call-Site Line Tracking for Tie-Breaking

### Context
With the improved `var.attr.method()` resolution, retrieval now creates more call edges from tests to source functions. However, this introduces a tie-breaking problem.

### The Problem

Consider `test_server_login_flow`:
```python
def test_server_login_flow():
    server = APIServer()
    server.start()                          # Line 44 - setup
    # Create user
    server.user_service.create_user(...)    # Line 46 - setup
    # Login
    response = server._handle_login(...)    # Line 48 - call under test
    assert 'token' in response              # Line 49 - FAILING LINE
```

All three method calls resolve with equal score (0.90):
- `server.start()` → setup
- `server.user_service.create_user()` → setup
- `server._handle_login()` → **actual call under test**

**Current limitation:** Retrieval can't distinguish setup from the call under test.

### Why This Matters

When a test fails at line 49, the traceback tells us:
```
test_server_login_flow:49: AssertionError
```

We want to prioritize `_handle_login` (called at line 48, adjacent to failure) over `start` and `create_user` (called at lines 44-46, further away).

### Current Behavior

Without call-site information:
```
EXPANDED tier (all score=0.648 after hop decay):
  5. create_user
  6. _validate_user
  7. _validate_email  
  8. _hash_password
  ...
```

The entire `create_user` subtree gets pulled in at high relevance, even though it's just setup code.

### Proposed Solution

**Add call-site line tracking to call graph:**

```python
call_graph = {
    "callees": {
        "test_id": ["callee1", "callee2", "callee3"]
    },
    "call_sites": {
        "test_id": {
            "callee1": [44],      # start() at line 44
            "callee2": [46],      # create_user() at line 46  
            "callee3": [48]       # _handle_login() at line 48
        }
    }
}
```

### Implementation Changes

**1. Indexer: Record call sites during AST walk**

```python
# In _extract_calls()
for node in ast.walk(func_node):
    if isinstance(node, ast.Call):
        callee_id, unresolved, is_builtin = self._resolve_call(...)
        if callee_id:
            callees.append(callee_id)
            call_sites[callee_id].append(node.lineno)  # NEW
```

**2. Retrieval: Use call sites for tie-breaking**

```python
# In walk(), when scoring edges from test to source
if bug.failing_line and test_id in call_sites:
    for callee_id, lines in call_sites[test_id].items():
        # Distance from failing line to nearest call site
        min_distance = min(abs(line - bug.failing_line) for line in lines)
        
        # Boost score for calls near the failure
        if min_distance == 0:
            proximity_boost = 0.2  # Called on failing line
        elif min_distance <= 2:
            proximity_boost = 0.1  # Called within 2 lines
        else:
            proximity_boost = 0.0
        
        edge_score += proximity_boost
```

### Expected Improvement

**Before (no call-site info):**
```
CORE tier:
  1. test_server_login_flow (seed)
  
EXPANDED tier (all equal after hop):
  2. start (0.648)
  3. create_user (0.648)
  4. _handle_login (0.648)  ← Should be higher!
```

**After (with call-site proximity):**
```
CORE tier:
  1. test_server_login_flow (seed)
  
EXPANDED tier:
  2. _handle_login (0.748)  ← Boosted (line 48, near line 49)
  3. create_user (0.648)
  4. start (0.648)
```

### Benefits

1. **More precise context**: Prioritizes code actually involved in the failure
2. **Better tie-breaking**: Uses traceback information meaningfully
3. **Reduced noise**: Setup code scores lower than tested code
4. **Smaller contexts**: Fewer irrelevant symbols in FULL tier

### When It Helps

- ✅ **Test failures with tracebacks** (know the failing line)
- ✅ **Tests with setup/teardown** (multiple calls at different distances)
- ✅ **Integration tests** (many calls to distinguish)

### When It Doesn't Matter

- ❌ **BM25 retrieval** (already uses text positions)
- ❌ **Tests without line info** (rare, but possible)
- ❌ **Single-call tests** (no ties to break)

### Scope

**This enhancement is for graph-based retrieval ONLY.**

BM25 already has positional information through the text itself, so it doesn't need call-site lines. The graph walk needs this because it only sees edges, not the source code.

### Implementation Priority

**Medium priority.** The current graph walk works correctly; this would make it more precise.

**Suggested approach:**
1. Add `call_sites` to call_graph during indexing (non-breaking: old consumers ignore it)
2. Update retrieval to use call_sites when available (graceful degradation if missing)
3. Add tests: verify proximity boost affects ranking as expected

### Testing Strategy

```python
def test_call_site_proximity_boosting():
    """Verify calls near failing line score higher."""
    # Create test with:
    #   Line 10: setup_call()
    #   Line 20: target_call()  ← Failing line = 21
    #   Line 30: teardown_call()
    
    # Run retrieval with failing_line=21
    hits = walk(graph, seeds, config, failing_line=21)
    
    # Verify: target_call > setup_call, teardown_call
    target_rank = next(i for i, h in enumerate(hits) if 'target_call' in h.symbol_id)
    setup_rank = next(i for i, h in enumerate(hits) if 'setup_call' in h.symbol_id)
    
    assert target_rank < setup_rank
```

---

## Other Future Enhancements

### 1. Multi-hop Scoring Decay Tuning

Current decay: `score * 0.72` per hop

Consider:
- **Edge-type-specific decay**: Calls decay less than references?
- **Tier-aware decay**: Less decay within CORE, more in FALLBACK?

### 2. Parameter Type Resolution

Current: Only resolve `self.attr` through `attr_types`

Enhancement: Resolve parameter types through annotations:
```python
def process(data: DataFrame) -> Result:
    return data.apply(...)  # Could resolve 'apply' to DataFrame.apply
```

### 3. Constant Value Tracking

Current: Constants have `value_preview` but aren't used in resolution

Enhancement: Track constant assignments to resolve:
```python
MAX_SIZE = 100
def check(n):
    if n > MAX_SIZE:  # Could link to MAX_SIZE constant
        ...
```

### 4. Import Star Resolution

Current: `from module import *` tracked but not resolved

Enhancement: Resolve star imports through actual module inspection (carefully, to avoid code execution)

---

## Notes for Maintainers

### Schema Evolution

When bumping schema version:
1. Update `SCHEMA_VERSION` constant in `indexer/index.py`
2. Add new fields to `SymbolInfo` or `IndexData` in `models.py`
3. Update `to_dict()` and `from_dict()` methods
4. Add migration logic if needed (for backward compat)
5. Update tests to verify new schema

### Testing Philosophy

**Indexer tests should:**
- Use temp projects (no fixture dependence)
- Test one feature per test
- Verify actual resolution, not just counts
- Include both positive and negative cases

**Integration tests should:**
- Use real fixtures (api_server, data_processor)
- Verify end-to-end pipelines
- Check file outputs (index.json, bug_report.json)
- Ensure schema consistency

### Performance Considerations

**Current bottlenecks:**
1. AST parsing (unavoidable, but cached per file)
2. Call resolution (many symbol lookups)
3. JSON serialization (large indexes)

**Optimization opportunities:**
- Index symbols by name for faster lookup
- Stream JSON output for very large repos
- Parallelize file parsing (be careful with shared state)

---

## Conclusion

The indexer is production-ready with schema 1.2. Future enhancements (especially call-site tracking) would improve retrieval precision but are not blockers for current use.

**Priority:**
1. **High:** Fix Bug Detector stats parsing (pre-existing issue)
2. **Medium:** Add call-site line tracking (this doc)
3. **Low:** Other enhancements listed above
