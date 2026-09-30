# Bug Detector Module - Design Document

## Overview

The Bug Detector is the first stage of the Automated Bug Fixing Agent pipeline. It identifies failing tests in Python repositories and extracts structured information about bugs for downstream processing.

## Architecture

### Component Design

```
┌─────────────────────────────────────────────────────────────┐
│                      Bug Detector                            │
│                                                              │
│  Input: Repository Path + Optional Test Files               │
│  Output: BugDetectionResult (List of BugReports)            │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  1. Validation                                      │    │
│  │     - Check repo exists                             │    │
│  │     - Check pytest available                        │    │
│  └────────────────────────────────────────────────────┘    │
│                        ↓                                     │
│  ┌────────────────────────────────────────────────────┐    │
│  │  2. Test Execution                                  │    │
│  │     - Run pytest with args                          │    │
│  │     - Capture stdout/stderr                         │    │
│  │     - Handle timeouts                               │    │
│  └────────────────────────────────────────────────────┘    │
│                        ↓                                     │
│  ┌────────────────────────────────────────────────────┐    │
│  │  3. Output Parsing                                  │    │
│  │     - Extract failed test names                     │    │
│  │     - Parse error messages                          │    │
│  │     - Extract file paths & line numbers             │    │
│  └────────────────────────────────────────────────────┘    │
│                        ↓                                     │
│  ┌────────────────────────────────────────────────────┐    │
│  │  4. Code Context Extraction                         │    │
│  │     - Parse source files with AST                   │    │
│  │     - Extract failing function                      │    │
│  │     - Extract surrounding context                   │    │
│  └────────────────────────────────────────────────────┘    │
│                        ↓                                     │
│  ┌────────────────────────────────────────────────────┐    │
│  │  5. Report Generation                               │    │
│  │     - Create BugReport objects                      │    │
│  │     - Compile statistics                            │    │
│  │     - Return BugDetectionResult                     │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Data Models

### BugReport

Represents a single failing test with complete context.

```python
@dataclass
class BugReport:
    test_name: str              # "tests/test_math.py::test_divide"
    error_type: str             # "AssertionError"
    error_message: str          # "assert 12 == 5"
    file_path: str              # "src/math_utils.py"
    line_number: int            # 13
    failing_function_code: str  # Complete function source
    context_before: str         # Lines before function
    context_after: str          # Lines after function
    traceback: Optional[str]    # Full stack trace
```

### BugDetectionResult

Contains all detected bugs and metadata.

```python
@dataclass
class BugDetectionResult:
    bugs: List[BugReport]       # All detected bugs
    total_tests_run: int        # Total test count
    total_failures: int         # Number of failures
    pytest_exit_code: int       # Pytest exit status
    
    @property
    def has_failures(self) -> bool
```

## Implementation Details

### 1. Repository Validation

**Purpose**: Ensure the target repository exists and is accessible.

**Process**:
- Check if path exists
- Verify it's a directory
- Raise `RepositoryNotFoundError` if invalid

**Edge Cases**:
- Symbolic links: Resolved to actual path
- Relative paths: Converted to absolute
- Windows paths: Handled correctly

### 2. Test Execution

**Purpose**: Run pytest and capture all output.

**Process**:
```python
cmd = ["pytest", "-v", "--tb=short"]
result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
```

**Features**:
- Verbose output for detailed information
- Short traceback format (more readable)
- 5-minute timeout to prevent hanging
- Captures both stdout and stderr
- Configurable additional arguments

**Exit Codes**:
- 0: All tests passed
- 1: Tests failed
- 2: Test execution interrupted
- 3: Internal error
- 4: pytest usage error
- 5: No tests collected

### 3. Output Parsing

**Purpose**: Extract failure information from pytest output.

**Strategy**: Use regex patterns to match pytest's output format.

**Patterns**:
```python
# Failed test pattern
r'^(.+?)::(.*?)\s+FAILED'

# Error location pattern
r'([^\s]+\.py):(\d+):'

# Error message patterns
r'([A-Z]\w+(?:Error|Exception)):\s*(.+)'
r'E\s+(assert.+)'
```

**Extraction**:
1. Find FAILURES section in output
2. Split by test name headers
3. Extract error type and message
4. Parse traceback for file/line info

**Challenges**:
- Multiple output formats (short/long/line/native)
- Multiline error messages
- Nested tracebacks
- Custom error types

**Solution**: Parse conservatively, handle missing information gracefully.

### 4. Code Context Extraction

**Purpose**: Extract the failing function and surrounding code.

**Strategy**: Use Python's `ast` module for accurate parsing.

**Process**:

1. **Parse source file**:
```python
tree = ast.parse(source_code)
```

2. **Find function containing the line**:
```python
for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if func_start <= line_number <= func_end:
            return node
```

3. **Extract function code**:
```python
function_lines = source_lines[func_start-1:func_end]
return '\n'.join(function_lines)
```

4. **Extract context**:
```python
context_before = lines[start:func_start-1]
context_after = lines[func_end:end]
```

**Handles**:
- Regular functions
- Async functions
- Class methods
- Static/class methods
- Nested functions (returns outermost)
- Lambda functions
- Decorators

**Edge Cases**:
- **Syntax errors**: Returns lines around error location
- **Missing files**: Returns empty strings
- **Invalid line numbers**: Handled safely
- **End of file**: Doesn't exceed bounds

### 5. Report Generation

**Purpose**: Create structured reports for each bug.

**Process**:
1. For each parsed failure
2. Extract code context
3. Create `BugReport` object
4. Add to results list

**Error Handling**:
- Individual failures don't stop processing
- Warnings logged for extraction failures
- Partial data returned when available

## Design Principles

### 1. Separation of Concerns

Each method has a single, clear responsibility:
- `_validate_repository()`: Only validation
- `_run_pytest()`: Only test execution
- `_parse_pytest_output()`: Only parsing
- `_extract_code_context()`: Only code extraction

**Benefits**:
- Easy to test each component
- Easy to modify behavior
- Clear error boundaries

### 2. DRY (Don't Repeat Yourself)

No repetitive logic:
- Single pytest execution method
- Reusable parsing patterns
- Common error handling

### 3. Fail Gracefully

Never crash the entire process:
- Missing files → empty context
- Parsing errors → partial data
- One bug extraction failure → others continue

### 4. Clear Error Messages

Custom exceptions with context:
```python
raise RepositoryNotFoundError(f"Repository path does not exist: {repo_path}")
raise PytestNotInstalledError("pytest is not installed. Install with: pip install pytest")
```

### 5. Extensibility

Easy to extend:
- Add new parsing patterns
- Support other test frameworks
- Add more context extraction

## Integration with Pipeline

### Input (from User/API)

```python
{
    "repo_path": "/path/to/repo",
    "test_files": ["tests/test_math.py"],  # optional
    "pytest_args": ["-x", "--tb=long"]     # optional
}
```

### Output (to Patch Generator)

```python
BugDetectionResult(
    bugs=[
        BugReport(
            test_name="tests/test_math.py::test_divide",
            error_type="AssertionError",
            error_message="assert 12 == 5",
            file_path="src/math_utils.py",
            line_number=13,
            failing_function_code="def divide(a, b):\n    return a + b",
            context_before="...",
            context_after="..."
        )
    ],
    total_tests_run=5,
    total_failures=1,
    pytest_exit_code=1
)
```

### Usage in Patch Generator

```python
class PatchGenerator:
    def generate_patch(self, repo_path: str) -> List[Patch]:
        # Step 1: Detect bugs
        detector = BugDetector()
        result = detector.run(repo_path)
        
        if not result.has_failures:
            return []
        
        # Step 2: Generate fix for each bug
        patches = []
        for bug in result.bugs:
            # Use Claude API with:
            # - bug.failing_function_code (what's wrong)
            # - bug.error_message (what's expected)
            # - bug.context_before/after (surrounding code)
            patch = self._generate_fix_with_ai(bug)
            patches.append(patch)
        
        return patches
```

## Performance Considerations

### Time Complexity

- **Test execution**: O(n) where n = number of tests
- **Output parsing**: O(m) where m = output size
- **Code extraction**: O(f) where f = file size

Total: O(n + m + f) - Linear in all dimensions

### Space Complexity

- **Output storage**: O(m) for pytest output
- **Source file storage**: O(f) per file
- **BugReports**: O(k) where k = number of bugs

### Optimizations

1. **Lazy file reading**: Only read files with failures
2. **AST caching**: Could cache parsed ASTs for repeated files
3. **Parallel extraction**: Could extract code context in parallel
4. **Streaming**: Could stream pytest output for very large test suites

## Testing Strategy

### Test Coverage

1. **Happy path**: Repository with failing tests
2. **No failures**: All tests pass
3. **Edge cases**:
   - Missing repository
   - pytest not installed
   - Malformed output
   - Syntax errors in source
   - Nested functions
   - Class methods
   - Multiple failures
   - Invalid line numbers

### Test Fixtures

Use temporary directories with sample code:

```python
@pytest.fixture
def repo_with_failing_test(temp_repo):
    # Create src/math_utils.py with bug
    # Create tests/test_math.py with failing test
    return temp_repo
```

### Mock Strategy

Mock external dependencies:
- `subprocess.run` for pytest execution
- File system operations (when needed)

Don't mock:
- Internal logic
- Data structures
- AST parsing (use real Python AST)

## Error Handling Matrix

| Error Type | Cause | Behavior | Recovery |
|------------|-------|----------|----------|
| RepositoryNotFoundError | Invalid path | Raise immediately | User provides valid path |
| PytestNotInstalledError | pytest not in PATH | Raise immediately | Install pytest |
| BugDetectorError | Pytest timeout | Raise with context | Increase timeout or reduce test scope |
| SyntaxError | Invalid Python | Log warning, partial data | Fix syntax or skip file |
| FileNotFoundError | Traceback points to missing file | Empty context | Continue with other bugs |
| ValueError | Invalid line number | Empty context | Continue with other bugs |

## Future Enhancements

### Short Term
- [ ] Support for unittest framework
- [ ] Parallel test execution
- [ ] Progress callbacks
- [ ] Custom error message templates

### Medium Term
- [ ] Git integration (run only changed tests)
- [ ] Coverage analysis
- [ ] Performance profiling
- [ ] Configurable parsing patterns

### Long Term
- [ ] Support for other languages (JavaScript, Java, etc.)
- [ ] Machine learning for error classification
- [ ] Automatic test generation
- [ ] Integration with CI/CD systems

## Comparison with Alternatives

### pytest-json-report

**Pros of our approach**:
- More detailed code context
- Handles malformed output
- No additional dependencies
- Custom error handling

**Cons of our approach**:
- More complex parsing
- Need to maintain regex patterns

### Using pytest's internal API

**Pros of our approach**:
- Independent of pytest version
- Works with any pytest installation
- No tight coupling

**Cons of our approach**:
- Parsing overhead
- Potential breakage on format changes

## Conclusion

The Bug Detector module provides a robust, extensible foundation for the bug fixing pipeline. Its clean architecture, comprehensive error handling, and thorough testing make it production-ready while remaining easy to maintain and extend.

Key strengths:
- ✓ Clear separation of concerns
- ✓ Comprehensive error handling
- ✓ Rich code context extraction
- ✓ Well-tested with edge cases
- ✓ Detailed documentation
- ✓ Easy integration with downstream components
