"""Data models and schemas for the bug fixing pipeline."""

from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class BugReport:
    """Structured report for a single failing test.
    
    Attributes:
        test_name: Full name of the failing test (e.g., 'tests/test_math.py::test_divide')
        error_type: Type of error (e.g., 'AssertionError', 'TypeError')
        error_message: Full error message from the test failure
        file_path: Relative path to the source file containing the bug
        line_number: Line number where the error occurred
        failing_function_code: Complete code of the function containing the bug
        context_before: Lines of code before the failing function (for context)
        context_after: Lines of code after the failing function (for context)
        traceback: Full stack trace (optional, for debugging)
        inferred_source_module: Inferred source module name from test file (e.g., 'calculator.py' from 'test_calculator.py')
    """
    test_name: str
    error_type: str
    error_message: str
    file_path: str
    line_number: int
    failing_function_code: str
    context_before: str = ""
    context_after: str = ""
    traceback: Optional[str] = None
    inferred_source_module: str = ""


@dataclass
class BugDetectionResult:
    """Result of running bug detection on a repository.
    
    Attributes:
        bugs: List of bug reports for failing tests
        total_tests_run: Total number of tests executed
        total_failures: Number of test failures detected
        pytest_exit_code: Exit code from pytest (0 = success, 1 = failures, etc.)
    """
    bugs: List[BugReport] = field(default_factory=list)
    total_tests_run: int = 0
    total_failures: int = 0
    pytest_exit_code: int = 0
    
    @property
    def has_failures(self) -> bool:
        """Check if any test failures were detected."""
        return len(self.bugs) > 0
