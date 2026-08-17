# Bug Detector - Quick Start Guide

## 5-Minute Getting Started

### Installation

```bash
pip install pytest
```

### Basic Usage

```python
from app.agents import BugDetector

# Initialize
detector = BugDetector()

# Run detection
result = detector.run("/path/to/your/repo")

# Check results
if result.has_failures:
    for bug in result.bugs:
        print(f"Bug: {bug.test_name}")
        print(f"Location: {bug.file_path}:{bug.line_number}")
        print(f"Error: {bug.error_message}")
        print(f"Code:\n{bug.failing_function_code}")
```

### Output Structure

```python
BugDetectionResult(
    bugs=[BugReport(...), BugReport(...)],  # List of bugs
    total_tests_run=10,                      # Total tests
    total_failures=2,                        # Failed tests
    pytest_exit_code=1                       # Pytest exit code
)

BugReport(
    test_name="tests/test_file.py::test_func",  # Full test name
    error_type="AssertionError",                 # Error type
    error_message="assert 5 == 3",              # Error message
    file_path="src/module.py",                  # Source file
    line_number=42,                             # Line number
    failing_function_code="def func():\n...",   # Complete function
    context_before="...",                       # Lines before
    context_after="...",                        # Lines after
    traceback="..."                             # Full traceback
)
```

## Common Use Cases

### 1. Detect All Bugs in a Repository

```python
detector = BugDetector()
result = detector.run("/path/to/repo")
print(f"Found {len(result.bugs)} bugs")
```

### 2. Run Specific Test Files

```python
result = detector.run(
    "/path/to/repo",
    test_files=["tests/test_critical.py", "tests/test_core.py"]
)
```

### 3. Custom Pytest Options

```python
result = detector.run(
    "/path/to/repo",
    pytest_args=["-x", "--tb=long", "-v"]  # Stop on first, long traceback
)
```

### 4. More Code Context

```python
detector = BugDetector(context_lines=10)  # 10 lines before/after
result = detector.run("/path/to/repo")
```

### 5. Integration with Patch Generator

```python
from app.agents import BugDetector

class PatchGenerator:
    def __init__(self):
        self.detector = BugDetector()
    
    def generate_patches(self, repo_path):
        result = self.detector.run(repo_path)
        
        patches = []
        for bug in result.bugs:
            # Use bug info to generate fix
            patch = self.create_patch(
                bug.failing_function_code,
                bug.error_message
            )
            patches.append(patch)
        
        return patches
```

## Error Handling

```python
from app.agents import (
    BugDetector,
    RepositoryNotFoundError,
    PytestNotInstalledError,
    BugDetectorError
)

try:
    detector = BugDetector()
    result = detector.run("/path/to/repo")
except RepositoryNotFoundError:
    print("Repository not found!")
except PytestNotInstalledError:
    print("Please install pytest: pip install pytest")
except BugDetectorError as e:
    print(f"Error during detection: {e}")
```

## What Gets Extracted

For this buggy code:

```python
# src/math_utils.py
def add(a, b):
    """Add two numbers."""
    return a + b

def divide(a, b):
    """Divide a by b."""
    return a + b  # BUG: should be a / b

def multiply(a, b):
    """Multiply two numbers."""
    return a * b
```

You get:

```python
BugReport(
    test_name="tests/test_math.py::test_divide",
    error_type="AssertionError",
    error_message="assert 12 == 5",
    file_path="src/math_utils.py",
    line_number=7,
    
    # The function with the bug
    failing_function_code='''def divide(a, b):
    """Divide a by b."""
    return a + b  # BUG: should be a / b''',
    
    # Code before the function
    context_before='''def add(a, b):
    """Add two numbers."""
    return a + b''',
    
    # Code after the function
    context_after='''def multiply(a, b):
    """Multiply two numbers."""
    return a * b''',
    
    traceback="...full pytest traceback..."
)
```

## Key Features

✓ **Automatic test discovery**: Runs all tests in the repository  
✓ **Detailed error extraction**: Type, message, location  
✓ **Complete function code**: Full source of failing functions  
✓ **Surrounding context**: Lines before/after for understanding  
✓ **Multiple failure support**: Handles all failures, not just first  
✓ **Nested function support**: Works with class methods, nested functions  
✓ **Graceful error handling**: Continues even if some extractions fail  
✓ **Zero configuration**: Works out of the box  

## Testing

Run the test suite:

```bash
pytest tests/test_bug_detector.py -v
```

Expected output:
```
tests/test_bug_detector.py::TestBugDetector::test_init PASSED
tests/test_bug_detector.py::TestBugDetector::test_nonexistent_repository PASSED
tests/test_bug_detector.py::TestBugDetector::test_repo_with_failing_test PASSED
tests/test_bug_detector.py::TestBugDetector::test_repo_with_all_passing_tests PASSED
...
==================== 25 passed in 5.23s ====================
```

## Next Steps

1. ✓ Install pytest
2. ✓ Run example: `python examples/bug_detector_example.py`
3. ✓ Test on your repo: `detector.run("/your/repo")`
4. → Build Patch Generator to consume bug reports
5. → Integrate with full pipeline

## Need Help?

- **Full documentation**: See `README.md` in this directory
- **Design details**: See `docs/bug_detector_design.md`
- **Examples**: See `examples/bug_detector_example.py`
- **Tests**: See `tests/test_bug_detector.py`

## Quick Reference

```python
# Imports
from app.agents import BugDetector
from app.models import BugReport, BugDetectionResult

# Initialize
detector = BugDetector(context_lines=5)

# Run
result = detector.run(repo_path, test_files=None, pytest_args=None)

# Access results
result.bugs              # List[BugReport]
result.total_tests_run   # int
result.total_failures    # int
result.pytest_exit_code  # int
result.has_failures      # bool

# Each BugReport has
bug.test_name                # str
bug.error_type              # str
bug.error_message           # str
bug.file_path               # str
bug.line_number             # int
bug.failing_function_code   # str
bug.context_before          # str
bug.context_after           # str
bug.traceback               # Optional[str]
```

That's it! You're ready to detect bugs automatically. 🐛🔍
