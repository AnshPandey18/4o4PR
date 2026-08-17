# Bug Detector Module

The Bug Detector is a core component of the Automated Bug Fixing Agent pipeline. It identifies failing tests in Python repositories and extracts relevant code context for downstream processing.

## Overview

The Bug Detector module:
1. Runs pytest on a target Python repository
2. Parses test output to identify failures
3. Extracts code context (function, surrounding lines)
4. Returns structured bug reports for the Patch Generator

## Installation

Ensure pytest is installed:
```bash
pip install pytest
```

## Usage

### Basic Usage

```python
from app.agents import BugDetector

detector = BugDetector()
result = detector.run("/path/to/repo")

if result.has_failures:
    for bug in result.bugs:
        print(f"Bug in {bug.file_path}:{bug.line_number}")
        print(f"Function: {bug.failing_function_code}")
```

### Run Specific Test Files

```python
result = detector.run(
    "/path/to/repo",
    test_files=["tests/test_math.py", "tests/test_utils.py"]
)
```

### Custom Pytest Arguments

```python
result = detector.run(
    "/path/to/repo",
    pytest_args=["-v", "--tb=long", "-x"]
)
```

### Custom Context Lines

```python
detector = BugDetector(context_lines=10)  # Extract 10 lines before/after
result = detector.run("/path/to/repo")
```

## API Reference

### BugDetector

**Constructor:**
```python
BugDetector(context_lines: int = 5)
```
- `context_lines`: Number of lines to extract before/after the failing function

**Methods:**

#### `run(repo_path, test_files=None, pytest_args=None)`

Run bug detection on a repository.

**Parameters:**
- `repo_path` (str): Path to the target repository
- `test_files` (List[str], optional): Specific test files to run
- `pytest_args` (List[str], optional): Additional pytest arguments

**Returns:** `BugDetectionResult`

**Raises:**
- `RepositoryNotFoundError`: If repo_path doesn't exist
- `PytestNotInstalledError`: If pytest is not available
- `BugDetectorError`: For other execution errors

### BugReport

Dataclass representing a single bug.

**Attributes:**
- `test_name` (str): Full test name (e.g., "tests/test_math.py::test_divide")
- `error_type` (str): Error type (e.g., "AssertionError", "TypeError")
- `error_message` (str): Error message from test failure
- `file_path` (str): Relative path to source file with bug
- `line_number` (int): Line number of the error
- `failing_function_code` (str): Complete code of failing function
- `context_before` (str): Code lines before the function
- `context_after` (str): Code lines after the function
- `traceback` (str, optional): Full stack trace

### BugDetectionResult

Dataclass representing detection results.

**Attributes:**
- `bugs` (List[BugReport]): List of detected bugs
- `total_tests_run` (int): Total number of tests executed
- `total_failures` (int): Number of test failures
- `pytest_exit_code` (int): Exit code from pytest
- `has_failures` (bool): Property indicating if bugs were found

## Error Handling

The module includes custom exceptions:

- **RepositoryNotFoundError**: Repository path doesn't exist or isn't a directory
- **PytestNotInstalledError**: pytest command not found in PATH
- **BugDetectorError**: General errors during detection

Example:
```python
from app.agents import BugDetector, RepositoryNotFoundError

try:
    detector = BugDetector()
    result = detector.run("/path/to/repo")
except RepositoryNotFoundError as e:
    print(f"Repository error: {e}")
except PytestNotInstalledError as e:
    print(f"Please install pytest: {e}")
```

## Edge Cases Handled

The Bug Detector gracefully handles:

- **Missing files**: Returns empty context if source file not found
- **Invalid line numbers**: Handles out-of-range line numbers
- **Syntax errors**: Extracts partial context from files with syntax errors
- **Nested functions**: Correctly identifies nested and class methods
- **Malformed pytest output**: Doesn't crash on unexpected output
- **Timeouts**: 5-minute timeout for pytest execution
- **Multiple failures**: Processes all failures, not just the first

## Architecture

The module follows a clean, modular design:

```
BugDetector
├── _validate_repository()      # Validate repo exists
├── _check_pytest_available()   # Ensure pytest is installed
├── _run_pytest()                # Execute pytest and capture output
├── _parse_pytest_output()       # Parse output for failures
├── _create_bug_report()         # Create structured report
└── _extract_code_context()      # Extract function and context
    ├── _extract_function_by_line()
    ├── _get_function_line_range()
    └── _get_node_end_line()
```

Each method has a single responsibility, making the code:
- Easy to test
- Easy to maintain
- Easy to extend

## Testing

Run the test suite:
```bash
pytest tests/test_bug_detector.py -v
```

The test suite includes:
- Repositories with failing tests
- Repositories with all passing tests
- Nested functions and class methods
- Malformed pytest output handling
- Edge cases (missing files, invalid line numbers)
- Multiple test failures
- Custom configuration options

## Integration with Patch Generator

The Bug Detector feeds into the Patch Generator (Step 2 of the pipeline):

```python
class PatchGenerator:
    def __init__(self):
        self.bug_detector = BugDetector()
    
    def generate_fixes(self, repo_path):
        # Step 1: Detect bugs
        result = self.bug_detector.run(repo_path)
        
        if not result.has_failures:
            return []
        
        # Step 2: Generate patches for each bug
        patches = []
        for bug in result.bugs:
            patch = self._generate_patch(
                bug.failing_function_code,
                bug.error_message,
                bug.context_before,
                bug.context_after
            )
            patches.append(patch)
        
        return patches
```

## Examples

See `examples/bug_detector_example.py` for complete usage examples.

## Performance

- **Timeout**: 5 minutes for pytest execution
- **Context extraction**: Uses AST parsing for accurate function boundaries
- **Error resilience**: Continues processing even if individual bug extraction fails

## Future Enhancements

Possible improvements:
- Support for other test frameworks (unittest, nose2)
- Parallel test execution
- Caching of source file parsing
- Git integration to detect changed files
- Coverage analysis integration
