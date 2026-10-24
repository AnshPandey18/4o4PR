# Comprehensive Indexer Implementation Guide

This document describes the updated indexer implementation (`index_v2.py` and `models_v2.py`) that implements all 6 task fixes.

## Task 1: Record Unresolved Calls with Details

**Goal**: Track calls that couldn't be resolved with detailed information about why.

### Implementation

**New Fields in `SymbolInfo`**:
```python
unresolved_calls: int  # Count of unresolved calls
unresolved: List[Dict[str, Any]]  # Detailed information for each
builtin_calls: List[str]  # Builtin function/method names
```

**Unresolved Entry Structure**:
```json
{
  "expr": "foo()",
  "name": "foo",
  "line": 42,
  "reason": "not_found"
}
```

**Reason Codes**:
- `"method_on_unknown_receiver"`: Method call on object other than `self` (e.g., `obj.method()`)
- `"dynamic_call"`: Call on variable or expression result (e.g., `callbacks[0]()`)
- `"external_module"`: Call on external module attribute (e.g., `external.func()`)
- `"not_found"`: Name not found in any scope

**Builtin Recognition**:
- Functions: `len`, `sum`, `print`, `int`, `str`, `list`, `dict`, `ValueError`, etc.
- Methods: `append`, `extend`, `split`, `join`, `upper`, `lower`, `get`, etc.
- All builtins are classified separately and counted in `builtin_calls`

### Key Method

```python
def _resolve_call(
    self,
    call_node: ast.Call,
    file_path: str,
    import_map: Dict[str, str],
    symbols: Dict[str, SymbolInfo]
) -> Tuple[Optional[str], Optional[Dict[str, Any]], bool]:
```

Returns tuple of `(symbol_id, unresolved_dict, is_builtin)`.

---

## Task 3: Fix Import Consistency

**Goal**: Every import has all required fields: `style`, `level`, `line`, `module`, `names`, `resolved_file`.

### Implementation

**Every Import Dict Must Have**:
```python
{
    'style': 'import' | 'from',       # Style of import
    'level': int,                      # 0 for absolute, 1+ for relative (.)
    'line': int,                       # Line number
    'module': str,                     # Module name ('' for 'from . import')
    'names': [                         # List of imported names
        {'name': str, 'asname': str|None}
    ],
    'resolved_file': str | None        # Resolved file path if successful
}
```

**Examples**:

```python
# import sys
{
    'style': 'import',
    'level': 0,
    'line': 1,
    'module': 'sys',
    'names': [{'name': 'sys', 'asname': None}],
    'resolved_file': None  # stdlib, not resolved to file
}

# from calculator import add
{
    'style': 'from',
    'level': 0,
    'line': 5,
    'module': 'calculator',
    'names': [{'name': 'add', 'asname': None}],
    'resolved_file': 'src/calculator.py'
}

# from . import utils
{
    'style': 'from',
    'level': 1,
    'line': 10,
    'module': '',
    'names': [{'name': 'utils', 'asname': None}],
    'resolved_file': 'src/utils.py'  # Relative to current file
}

# from ..other import func as f
{
    'style': 'from',
    'level': 2,
    'line': 15,
    'module': 'other',
    'names': [{'name': 'func', 'asname': 'f'}],
    'resolved_file': 'other/module.py'
}
```

### Key Method

```python
def _extract_imports_from_file(
    self,
    file_path: Path,
    rel_path: str
) -> List[Dict[str, Any]]:
```

Processes `ast.Import` and `ast.ImportFrom` nodes, extracting all metadata consistently.

---

## Task 4: Fix run_id vs generated_at Timezone

**Goal**: All timestamps use UTC consistently. Generate `run_id` from UTC time.

### Implementation

**UTC Helper Function**:
```python
def make_run_id(now_utc: datetime) -> str:
    """Create a run_id from UTC datetime.
    
    Format: r_YYYYMMDD_HHMMSS (e.g., r_20261020_124056)
    """
```

**Index Method Signature**:
```python
def index(
    self,
    run_id: Optional[str] = None,
    cache_dir: Optional[Path] = None,
    now_utc: Optional[datetime] = None
) -> IndexData:
```

**Behavior**:
1. If `now_utc` is None, uses `datetime.now(timezone.utc)`
2. Ensures datetime is UTC-aware (converts if necessary)
3. If `run_id` is None, generates from `now_utc`: `r_YYYYMMDD_HHMMSS`
4. `generated_at` derived from same `now_utc`: ISO format with `Z` suffix

**Example**:
```python
from datetime import datetime, timezone

now = datetime.now(timezone.utc)  # 2026-10-20 12:40:56 UTC
indexer = RepoIndexer(...)
index_data = indexer.index(now_utc=now)
# run_id: "r_20261020_124056"
# generated_at: "2026-10-20T12:40:56+00:00Z"
```

---

## Task 5: Index Constants, Classes, Methods, and References

**Goal**: Track constant definitions, class definitions, methods, and references between symbols.

### Implementation

**Symbol Kinds**:
- `"constant"`: Module-level `Assign` or `AnnAssign` (e.g., `PI = 3.14`)
- `"class"`: Class definition
- `"function"`: Module-level function
- `"method"`: Function inside a class

**Symbol ID Formats**:
- Constants: `file::NAME` (e.g., `src/config.py::DEBUG`)
- Functions: `file::func_name` (e.g., `src/utils.py::process`)
- Classes: `file::ClassName` (e.g., `src/models.py::User`)
- Methods: `file::ClassName.method_name` (e.g., `src/models.py::User.save`)

**Constant Extraction**:
```python
@dataclass
class SymbolInfo:
    value_preview: Optional[str]  # Source segment (max 80 chars)
    references: List[str]  # List of constant IDs used in this symbol
```

**References Detection**:
- Detects `ast.Name` nodes in `Load` context (reads)
- Skips local assignments and parameters (shadowing)
- Only includes constants from same file
- Builds `call_graph['references']` and `call_graph['referenced_by']`

**Example**:
```python
# src/config.py
DEBUG = True
MAX_RETRIES = 3

# src/api.py
def connect():
    if config.DEBUG:  # References DEBUG
        print(f"Retries: {config.MAX_RETRIES}")  # References MAX_RETRIES
```

Would generate:
```json
{
  "call_graph": {
    "references": {
      "src/api.py::connect": [
        "src/config.py::DEBUG",
        "src/config.py::MAX_RETRIES"
      ]
    },
    "referenced_by": {
      "src/config.py::DEBUG": ["src/api.py::connect"],
      "src/config.py::MAX_RETRIES": ["src/api.py::connect"]
    }
  }
}
```

---

## Task 6: Improvements

### 6a: Calculate Metrics for All Symbols

**New Fields in SymbolInfo**:
```python
line_count: int  # Number of lines from start to end
char_count: int  # len(source) // 4
approx_tokens: int  # char_count (estimates tokens)
```

**Calculation**:
```python
line_count = line_end - line_start + 1
source_segment = '\n'.join(source_lines[line_start-1:line_end])
char_count = len(source_segment) // 4  # Rough estimate
approx_tokens = max(1, char_count)
```

### 6b: Handle Decorated Functions/Classes

**Requirement**: `line_start` must be the first decorator's line if decorated, not the `def`/`class` line.

**Implementation**:
```python
line_start = node.lineno
if node.decorator_list:
    line_start = min(dec.lineno for dec in node.decorator_list)
```

**Example**:
```python
@property  # line 10
@cached    # line 11
def value(self):  # line 12
    return 42

# Symbol: line_start = 10 (first decorator), line_end = 12
```

### 6c: Generate test_to_source from call_graph

**Single Function**:
```python
def _generate_test_to_source(
    self,
    call_graph: Dict[str, Any],
    symbols: Dict[str, SymbolInfo]
) -> Dict[str, List[str]]:
```

Maps test functions to source functions they directly call.

**Example**:
```json
{
  "test_to_source": {
    "tests/test_math.py::test_add": ["src/math.py::add"],
    "tests/test_math.py::test_multiply": ["src/math.py::multiply"]
  }
}
```

### 6d: Add Transitive Mapping

**New Function**:
```python
def _generate_test_to_source_transitive(
    self,
    call_graph: Dict[str, Any],
    symbols: Dict[str, SymbolInfo],
    max_depth: int = 3
) -> Dict[str, List[str]]:
```

Maps test functions to source functions reachable through callees up to depth 3.

**Algorithm**:
- BFS from test function
- Traverse through callees
- Collect all source functions encountered
- Skip test functions during traversal
- Limit depth to avoid infinite traversal

**Example**:
```python
# Call chain: test_main -> main -> helper -> util
# Direct: test_main -> main
# Transitive (depth=3): test_main -> main, helper, util

{
  "test_to_source": {
    "test_main": ["main"]
  },
  "test_to_source_transitive": {
    "test_main": ["main", "helper", "util"]
  }
}
```

### 6e: Handle Parse Errors

**Requirement**: Files with syntax errors appear in `files` with `parse_ok: false` and entry in `parse_errors`.

**Implementation**:
```python
except SyntaxError as e:
    logger.warning(f"Syntax error in {rel_path}: {e}")
    parse_errors.append(ParseError(
        file=rel_path,
        line=e.lineno or 0,
        message=str(e)
    ))
    # Still record the file
    files[rel_path] = FileInfo(
        path=rel_path,
        kind="test" if is_test_file(rel_path, self.test_dirs) else "source",
        module=None,
        lines=0,
        sha1=sha1_file(file_path),
        parse_ok=False
    )
```

**Output**:
```json
{
  "files": {
    "src/broken.py": {
      "kind": "source",
      "parse_ok": false,
      "lines": 0,
      "sha1": "abc123..."
    }
  },
  "parse_errors": [
    {
      "file": "src/broken.py",
      "line": 5,
      "message": "invalid syntax (<string>, line 5)"
    }
  ]
}
```

---

## Integration Guide

### Update Existing Code

To integrate these changes:

1. **Replace models.py**:
   ```bash
   cp models_v2.py models.py
   ```

2. **Replace index.py**:
   ```bash
   cp index_v2.py index.py
   ```

3. **Update imports** in other files if they reference old model names

### Backward Compatibility

New fields are added; old fields preserved:
- Existing code reading `callees` and `callers` continues to work
- New `references` and `referenced_by` are optional
- `unresolved` list is new; code checking `unresolved_calls` count still works

### Usage Example

```python
from pathlib import Path
from indexer.index import RepoIndexer, make_run_id
from datetime import datetime, timezone

project_root = Path('/path/to/project')
indexer = RepoIndexer(
    project_root=project_root,
    import_roots=['src'],
    test_dirs=['tests'],
    exclude_patterns=['**/__pycache__', '**/*.pyc']
)

# Generate index with UTC time
now_utc = datetime.now(timezone.utc)
index_data = indexer.index(now_utc=now_utc)

print(f"Run ID: {index_data.run_id}")
print(f"Generated at: {index_data.generated_at}")

# Access symbols
for symbol_id, symbol in index_data.symbols.items():
    print(f"{symbol_id}: {symbol.kind}")
    if symbol.kind == "constant":
        print(f"  Value: {symbol.value_preview}")
    if symbol.references:
        print(f"  References: {symbol.references}")
    if symbol.unresolved:
        for unres in symbol.unresolved:
            print(f"  Unresolved: {unres['expr']} (reason: {unres['reason']})")

# Test-to-source mappings
print("\nDirect mappings:")
for test_id, source_ids in index_data.test_to_source.items():
    print(f"{test_id} -> {source_ids}")

print("\nTransitive mappings:")
for test_id, source_ids in index_data.test_to_source_transitive.items():
    print(f"{test_id} => {source_ids}")

# Call graph with references
call_graph = index_data.call_graph
for symbol_id, refs in call_graph.get('references', {}).items():
    print(f"{symbol_id} uses: {refs}")
```

---

## Summary of Changes

| Task | Feature | File | Method/Field |
|------|---------|------|--------------|
| 1 | Unresolved calls | models_v2.py | `unresolved`, `builtin_calls` |
| 1 | Call resolution | index_v2.py | `_resolve_call()` |
| 3 | Import consistency | index_v2.py | `_extract_imports_from_file()` |
| 4 | UTC timezone | index_v2.py | `make_run_id()`, `index()` |
| 5 | Constants | index_v2.py | `_extract_constant_info()` |
| 5 | References | index_v2.py | `_extract_references()`, `_find_constant_references()` |
| 6 | Metrics | models_v2.py | `line_count`, `char_count`, `approx_tokens` |
| 6 | Decorated symbols | index_v2.py | `_extract_function_info()`, `_extract_class_info()` |
| 6 | test_to_source | index_v2.py | `_generate_test_to_source()` |
| 6 | test_to_source_transitive | index_v2.py | `_generate_test_to_source_transitive()` |
| 6 | Parse error handling | index_v2.py | `index()` try/except block |

---

## Testing Recommendations

1. **Import Resolution**: Verify all import styles parse correctly with proper `level` and `resolved_file`
2. **Unresolved Calls**: Check reason codes are correct for various call patterns
3. **Constants**: Verify constants are extracted and referenced correctly
4. **Metrics**: Validate line/char/token counts match actual source
5. **Test Mappings**: Ensure transitive mapping discovers all reachable sources
6. **Parse Errors**: Test on files with syntax errors, verify proper handling

