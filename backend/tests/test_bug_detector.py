"""Unit tests for the Bug Detector module."""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.agents.bug_detector import (
    BugDetector,
    RepositoryNotFoundError,
    PytestNotInstalledError,
    BugDetectorError
)
from app.models.schemas import BugReport, BugDetectionResult


@pytest.fixture
def temp_repo():
    """Create a temporary repository for testing."""
    temp_dir = tempfile.mkdtemp()
    repo_path = Path(temp_dir)
    
    # Create directory structure
    src_dir = repo_path / "src"
    tests_dir = repo_path / "tests"
    src_dir.mkdir()
    tests_dir.mkdir()
    
    yield repo_path
    
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def repo_with_failing_test(temp_repo):
    """Create a repository with a failing test."""
    # Create source file with a bug
    src_file = temp_repo / "src" / "math_utils.py"
    src_file.write_text('''"""Math utility functions."""

def add(a, b):
    """Add two numbers."""
    return a + b

def subtract(a, b):
    """Subtract b from a."""
    return a - b

def divide(a, b):
    """Divide a by b. BUG: returns addition instead."""
    return a + b  # Bug: should be a / b

def multiply(a, b):
    """Multiply two numbers."""
    return a * b
''')
    
    # Create test file
    test_file = temp_repo / "tests" / "test_math_utils.py"
    test_file.write_text('''"""Tests for math utilities."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from math_utils import add, subtract, divide, multiply

def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0

def test_subtract():
    assert subtract(5, 3) == 2
    assert subtract(0, 5) == -5

def test_divide():
    """This test will fail due to the bug."""
    assert divide(10, 2) == 5
    assert divide(9, 3) == 3

def test_multiply():
    assert multiply(3, 4) == 12
    assert multiply(0, 100) == 0
''')
    
    return temp_repo


@pytest.fixture
def repo_with_all_passing_tests(temp_repo):
    """Create a repository with all passing tests."""
    # Create source file without bugs
    src_file = temp_repo / "src" / "calculator.py"
    src_file.write_text('''"""Calculator functions."""

def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
''')
    
    # Create test file
    test_file = temp_repo / "tests" / "test_calculator.py"
    test_file.write_text('''"""Tests for calculator."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from calculator import add, subtract

def test_add():
    assert add(1, 2) == 3

def test_subtract():
    assert subtract(5, 2) == 3
''')
    
    return temp_repo


@pytest.fixture
def repo_with_nested_functions(temp_repo):
    """Create a repository with nested functions and class methods."""
    # Create source file with nested functions
    src_file = temp_repo / "src" / "advanced.py"
    src_file.write_text('''"""Advanced code patterns."""

class Calculator:
    """Calculator class."""
    
    def __init__(self):
        self.result = 0
    
    def divide(self, a, b):
        """Divide with bug."""
        return a + b  # Bug: should be a / b
    
    def nested_operation(self, x):
        """Method with nested function."""
        def inner(y):
            return y * 2
        return inner(x) + 1

def outer_function(n):
    """Function with nested function."""
    def inner_function(m):
        return m - 1  # Bug: supposed to add
    return inner_function(n) + 5
''')
    
    # Create test file
    test_file = temp_repo / "tests" / "test_advanced.py"
    test_file.write_text('''"""Tests for advanced patterns."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from advanced import Calculator, outer_function

def test_calculator_divide():
    calc = Calculator()
    assert calc.divide(10, 2) == 5

def test_nested_operation():
    calc = Calculator()
    assert calc.nested_operation(3) == 7

def test_outer_function():
    assert outer_function(10) == 16
''')
    
    return temp_repo


class TestBugDetector:
    """Test suite for BugDetector class."""
    
    def test_init(self):
        """Test BugDetector initialization."""
        detector = BugDetector()
        assert detector.context_lines == 5
        
        detector_custom = BugDetector(context_lines=10)
        assert detector_custom.context_lines == 10
    
    def test_nonexistent_repository(self):
        """Test that nonexistent repository raises error."""
        detector = BugDetector()
        
        with pytest.raises(RepositoryNotFoundError):
            detector.run("/path/that/does/not/exist")
    
    def test_file_instead_of_directory(self, temp_repo):
        """Test that passing a file instead of directory raises error."""
        detector = BugDetector()
        test_file = temp_repo / "test.txt"
        test_file.write_text("not a directory")
        
        with pytest.raises(RepositoryNotFoundError):
            detector.run(str(test_file))
    
    @patch('subprocess.run')
    def test_pytest_not_installed(self, mock_run, temp_repo):
        """Test that missing pytest raises error."""
        mock_run.side_effect = FileNotFoundError()
        detector = BugDetector()
        
        with pytest.raises(PytestNotInstalledError):
            detector.run(str(temp_repo))
    
    def test_repo_with_failing_test(self, repo_with_failing_test):
        """Test detection of failing tests."""
        detector = BugDetector()
        result = detector.run(str(repo_with_failing_test))
        
        assert isinstance(result, BugDetectionResult)
        assert result.has_failures
        assert len(result.bugs) > 0
        assert result.total_failures > 0
        
        # Check the bug report structure
        bug = result.bugs[0]
        assert isinstance(bug, BugReport)
        assert "test_divide" in bug.test_name
        assert bug.error_type in ["AssertionError", "assert"]
        assert bug.file_path.endswith("math_utils.py")
        assert bug.line_number > 0
        assert "def divide" in bug.failing_function_code
        assert "return a + b" in bug.failing_function_code
    
    def test_repo_with_all_passing_tests(self, repo_with_all_passing_tests):
        """Test that passing tests return empty bug list."""
        detector = BugDetector()
        result = detector.run(str(repo_with_all_passing_tests))
        
        assert isinstance(result, BugDetectionResult)
        assert not result.has_failures
        assert len(result.bugs) == 0
        assert result.total_failures == 0
        assert result.pytest_exit_code == 0
    
    def test_specific_test_file(self, repo_with_failing_test):
        """Test running specific test files."""
        detector = BugDetector()
        result = detector.run(
            str(repo_with_failing_test),
            test_files=["tests/test_math_utils.py"]
        )
        
        assert result.has_failures
        assert len(result.bugs) > 0
    
    def test_custom_pytest_args(self, repo_with_failing_test):
        """Test passing custom pytest arguments."""
        detector = BugDetector()
        result = detector.run(
            str(repo_with_failing_test),
            pytest_args=["-x"]  # Stop after first failure
        )
        
        assert isinstance(result, BugDetectionResult)
        # Should still detect failures even with -x flag
        assert result.has_failures or result.pytest_exit_code != 0
    
    def test_code_context_extraction(self, repo_with_failing_test):
        """Test that code context is properly extracted."""
        detector = BugDetector()
        result = detector.run(str(repo_with_failing_test))
        
        if result.has_failures:
            bug = result.bugs[0]
            
            # Check function code extraction
            assert bug.failing_function_code != ""
            assert "def divide" in bug.failing_function_code
            
            # Check context before/after
            # Context before should contain previous function(s)
            if bug.context_before:
                assert "def" in bug.context_before or bug.context_before == ""
            
            # Context after should contain next function(s)
            if bug.context_after:
                assert "def" in bug.context_after or bug.context_after == ""
    
    def test_nested_functions_and_classes(self, repo_with_nested_functions):
        """Test extraction of class methods and nested functions."""
        detector = BugDetector()
        result = detector.run(str(repo_with_nested_functions))
        
        assert result.has_failures
        
        # Find the bug in Calculator.divide
        divide_bug = None
        for bug in result.bugs:
            if "test_calculator_divide" in bug.test_name:
                divide_bug = bug
                break
        
        assert divide_bug is not None
        assert "def divide" in divide_bug.failing_function_code
        assert "self" in divide_bug.failing_function_code  # It's a method
    
    def test_malformed_pytest_output(self, temp_repo):
        """Test handling of malformed pytest output."""
        detector = BugDetector()
        
        # Mock the pytest run to return malformed output
        with patch.object(detector, '_run_pytest') as mock_run:
            mock_run.return_value = (1, "MALFORMED OUTPUT WITH NO STRUCTURE")
            
            result = detector.run(str(temp_repo))
            
            # Should not crash, but may return empty or partial results
            assert isinstance(result, BugDetectionResult)
    
    def test_file_not_found_in_traceback(self, temp_repo):
        """Test handling when traceback references non-existent file."""
        detector = BugDetector()
        
        # Mock parsed failure with non-existent file
        failure_info = {
            'test_name': 'test_something',
            'error_type': 'ImportError',
            'error_message': 'Module not found',
            'file_path': 'nonexistent.py',
            'line_number': 10,
            'traceback': 'some traceback'
        }
        
        bug_report = detector._create_bug_report(temp_repo, failure_info)
        
        # Should create report even if file doesn't exist
        assert isinstance(bug_report, BugReport)
        assert bug_report.failing_function_code == ""
        assert bug_report.context_before == ""
        assert bug_report.context_after == ""
    
    def test_line_number_edge_cases(self, temp_repo):
        """Test handling of edge case line numbers."""
        detector = BugDetector()
        
        # Create a simple file
        src_file = temp_repo / "simple.py"
        src_file.write_text('''def func():
    return 1
''')
        
        # Test line number 0
        failure_info = {
            'test_name': 'test_zero',
            'error_type': 'Error',
            'error_message': 'test',
            'file_path': 'simple.py',
            'line_number': 0,
            'traceback': ''
        }
        
        bug_report = detector._create_bug_report(temp_repo, failure_info)
        assert bug_report.failing_function_code == ""
        
        # Test very large line number
        failure_info['line_number'] = 999999
        bug_report = detector._create_bug_report(temp_repo, failure_info)
        # Should not crash
        assert isinstance(bug_report, BugReport)
    
    def test_syntax_error_in_source(self, temp_repo):
        """Test handling of source files with syntax errors."""
        # Create file with syntax error
        src_file = temp_repo / "src" / "broken.py"
        src_file.write_text('''def broken_function(
    # Missing closing parenthesis
    return "broken"
''')
        
        detector = BugDetector()
        
        # Should handle syntax error gracefully
        code, before, after = detector._extract_code_context(
            temp_repo, "src/broken.py", 2
        )
        
        # Should return something even with syntax error
        assert isinstance(code, str)
    
    def test_multiple_failures(self, temp_repo):
        """Test handling multiple test failures."""
        # Create source with multiple bugs
        src_file = temp_repo / "src" / "multi_bug.py"
        src_file.write_text('''def bug1():
    return 1 + 1  # Should return 3

def bug2():
    return 5 - 1  # Should return 5
''')
        
        test_file = temp_repo / "tests" / "test_multi.py"
        test_file.write_text('''import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from multi_bug import bug1, bug2

def test_bug1():
    assert bug1() == 3

def test_bug2():
    assert bug2() == 5
''')
        
        detector = BugDetector()
        result = detector.run(str(temp_repo))
        
        # Should detect multiple failures
        assert len(result.bugs) == 2
        assert result.total_failures == 2
    
    def test_context_lines_customization(self, repo_with_failing_test):
        """Test custom context_lines parameter."""
        detector_small = BugDetector(context_lines=2)
        detector_large = BugDetector(context_lines=10)
        
        result_small = detector_small.run(str(repo_with_failing_test))
        result_large = detector_large.run(str(repo_with_failing_test))
        
        if result_small.has_failures and result_large.has_failures:
            # Larger context should have more or equal lines
            small_context_len = len(result_small.bugs[0].context_before.splitlines())
            large_context_len = len(result_large.bugs[0].context_before.splitlines())
            
            assert large_context_len >= small_context_len
    
    @patch('subprocess.run')
    def test_pytest_timeout(self, mock_run, temp_repo):
        """Test handling of pytest timeout."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="pytest 7.0.0", stderr=""),  # --version check
            subprocess.TimeoutExpired("pytest", 300)  # Actual run times out
        ]
        
        detector = BugDetector()
        
        with pytest.raises(BugDetectorError) as exc_info:
            detector.run(str(temp_repo))
        
        assert "timed out" in str(exc_info.value).lower()
    
    def test_extract_test_stats(self):
        """Test extraction of test statistics from pytest output."""
        detector = BugDetector()
        
        # Test typical pytest summary
        output1 = "=== 2 failed, 3 passed in 0.05s ==="
        total, failures = detector._extract_test_stats(output1)
        assert total == 5
        assert failures == 2
        
        # Test only failures
        output2 = "=== 1 failed in 0.01s ==="
        total, failures = detector._extract_test_stats(output2)
        assert failures == 1
        
        # Test only passes
        output3 = "=== 5 passed in 0.10s ==="
        total, failures = detector._extract_test_stats(output3)
        assert total == 5
        assert failures == 0
        
        # Test no stats
        output4 = "Some random output"
        total, failures = detector._extract_test_stats(output4)
        assert total == 0
        assert failures == 0


class TestBugReport:
    """Test suite for BugReport dataclass."""
    
    def test_bug_report_creation(self):
        """Test creating a BugReport instance."""
        report = BugReport(
            test_name="tests/test_file.py::test_function",
            error_type="AssertionError",
            error_message="Expected 5, got 3",
            file_path="src/module.py",
            line_number=42,
            failing_function_code="def function():\n    return 3",
            context_before="# Some context",
            context_after="# More code",
            traceback="Full traceback here"
        )
        
        assert report.test_name == "tests/test_file.py::test_function"
        assert report.error_type == "AssertionError"
        assert report.line_number == 42
        assert report.traceback == "Full traceback here"
    
    def test_bug_report_optional_fields(self):
        """Test BugReport with optional fields."""
        report = BugReport(
            test_name="test",
            error_type="Error",
            error_message="message",
            file_path="file.py",
            line_number=1,
            failing_function_code="code"
        )
        
        assert report.context_before == ""
        assert report.context_after == ""
        assert report.traceback is None


class TestBugDetectionResult:
    """Test suite for BugDetectionResult dataclass."""
    
    def test_detection_result_creation(self):
        """Test creating a BugDetectionResult instance."""
        bug1 = BugReport(
            test_name="test1",
            error_type="Error",
            error_message="msg",
            file_path="file.py",
            line_number=1,
            failing_function_code="code"
        )
        
        result = BugDetectionResult(
            bugs=[bug1],
            total_tests_run=10,
            total_failures=1,
            pytest_exit_code=1
        )
        
        assert len(result.bugs) == 1
        assert result.total_tests_run == 10
        assert result.total_failures == 1
        assert result.has_failures is True
    
    def test_detection_result_no_failures(self):
        """Test BugDetectionResult with no failures."""
        result = BugDetectionResult(
            bugs=[],
            total_tests_run=5,
            total_failures=0,
            pytest_exit_code=0
        )
        
        assert len(result.bugs) == 0
        assert result.has_failures is False
    
    def test_detection_result_defaults(self):
        """Test BugDetectionResult default values."""
        result = BugDetectionResult()
        
        assert result.bugs == []
        assert result.total_tests_run == 0
        assert result.total_failures == 0
        assert result.pytest_exit_code == 0
        assert result.has_failures is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
